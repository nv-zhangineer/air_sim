import sys
from pydantic import BaseModel, ValidationError
from typing import Literal
import streamlit as st
from data_handler.payload_handler import render_jinja
from device_store import DeviceStore

# Access the already initialized singleton instance
device_store = DeviceStore()


class VPCDomain(BaseModel):
    """
    An example Pydandic class to valid user inputs for vPC domains.
    # TODO add task to validate entries from each spreadsheet
    """
    device_name: str
    domain_id: int
    peer_switch: Literal['enabled', 'disabled']  # Must be 'enabled' or 'disabled'
    peer_gateway: Literal['enabled', 'disabled']  # Must be 'enabled' or 'disabled'
    l3_peer_router: Literal['enabled', 'disabled']  # Must be 'enabled' or 'disabled'
    keepalive_dst: str
    keepalive_src: str
    keepalive_vrf: str
    system_priority: int
    role_priority: int
    delay_restore: int
    auto_recovery_reload_delay: int
    ip_arp_sync: Literal['enabled', 'disabled']  # Must be 'enabled' or 'disabled'


class CreateNXOSConfig(object):
    def __init__(self, rows, file_dir):
        self.rows = rows
        self.file_dir = file_dir
        self.function_map = {
            'NTP': self.create_generic_config,
            'DNS': self.create_generic_config,
            'SNMP': self.create_generic_config,
            'Banner': self.create_banner_config,
            'AAA': self.create_generic_config,
            'Logging': self.create_generic_config,
            'CoreGlobalConfig': self.create_role_specific_global_config,
            'AccessGlobalConfig': self.create_role_specific_global_config,
            'SPAN': self.create_span_config,
            'Alias': self.create_alias_config,
            'OSPFL3Intf': self.create_ospf_l3_intf_config,
            'Loopback': self.create_loopback_config,
            'OSPF': self.create_ospf_config,
            'CoreL2Intf': self.create_core_l2_intf_config,
            'PeerLink': self.create_peer_link_config,
            'VLAN': self.create_vlan_config,
            'KeepAliveLink': self.create_keepalive_config,
            'VPCDom': self.create_vpc_domain_config,
            'AccL2Intf': self.create_access_l2_intf_config,
            'SVI': self.create_svi_config
        }
        self.initialized_files = set()  # Set to keep track of initialized files

    def initialize_file(self, device_name, extension, comment=""):
        """
        initialize file with optional comments at the beginning of the file
        :param device_name: name of the device
        :param extension: file extension added ,
            such as 'svi' for svi config creates myconfig-svi.txt indicates it's for SVI configurations
        :param comment: comment to be added to the starting of each file
        :return: returns the full file path
        """
        file_path = f'{self.file_dir}/{device_name}/{device_name}-{extension}.txt'
        if file_path not in self.initialized_files:
            try:
                with open(file_path, 'w') as ouf:
                    ouf.write(f"!{comment}\n")  # Add the starting line
                self.initialized_files.add(file_path)  # Mark the file as initialized
            except FileNotFoundError:
                st.error(f"Device {device_name} dos not exist in the device list\n{device_store.devices} ")
                sys.exit()
        return file_path

    def create_role_specific_global_config(self, sheet_name):
        """
        Creates NXOS syntax for generic configurations
        All configurations are created on all switches
        Role means the switch role, could be Access, Core, Spine, Leaf...etc.
        The role matching config is to match the sheet tab named Core/Global
        This function needs to be refactored to merge with the "create_generic_config" method
        """
        # self.rows is a generator object, we must convert it to list to loop through it multiple times.
        rows = list(self.rows)
        for device in device_store.devices:
            if device.role.lower() in sheet_name.lower():
                for row in rows:
                    generic_config_data = {
                        'config': str(row.get('Configuration').strip())
                    }
                    payload = render_jinja(template_name='generic_config.j2', data=generic_config_data, folder='nxos')
                    file_path = self.initialize_file(device_name=device.name,
                                                     extension=f"01-{sheet_name}".lower(),
                                                     comment=f"{sheet_name} Configurations")
                    with open(file_path, 'a') as ouf:
                        ouf.write(payload)
                        ouf.write('\n')

    def create_generic_config(self, sheet_name):
        """
        Creates NXOS syntax for generic configurations
        All configurations are created on all switches
        """
        # self.rows is a generator object, we must convert it to list to loop through it multiple times.
        rows = list(self.rows)
        for device in device_store.devices:
            for row in rows:
                generic_config_data = {
                    'config': str(row.get('Configuration').strip())
                }
                payload = render_jinja(template_name='generic_config.j2', data=generic_config_data, folder='nxos')
                file_path = self.initialize_file(device_name=device.name,
                                                 extension=f"02-{sheet_name}".lower(),
                                                 comment=f"{sheet_name} Configurations")
                with open(file_path, 'a') as ouf:
                    ouf.write(payload)
                    ouf.write('\n')

    def create_banner_config(self):
        """
        Creates NXOS syntax for banner configurations
        All configurations are created on all switches
        Banner should have only 1 row, no jinja template is needed
        """
        rows = list(self.rows)
        for device in device_store.devices:
            for row in rows:
                banner_template_content = str(row.get('MOTD')) + "\n!\n" + str(row.get('EXEC'))
                banner_config_data = {
                    'Hostname': device.name,
                    'MgmtIP': device.mgmt_ip,
                    'Model': device.model,
                    'SerialNum': device.serial_num,
                }
                payload = render_jinja(template_content=banner_template_content, data=banner_config_data)
                file_path = self.initialize_file(device_name=device.name,
                                                 extension="03-banner",
                                                 comment="Banner Configurations")
                with open(file_path, 'a') as ouf:
                    ouf.write(payload)
                    ouf.write('\n')

    def create_alias_config(self):
        """
        Creates NXOS syntax for alias configuration
        All aliases are created for all switches
        """
        # self.rows is a generator object, we must convert it to list to loop through it multiple times.
        rows = list(self.rows)
        for device in device_store.devices:
            for row in rows:
                alias_data = {
                    'alias_name': str(row.get('AliasName').strip()),
                    'command': str(row.get('Command').strip())
                }
                payload = render_jinja(template_name='alias.j2', data=alias_data, folder='nxos')
                file_path = self.initialize_file(device_name=device.name,
                                                 extension="04-alias",
                                                 comment="Alias Configurations")
                with open(file_path, 'a') as ouf:
                    ouf.write(payload)
                    ouf.write('\n')

    def create_vlan_config(self):
        """
        Creates NXOS syntax VLAN configurations
        All VLANs are created for all switches
        """
        # self.rows is a generator object, we must convert it to list to loop through it multiple times.
        rows = list(self.rows)
        for device in device_store.devices:
            for row in rows:
                vlan_data = {
                    'vlan_id': int(row.get('VLANId')),
                    'name': str(row.get('Name').strip())
                }
                payload = render_jinja(template_name='vlan.j2', data=vlan_data, folder='nxos')
                file_path = self.initialize_file(device_name=device.name,
                                                 extension="05-vlan",
                                                 comment="VLAN configuration")
                with open(file_path, 'a') as ouf:
                    ouf.write(payload)
                    ouf.write('\n')

    def create_keepalive_config(self):
        """
        Creates NXOS syntax Keepalive Links configuration
        This configuration is only needed if the customer does not use mgmt interface
        """
        for row in self.rows:
            device_name = row.get('DeviceName').strip()
            keepalive_data = {
                'device_name': device_name,
                'interface': row.get('Interface').strip(),
                'description': str(row.get('Description').strip()),
                'lacp_group': row.get('LACPGroup'),
                'vrf': str(row.get('VRF')).strip(),
                'ip_address': row.get('IPAddress')
            }

            if not keepalive_data['interface']:
                print(f"Missing interface data for row {keepalive_data}")
            payload = render_jinja(template_name='keepalive.j2', data=keepalive_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="06-keepalive",
                                             comment="Keepalive Interface Configuration")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_vpc_domain_config(self):
        """
        Creates NXOS syntax VPC Domain configurations
        """
        for row in self.rows:
            device_name = row.get('DeviceName').strip()
            try:
                vpc_domain_data = {
                    'device_name': device_name,
                    'domain_id': int(row.get('DomID')),
                    'peer_switch': str(row.get('PeerSwitch').strip()),  # enabled/disabled
                    'peer_gateway': str(row.get('PeerGateway').strip()),  # enabled/disabled
                    'l3_peer_router': str(row.get('L3PeerRtr').strip()),    # enabled/disabled
                    'keepalive_dst': str(row.get('KeepAliveDst').strip()),
                    'keepalive_src': str(row.get('KeepAliveSrc').strip()),
                    'keepalive_vrf': str(row.get('KeepAliveVRF').strip()),
                    'system_priority': int(row.get('SystemPriority')),
                    'role_priority': int(row.get('RolePriority')),
                    'delay_restore': int(row.get('DelayRestore')),
                    'auto_recovery_reload_delay': int(row.get('AutoRecoveryReloadDelay')),
                    'ip_arp_sync': str(row.get('IPArpSync').strip())
                }
                vpc_domain = VPCDomain(**vpc_domain_data)
                payload = render_jinja(template_name='vpc_domain.j2', data=vpc_domain.dict(), folder='nxos')
                file_path = self.initialize_file(device_name=device_name,
                                                 extension="07-vpc-domain",
                                                 comment="vPC Domain Configurations")
                with open(file_path, 'a') as ouf:
                    ouf.write(payload)
                    ouf.write('\n')
            except ValidationError as e:
                print("Validation error:", e)

    def create_peer_link_config(self):
        """
        Creates NXOS syntax Peer Link configurations
        """
        for row in self.rows:
            device_name = str(row.get('DeviceName').strip())
            peer_link_data = {
                'device_name': device_name,
                'interface': str(row.get('Interface').strip()).lower(),
                'description': str(row.get('Description').strip()),
                'lacp_group': row.get('LACPGroup'),
                'port_mode': str(row.get('PortMode')).strip().lower(),
                'vlans': str(row.get('VLANs')).strip(),
                'vlan_operator': str(row.get('VLANOperator')).strip().lower(),
                'peer_link': str(row.get('PeerLink').strip()).lower(),
            }
            payload = render_jinja(template_name='peer_link.j2', data=peer_link_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="08-peer-link",
                                             comment="Peer Link Configurations")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_svi_config(self):
        """
        Creates NXOS syntax for SVI configurations
        """

        for row in self.rows:
            device_name = row.get('DeviceName').strip()
            svi_data = {
                'device_name': device_name,
                'interface': str(row.get('Interface').strip().lower()),
                'description': str(row.get('Description').strip()),
                'ip_redirects': str(row.get('IPRedirects').lower()),
                'ip_address': row.get('IPAddress'),
                'ospf_process': row.get('OSPFProcess'),
                'ospf_area': row.get('OSPFArea'),
                'hsrp_version': row.get('HSRPVersion'),
                'hsrp_id': row.get('HSRPId'),
                'hsrp_ip': row.get('HSRPIp'),
                'hsrp_md5_auth': row.get('HSRPMD5Auth'),
                'hsrp_preempt_delay_min': row.get('HSRPPreemptDelayMin'),
                'hsrp_priority': row.get('HSRPPriority')
            }
            payload = render_jinja(template_name='svi.j2', data=svi_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="09-svi",
                                             comment="SVI configuration")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_access_l2_intf_config(self):
        """
        Creates NXOS syntax access interface configuration
        """
        for row in self.rows:
            device_name = row.get('DeviceName').strip()
            access_l2_intf_data = {
                'device_name': device_name,
                'interface': str(row.get('Interface').strip().lower()),
                'shutdown': str(row.get('ShutDown').strip().lower()),
                'description': str(row.get('Description').strip()),
                'lacp_group': row.get('LACPGroup'),
                'port_mode': str(row.get('PortMode')).strip().lower(),
                'vlans': str(row.get('VLANs')).strip(),
                'vlan_operator': str(row.get('VLANOperator')).strip().lower(),
                'stp_port_type': row.get('STPPortType'),
                'orphan_port': str(row.get('OrphanPort')).lower(),
                'vpc': str(row.get('VPC')).lower()
            }
            if not access_l2_intf_data['interface']:
                print(f"Missing interface data for row {access_l2_intf_data}")
            payload = render_jinja(template_name='access_l2_intf.j2', data=access_l2_intf_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="10-access-l2-intf",
                                             comment="Access Interface Configuration")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_core_l2_intf_config(self):
        """
        Creates NXOS syntax for L2 configurations between core and access
        """
        for row in self.rows:
            device_name = str(row.get('DeviceName').strip())
            core_l2_intf_data = {
                'device_name': device_name,
                'interface': str(row.get('Interface').strip()).lower(),
                'description': str(row.get('Description').strip()),
                'lacp_group': row.get('LACPGroup'),
                'port_mode': str(row.get('PortMode')).strip().lower(),
                'vlans': str(row.get('VLANs')).strip(),
                'vlan_operator': str(row.get('VLANOperator')).strip().lower(),
                'stp_guard': str(row.get('STPGuard').strip()).lower(),
                'stp_port_type': str(row.get('STPPortType').strip()).lower(),
                'vpc': str(row.get('VPC').strip()).lower()
            }
            payload = render_jinja(template_name='core_l2_intf.j2', data=core_l2_intf_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="11-core-to-access-l2-interface",
                                             comment="Core To Access L2 Interface Configurations")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_ospf_config(self):
        """
        Creates NXOS syntax for OSPF configurations
        """
        for row in self.rows:
            device_name = str(row.get('DeviceName').strip())
            ospf_data = {
                'device_name': device_name,
                'process_id': int(row.get('ProcessID')),
                'router_id': str(row.get('RouterID').strip()),
                'log_adjacency': str(row.get('LogAdjacency').strip().lower()),
                'passive_default': str(row.get('PassiveDefault')).strip().lower(),
                'bfd': str(row.get('BFD')).strip()
            }
            payload = render_jinja(template_name='ospf.j2', data=ospf_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="12-ospf",
                                             comment="OSPF Configurations")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_loopback_config(self):
        """
        Creates NXOS syntax for Loopback configurations
        """
        for row in self.rows:
            device_name = str(row.get('DeviceName').strip())
            loopback_data = {
                'device_name': device_name,
                'interface': str(row.get('Interface').strip().lower()),
                'vrf': str(row.get('VRF').strip()),
                'description': str(row.get('Description').strip()),
                'ip_address': row.get('IPAddress'),
                'ospf_process': row.get('OSPFProcess'),
                'ospf_area': row.get('OSPFArea')
            }
            payload = render_jinja(template_name='loopback.j2', data=loopback_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="13-loopback",
                                             comment="Loopback Interface Configurations")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_ospf_l3_intf_config(self):
        """
        Creates NXOS syntax for L3 routing interfaces on core router
        """
        for row in self.rows:
            device_name = str(row.get('DeviceName').strip())
            ospf_l3_intf_data = {
                'device_name': device_name,
                'interface': str(row.get('Interface').strip().lower()),
                'description': str(row.get('Description').strip()),
                'lacp_group': row.get('LACPGroup'),
                'vrf': str(row.get('VRF').strip()),
                'ip_redirects': str(row.get('IPRedirects').lower()),
                'ip_address': row.get('IPAddress'),
                'ospf_process': row.get('OSPFProcess'),
                'ospf_area': row.get('OSPFArea'),
                'ospf_network_type': row.get('ospf_network_type'),
                'ospf_passive_interface': row.get('OSPFPassiveInterface'),
                'ospf_auth': row.get('OSPFAuth'),
                'auth_key_id': row.get('AuthKeyID'),
                'encryption_type': row.get('EncryptionType'),
                'encryption_key': row.get('EncryptionKey'),
                'mtu': row.get('MTU'),
                'bfd': row.get('BFD')
            }
            payload = render_jinja(template_name='ospf_l3_intf.j2', data=ospf_l3_intf_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="14-ospf-l3-interface",
                                             comment="OSPF L3 interface configurations")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')

    def create_span_config(self):
        """
        Creates NXOS syntax for SPAN configurations
        """
        for row in self.rows:
            device_name = str(row.get('DeviceName').strip())
            span_data = {
                'device_name': device_name,
                'session_id': row.get('SessionID'),
                'description': str(row.get('Description').strip()),
                'src_interface': str(row.get('SrcIntf').strip()).lower(),
                'src_vlan': row.get('SrcVLAN'),
                'direction': str(row.get('Direction').strip()),
                'dst_interface': str(row.get('DstIntf').strip()).lower()
            }
            payload = render_jinja(template_name='span.j2', data=span_data, folder='nxos')
            file_path = self.initialize_file(device_name=device_name,
                                             extension="15-span",
                                             comment="SPAN Session Configurations")
            with open(file_path, 'a') as ouf:
                ouf.write(payload)
                ouf.write('\n')
