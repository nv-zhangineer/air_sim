import ipaddress
import pandas as pd
import math
from typing import List, Dict
from data_handler import payload_handler

# TODO - update interface naming for hosts and add configurations to host interfaces
# TODO - add support to start from non-zero


class NetworkMapping:
    def __init__(self,
                 num_hosts: int = None,
                 input_data: Dict = None,
                 start_id: int = 0,
                 digit_filler: int = 3,
                 host_prefix: str = "dgx",
                 leaf_prefix: str = "leaf",
                 spine_prefix: str = "spine",
                 host_p2p_lead_octet: int = 172,
                 spine_base_as: int = 65200,
                 leaf_base_as: int = 65000,
                 p2pmask: str = "/31",
                 breakout: int = 2,
                 num_spines: int = 0,
                 nvidia_air=True,
                 file_dir: str = None):
        """
        :param num_hosts: number of hosts (DGX nodes)
        :param input_data: customized input data. User would provide a spreadsheet that's converted to dictionary
        :param start_id: starting ID assignment, this applies to all hosts, leafs and spines
        :param digit_filler: number of digits for leaf/spine/host IDs, we'll autofill up to the specified count
        :param host_prefix: prefix for the host name
        :param leaf_prefix: prefix for the leaf name
        :param spine_prefix: prefix for the spine name
        :param host_p2p_lead_octet: the first octet to be used for the IP for host point-to-point routed connection
        :param spine_base_as: base AS number for spines for BGP peering
        :param leaf_base_as: base AS number for leafs for BGP peering
        :param p2pmask: subnet mask for point-to-point connection, default is /31 and unchangeable
        :param breakout: number of breakout ports, default is 2 and only supported is 2
        :param num_spines: this field is only used when user_input data is provided
        :param nvidia_air: (True)/False, if True, we need to create NVIDIA AIR specific device definitions as well.
        #     for example: [function="spine" memory="2048" os="cumulus-vx-5.6.0" cpu="2" storage="10"]
        :param file_dir: directory where we would store all the files generated from the script
        """
        # starting numerical value for node IDs, IP assignments...etc. 0 allows max scalability
        self.start_id = start_id
        self.input_data = input_data
        self.digit_filler = digit_filler
        self.host_prefix = host_prefix
        self.leaf_prefix = leaf_prefix
        self.spine_prefix = spine_prefix
        self.leaf_spine_mapping_data = []
        self.host_p2p_lead_octet = host_p2p_lead_octet
        self.bgp_global_data = []
        self.spine_base_as = spine_base_as
        self.leaf_base_as = leaf_base_as
        self.leaf_spine_dot_data = []
        self.p2pmask = p2pmask
        self.breakout = breakout
        self.nvidia_air = nvidia_air
        if self.nvidia_air:
            self.breakout = 1
        self.num_hosts = num_hosts
        self.num_sus = 1
        self.num_leafs = 4
        self.num_spines = num_spines
        self.file_dir = file_dir

        if self.input_data:
            self.leaf_host_p2p_data = input_data['leaf_host_p2p']
            self.leaf_spine_p2p_data = input_data['leaf_spine_p2p']
            self.num_gpus = len(self.leaf_host_p2p_data)
            if self.num_gpus % 8 != 0:
                raise ValueError(f"The number of leaf_host_p2p entries ({self.num_gpus}) is not divisible by 8.")
            if len(self.leaf_spine_p2p_data) % 8 != 0:
                raise ValueError(f"The number of leaf_spine_p2p entries ({len(self.leaf_spine_p2p_data)}) "
                                 f"is not divisible by 8.")
            self.num_hosts = self.num_gpus / 8
            self.num_leafs = int(self.num_hosts / 8)
            # in the case with self input data
            # we don't auto calculate spine because we don't know if the customer follows best practice
            # meaning that spine count should always be to the power of 2 such as 2, 4, 8, 16...etc.
            # best practice is that even if you aren't using the spines, you should still purchase them for expansion,
            # you don't have to re-adjust cables later on
            if self.num_spines > 0:
                self.leaf_spine_mapping_data = self._create_leaf_spine_mapping_data()
                self.leaf_spine_dot_data = self._create_leaf_spine_dot_data()
                self.leaf_spine_interface_data = self._create_leaf_spine_interface_data()
                self.bgp_global_data = self._create_bgp_global_data()
                self.bgp_session_data = self._create_bgp_session_data()

        elif num_hosts:
            if self.num_hosts > 1024:  # 3-tier
                pass
            if self.num_hosts > 32:  # 2-tier
                self.num_sus = math.ceil(self.num_hosts / 32) if num_hosts else 0
                self.num_spines = self._calculate_num_spines()
                self.num_leafs = int(self.num_hosts / 8)
                self.leaf_spine_mapping_data = self._create_leaf_spine_mapping_data()
                self.leaf_spine_dot_data = self._create_leaf_spine_dot_data()
                self.leaf_spine_interface_data = self._create_leaf_spine_interface_data()
                self.bgp_global_data = self._create_bgp_global_data()
                self.bgp_session_data = self._create_bgp_session_data()

        self.leaf_host_mapping_data = self._create_leaf_host_mapping_data()
        self.host_dot_data = self._create_leaf_host_dot_data()
        self.devices = self._get_devices()
        self.leafs = self._get_leafs()
        self.spines = self._get_spines()

        # Combine host and leaf-spine point-to-point data
        self.dot_data = self.host_dot_data + self.leaf_spine_dot_data

    @staticmethod
    def _generate_host_ip(x, pod_id, su_id, rail_id, local_host_id):
        # Check if host_id exceeds the limit for 6 bits (maximum value is 62 in decimal)
        if local_host_id > 62:
            raise ValueError(f"host_id ({local_host_id}) is too large. It must be between 0 and 62 inclusive.")

        rail_bin = f"{rail_id:03b}"
        pod_bin = f"{pod_id:05b}"
        y_bin = rail_bin + pod_bin
        y = int(y_bin, 2)
        z = su_id

        # Generate NIC and Switch binary representations
        w_nic_bin = f"00{local_host_id:05b}0"  # NIC
        if len(w_nic_bin) > 8:
            raise ValueError(f"Generated NIC binary ({w_nic_bin}) exceeds 8 bits.")

        w_switch_bin = f"00{local_host_id:05b}1"  # Switch
        if len(w_switch_bin) > 8:
            raise ValueError(f"Generated Switch binary ({w_switch_bin}) exceeds 8 bits.")

        w_nic = int(w_nic_bin, 2)
        w_switch = int(w_switch_bin, 2)

        ip_nic = ipaddress.IPv4Address((x << 24) | (y << 16) | (z << 8) | w_nic)
        ip_switch = ipaddress.IPv4Address((x << 24) | (y << 16) | (z << 8) | w_switch)

        return ip_nic, ip_switch

    def _calculate_num_spines(self):
        raw_num_spines = self.num_hosts * 8 / 128
        num_spines = math.ceil(raw_num_spines)
        if num_spines & (num_spines - 1) != 0:  # Check if not a power of 2
            num_spines = 2 ** math.ceil(math.log2(num_spines))

        return num_spines

    def _create_leaf_host_mapping_data(self):
        if self.input_data:
            return self._create_leaf_host_mapping_from_input()
        else:
            pod_id = 0
            result = []

            global_host_id = 0

            for su_id in range(self.num_sus):
                for local_host_id in range(32):
                    if global_host_id >= self.num_hosts:
                        break
                    # print("base interface is...", base_intf)

                    # print("swp_intf is...", swp_intf)
                    connections_per_leaf = 2

                    for rail_id in range(8):
                        leaf_id = su_id * 4 + (rail_id // connections_per_leaf)
                        nic_ip, switch_ip = self._generate_host_ip(self.host_p2p_lead_octet,
                                                                   pod_id,
                                                                   su_id,
                                                                   rail_id,
                                                                   local_host_id)
                        leaf_name = f"{self.leaf_prefix}{str(leaf_id).zfill(self.digit_filler)}"

                        # base_intf is the interface that we start assignment,
                        # local_host_id always goes from 0 to 31, since we assign 2 host ports to the same leaf,
                        # we calculate the starting switch port number by using the formula below.
                        # rail_id goes from 0 to 7

                        # if breakout ports is > 1, we would loop through all the breakout ports
                        if self.breakout > 1:
                            # base_intf value is only used when we have breakouts
                            base_intf = local_host_id + 1
                            swp_intf = f"swp{base_intf}"
                            breakout_ports = self._convert_swp_to_breakout(swp_intf)
                            leaf_intf = breakout_ports[rail_id % self.breakout]
                        else:
                            if rail_id % 2 == 0:
                                swp_intf = (local_host_id + 1) * 2 - 1
                            else:
                                swp_intf = (local_host_id + 1) * 2
                            leaf_intf = f"swp{swp_intf}"

                        host_name = f"{self.host_prefix}{str(global_host_id).zfill(self.digit_filler)}"
                        host_intf = f"rail{rail_id + 1}"
                        result.append({
                            "SU": su_id,
                            "HostID": global_host_id,
                            "HostName": host_name,
                            "Rail": rail_id,
                            "HostIntf": host_intf,
                            "HostIntfIP": str(nic_ip),
                            "LeafID": leaf_id,
                            "LeafName": leaf_name,
                            "LeafIntf": leaf_intf,
                            "LeafIntfIP": str(switch_ip),
                            "Mask": self.p2pmask,
                            "Description": f"{host_name}-{host_intf}"
                        })
                    global_host_id += 1
            return result

    def _create_leaf_host_mapping_from_input(self) -> List[Dict]:
        """
        Parses user-provided host mapping data.

        :return: List of parsed host mapping dictionaries.
        """
        result = []
        for row in self.input_data['leaf_host_p2p']:
            nic_ip, switch_ip = self._generate_host_ip(
                self.host_p2p_lead_octet,
                pod_id=int(row["PodID"]),
                su_id=int(row["SU"]),
                rail_id=int(row["RailID"]),
                local_host_id=int(row["HostID"]) % 32,
            )
            result.append({
                "SU": int(row["SU"]),
                "HostID": int(row["HostID"]),
                "HostName": row["Hostname"],
                "Rail": int(row["RailID"]),
                "HostIntf": row["RailPort"],
                "HostIntfIP": str(nic_ip),
                "LeafID": int(row["LeafID"]),
                "LeafName": row["LeafName"],
                "LeafIntf": row["LeafIntf"],
                "LeafIntfIP": str(switch_ip),
                "Mask": self.p2pmask,
                "Description": row.get("Description", f"{row['Hostname']}-{row['RailPort']}"),
            })
        return result

    def _create_leaf_spine_mapping_data(self) -> List[Dict]:
        #TODO add support for multi-pod
        result = []

        if self.input_data:
            return self._create_leaf_spine_mapping_from_input()
        else:
            leaf_connections_to_each_spine = 64 // self.num_spines
            # we start spine connection after assigned all downlink ports to DGX
            # we need to increment this number by `leaf_connections_to_each_spine` count after looping through
            # all ports connected to a given spine
            starting_leaf_intf_id = int(128 / (self.breakout * 2) + 1)  # +1 because interface ID starts at 1
            for spine_id in range(self.num_spines):
                spine_as = spine_id + self.spine_base_as
                base_ip = ipaddress.IPv4Address(f"10.254.{spine_id}.0")
                spine_intf_offset = 1

                for leaf_id in range(self.num_leafs):   # start from 0

                    leaf_as = self.leaf_base_as + leaf_id
                    su_id = leaf_id // 4
                    current_leaf_intf_id = starting_leaf_intf_id  # +1 because interface ID starts at 1

                    for connection in range(leaf_connections_to_each_spine):
                        breakout_index = connection % self.breakout
                        leaf_swp = f"swp{current_leaf_intf_id}"
                        spine_swp = f"swp{int((connection // self.breakout) + spine_intf_offset)}"

                        leaf_breakout_ports = self._convert_swp_to_breakout(leaf_swp) if self.breakout > 1 else [
                            leaf_swp]

                        spine_breakout_ports = self._convert_swp_to_breakout(spine_swp) if self.breakout > 1 else [
                            spine_swp]

                        leaf_intf = leaf_breakout_ports[breakout_index]
                        spine_intf = spine_breakout_ports[breakout_index]

                        base_port = int(spine_intf.split('swp')[1].split('s')[0])
                        numerical_value = (base_port - 1) * self.breakout + breakout_index + 1
                        spine_ip = base_ip + (numerical_value - 1) * 2
                        leaf_ip = spine_ip + 1

                        result.append({
                            "SU": su_id,
                            "SpineID": spine_id,
                            "SpineName": f"{self.spine_prefix}{str(spine_id).zfill(self.digit_filler)}",
                            "SpineIntf": spine_intf,
                            "SpineIntfIP": str(spine_ip),
                            "SpineAS": spine_as,
                            "LeafID": leaf_id,
                            "LeafName": f"{self.leaf_prefix}{str(leaf_id).zfill(self.digit_filler)}",
                            "LeafIntf": leaf_intf,
                            "LeafIntfIP": str(leaf_ip),
                            "LeafAS": leaf_as,
                            "Mask": self.p2pmask
                        })

                        if breakout_index == self.breakout - 1:
                            current_leaf_intf_id += 1
                    # we need to increment the number of interfaces after
                    spine_intf_offset += int(leaf_connections_to_each_spine / self.breakout)
                # we increment the number of connections / breakout because physical port numbers gets incremented
                # we should not account for breakouts when incrementing
                # meaning that when we increment 8 physical port number,
                # we are actually going to loop through 8 * num_breakout ports ( 16 if breakout = 2 )
                starting_leaf_intf_id += int(leaf_connections_to_each_spine / self.breakout)
            return result

    def _create_leaf_spine_mapping_from_input(self) -> List[Dict]:
        """
        Parses user-provided leaf-spine mapping data.

        :return: List of parsed leaf-spine mapping dictionaries.
        """
        result = []

        def extract_intf_id(port_name):
            if "swp" in port_name:
                return int(port_name.split("swp")[1])
            return None

        for row in self.input_data['leaf_spine_p2p']:
            spine_id = int(row["SpineID"])
            spine_as = spine_id + self.spine_base_as
            base_ip = ipaddress.IPv4Address(f"10.254.{spine_id}.0")
            leaf_id = int(row["LeafID"])
            leaf_as = self.leaf_base_as + leaf_id
            spine_intf_id = extract_intf_id(row["SpineIntf"])
            spine_intf_ip = base_ip + (spine_intf_id - 1) * 2
            leaf_intf_ip = spine_intf_ip + 1

            result.append({
                "SU": int(row["SU"]),
                "SpineID": spine_id,
                "SpineName": row["SpineName"],
                "SpineIntf": row["SpineIntf"],
                "SpineIntfIP": spine_intf_ip,
                "SpineAS": spine_as,
                "LeafID": leaf_id,
                "LeafName": row["LeafName"],
                "LeafIntf": row["LeafIntf"],
                "LeafIntfIP": leaf_intf_ip,
                "LeafAS": leaf_as,
                "Mask": self.p2pmask,
            })
        return result

    def _create_leaf_spine_interface_data(self) -> List[Dict]:
        device_interface_data = []

        for entry in self.leaf_spine_mapping_data:
            # Add spine data
            device_interface_data.append({
                'DeviceName': entry['SpineName'],
                'Interface': entry['SpineIntf'],
                'InterfaceIP': entry['SpineIntfIP'],
                'Mask': self.p2pmask
            })

            # Add leaf data
            device_interface_data.append({
                'DeviceName': entry['LeafName'],
                'Interface': entry['LeafIntf'],
                'InterfaceIP': entry['LeafIntfIP'],
                'Mask': self.p2pmask
            })

        return device_interface_data

    def _create_bgp_global_data(self) -> List[Dict]:
        leaf_base_lo_ip = ipaddress.IPv4Address("10.0.0.0")
        spine_base_lo_ip = ipaddress.IPv4Address("10.1.0.0")
        super_spine_base_lo_ip = ipaddress.IPv4Address("10.2.0.0")

        unique_entries = set()
        bgp_global_data = []

        for entry in self.leaf_spine_mapping_data:
            # Spine Data
            spine_data = {
                "DeviceName": entry['SpineName'],
                "VRF": "default",
                "AS": self.spine_base_as + entry['SpineID'],
                "LoopbackIP": spine_base_lo_ip + entry['SpineID'],
                "RouterID": spine_base_lo_ip + entry['SpineID'],
            }
            if tuple(spine_data.items()) not in unique_entries:
                unique_entries.add(tuple(spine_data.items()))
                bgp_global_data.append(spine_data)

            # Leaf Data
            leaf_data = {
                "DeviceName": entry['LeafName'],
                "VRF": "default",
                "AS": self.leaf_base_as + entry['LeafID'],
                "LoopbackIP": leaf_base_lo_ip + entry['LeafID'],
                "RouterID": leaf_base_lo_ip + entry['LeafID'],
            }
            if tuple(leaf_data.items()) not in unique_entries:
                unique_entries.add(tuple(leaf_data.items()))
                bgp_global_data.append(leaf_data)
        return sorted(bgp_global_data, key=lambda x: x["DeviceName"])

    def _create_bgp_session_data(self) -> List[Dict]:
        bgp_session_data = []

        for entry in self.leaf_spine_mapping_data:
            # Add spine data
            bgp_session_data.append({
                'DeviceName': entry['SpineName'],
                'VRF': "default",
                'LocalAS': entry['SpineAS'],
                'NeighborIP': entry['LeafIntfIP'],
                'RemoteAS': entry['LeafAS']
            })

            # Add leaf data
            bgp_session_data.append({
                'DeviceName': entry['LeafName'],
                'VRF': "default",
                'LocalAS': entry['LeafAS'],
                'NeighborIP': entry['SpineIntfIP'],
                'RemoteAS': entry['SpineAS']
            })

        return sorted(bgp_session_data, key=lambda x: x["DeviceName"])

    def _get_host_list(self) -> List[Dict]:
        """
        Get a list of DGX hosts
        :return: list of DGX hosts in a dictionary format with device name and their roles
        """
        host_list = []
        unique_entries = set()

        for entry in self.leaf_host_mapping_data:
            host_data = {
                'DeviceName': entry['HostName'],
                'Role': 'host'
            }
            if tuple(host_data.items()) not in unique_entries:
                unique_entries.add(tuple(host_data.items()))
                host_list.append(host_data)
        return host_list

    def _get_leafs(self) -> list[Dict]:
        """
        :return: a list of Leafs with "DeviceName" and "Role" dictionary keys
            [{'DeviceName': 'leaf000', 'Role': 'leaf'}, {'DeviceName': 'leaf001', 'Role': 'leaf'},
            {'DeviceName': 'leaf002', 'Role': 'leaf'}, {'DeviceName': 'leaf003', 'Role': 'leaf'}]
        """
        return [entry for entry in self.devices if 'leaf' in entry['Role']]

    def _get_spines(self) -> list[Dict]:
        """
        :return: a list of Spines with "DeviceName" and "Role" dictionary keys
            [{'DeviceName': 'spine000', 'Role': 'spine'}, {'DeviceName': 'spine001', 'Role': 'spine'},
            {'DeviceName': 'spine002', 'Role': 'spine'}, {'DeviceName': 'spine003', 'Role': 'spine'}]
        """
        return [entry for entry in self.devices if 'spine' in entry['Role']]

    def _get_devices(self) -> List[Dict]:
        """
        Get a list of Spines, Leafs and Hosts with their device names and roles
        :return: list of Spines, Leafs and Hosts in dictionary format with their device names and roles
        """
        device_list = []
        unique_entries = set()
        for entry in self.leaf_host_mapping_data:
            leaf_data = {
                'DeviceName': entry['LeafName'],
                'Role': 'leaf',
            }
            if tuple(leaf_data.items()) not in unique_entries:
                unique_entries.add(tuple(leaf_data.items()))
                device_list.append(leaf_data)

        if self.leaf_spine_mapping_data:
            for entry in self.leaf_spine_mapping_data:
                # Add spine data
                spine_data = {
                    'DeviceName': entry['SpineName'],
                    'Role': 'spine',
                }
                if tuple(spine_data.items()) not in unique_entries:
                    unique_entries.add(tuple(spine_data.items()))
                    device_list.append(spine_data)

        host_list = self._get_host_list()
        return device_list + host_list

    def _create_leaf_host_dot_data(self):
        host_p2p_data = [
            {
                'SourceDevice': entry['LeafName'],
                'SourceIntf': entry['LeafIntf'],
                'DstDevice': entry['HostName'],
                'DestIntf': entry['HostIntf']
            }
            for entry in self.leaf_host_mapping_data
        ]
        return host_p2p_data

    def _create_leaf_spine_dot_data(self):
        leaf_spine_dot_data = [
            {
                'SourceDevice': entry['LeafName'],
                'SourceIntf': entry['LeafIntf'],
                'DstDevice': entry['SpineName'],
                'DestIntf': entry['SpineIntf']
            }
            for entry in self.leaf_spine_mapping_data
        ]
        return leaf_spine_dot_data

    def _convert_swp_to_breakout(self, swp):
        """
        Converts a single switch port to a list of breakout ports.

        Args:
            swp (str): a switch port name, e.g. swp1
        Returns:
            list: List of breakout ports (e.g., ["swp1s0", "swp1s1", ...]).
        """
        return [f"{swp}s{i}" for i in range(self.breakout)]

    def create_dot_graph(self, graph_name="topology", write_to_file=True) -> str:
        """
        :param graph_name:
        :param write_to_file:
        :return:
        """
        def create_dot(dataframe) -> str:
            dot_lines = [f'graph {graph_name} {{']
            if self.nvidia_air:
                for device in self.devices:
                    device_name = device['DeviceName']
                    if device['Role'] == 'leaf':
                        dot_lines.append(
                            f'"{device_name}" [function="leaf" memory="2048" os="cumulus-vx-5.6.0" cpu="2" storage="10"]')
                    elif device['Role'] == 'spine':
                        dot_lines.append(
                            f'"{device_name}" [function="spine" memory="2048" os="cumulus-vx-5.6.0" cpu="2" storage="10"]')
            for entry in dataframe:
                source = f'"{entry["SourceDevice"]}":"{entry["SourceIntf"]}"'
                destination = f'"{entry["DstDevice"]}":"{entry["DestIntf"]}"'
                dot_lines.append(f'    {source} -- {destination}')
            dot_lines.append('}')
            dot_graph = "\n".join(dot_lines)
            if write_to_file:
                ansible_dot_file = f"cumulus_ansible/roles/ptm/files/{graph_name}.dot"  # part of ansible script
                self.create_file(ansible_dot_file, dot_graph)
            return dot_graph
        if self.nvidia_air:
            # we do not support creating hosts in NVIDIA AIR, it's not scalable. only leaf/spine will be created
            return create_dot(self.leaf_spine_dot_data)
        else:
            return create_dot(self.dot_data)

    def create_excel(self):
        filename = f"{self.file_dir}/pdg_data.xlsx"
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            devices_df = pd.DataFrame(self.devices)
            devices_df.to_excel(writer, index=False, sheet_name="Device List")

            # Save host port mapping data
            host_df = pd.DataFrame(self.leaf_host_mapping_data)
            host_df.to_excel(writer, index=False, sheet_name="Host Port Mapping")

            # Save leaf-spine port mapping data if it exists
            if self.leaf_spine_mapping_data:
                leaf_spine_df = pd.DataFrame(self.leaf_spine_mapping_data)
                leaf_spine_df.to_excel(writer, index=False, sheet_name="Leaf-Spine Port Mapping")

                bgp_df = pd.DataFrame(self.bgp_global_data)
                bgp_df.to_excel(writer, index=False, sheet_name="BGPGlobal")

                bgp_session_df = pd.DataFrame(self.bgp_session_data)
                bgp_session_df.to_excel(writer, index=False, sheet_name="BGPSession")

                leaf_spine_interface_df = pd.DataFrame(self.leaf_spine_interface_data)
                leaf_spine_interface_df.to_excel(writer, index=False, sheet_name="LeafSpineInterface")

            dot_df = pd.DataFrame(self.dot_data)
            dot_df.to_excel(writer, index=False, sheet_name="dot")

    @staticmethod
    def create_file(filepath, content):
        from pathlib import Path

        # Ensure the directory exists
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content to the file
        file_path.write_text(content)

    def generate_air_script(self):
        data = {
            "leafs": self.leafs,
            "spines": self.spines
        }
        payload = payload_handler.render_jinja(template_name="air_env_setup_template.j2", data=data, folder="bash")
        self.create_file(filepath='nvidia_air/scripts/env_setup.sh', content=payload)

    def generate_ansible_hosts(self):
        spine_data = {
            "spine_prefix": self.spine_prefix,
            "spine_start": ''.join(filter(str.isdigit, self.spines[0]['DeviceName'])),
            "spine_end": ''.join(filter(str.isdigit, self.spines[-1]['DeviceName'])),
        } if self.spines else {}
        leaf_data = {
            "leaf_prefix": self.leaf_prefix,
            "leaf_start": ''.join(filter(str.isdigit, self.leafs[0]['DeviceName'])),
            "leaf_end": ''.join(filter(str.isdigit, self.leafs[-1]['DeviceName'])),
        }
        data = leaf_data | spine_data
        payload = payload_handler.render_jinja(template_name="hosts.j2", data=data,
                                               folder="ansible")

        # Write the updated content to the output file
        self.create_file(f'cumulus_ansible/inventory/hosts', content=payload)


if __name__ == "__main__":
    # from util.parse_excel import ReadExcel
    # excel_data = ReadExcel("scottdc_p2p.xlsx")
    # input_data = {}
    # for sheet_name in excel_data.sheet_names:
    #     if sheet_name == "LeafHostP2P":
    #         input_data["leaf_host_p2p"] = list(excel_data.excel_generate_line(sheet_name=sheet_name))
    #     elif sheet_name == "LeafSpineP2P":
    #         input_data["leaf_spine_p2p"] = list(excel_data.excel_generate_line(sheet_name=sheet_name))
    # mapper = NetworkMapping(input_data=input_data, num_spines=8)

    hosts = int(input("Number of Hosts: "))
    mapper = NetworkMapping(num_hosts=hosts, nvidia_air=True, file_dir="nvidia")
    mapper.generate_air_script()
    mapper.generate_ansible_hosts()
    mapper.create_excel()
    mapper.create_dot_graph()