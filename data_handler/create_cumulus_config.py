import sys
import os
from pydantic import BaseModel, ValidationError
from typing import Literal

from device_store import DeviceStore
from data_handler.base_config_creator import BaseConfigManager

# Access the already initialized singleton instance
device_store = DeviceStore()


class CreateCumulusConfig(BaseConfigManager):
    def __init__(self, rows, file_dir):
        super().__init__(rows, file_dir)
        self.function_map = {
            'NTP': lambda sheet: self.create_generic_config(sheet),
            'DNS': lambda sheet: self.create_generic_config(sheet),
            # 'Banner': lambda: self.create_banner_config('PreLogin', 'PostLogin'),
            'LeafSpineInterface': self.create_leaf_spine_interface_config,
            'BGPGlobal': self.create_bgp_global_config,
            'BGPSession': self.create_bgp_session_config,
        }

    def get_template_folder(self):
        return 'cumulus'

    def create_system_config(self):
        pass

    def create_leaf_spine_interface_config(self):
        """
        Creates Cumulus syntax for leaf/spine L3 interface configurations.
        """
        for row in self.rows:
            data = {
                'device_name': row.get('DeviceName').strip(),
                'interface': row.get('Interface').strip().lower(),
                'interface_ip': row.get('InterfaceIP').strip(),
                'mask': row.get('Mask').strip()
            }
            self.render_and_write_config(
                template_name='leaf_spine_interface.j2',
                data=data,
                device_name=data['device_name'],
                extension_prefix='l3_interface',
                comment='Leaf to Spine interface configuration'
            )

    def create_bgp_session_config(self):
        """
        Creates Cumulus syntax for BGP session configurations.
        """
        for row in self.rows:
            data = {
                'device_name': row.get('DeviceName').strip(),
                'vrf': row.get('VRF').strip().lower(),
                'bgp_neighbor': row.get('NeighborIP').strip(),
                'remote_as': int(row.get('RemoteAS')),
            }
            self.render_and_write_config(
                template_name='bgp_session.j2',
                data=data,
                device_name=data['device_name'],
                extension_prefix='bgp_session',
                comment='BGP session and neighbor configuration between leaf/spine'
            )

    def create_bgp_global_config(self):
        """
        Creates Cumulus syntax CLI for BGP global configurations per device
        We'll also create the loopback, and advertise it as part of the configuration.
        The configuration Syntax is as follows:
            nv set interface lo ip address 10.0.0.0/32
            nv set interface lo type loopback
            nv set router bgp autonomous-system 65000
            nv set router bgp enable on
            nv set router bgp router-id 10.0.0.0
            nv set vrf default router bgp address-family ipv4-unicast enable on
            nv set vrf default router bgp address-family ipv4-unicast network 10.0.0.0/32
        """
        for row in self.rows:
            data = {
                'device_name': row.get('DeviceName').strip(),
                'vrf': row.get('VRF').strip().lower(),
                'local_as': int(row.get('AS')),
                'router_id': row.get('RouterID').strip(),
                'loopback_ip': row.get('LoopbackIP').strip()
            }
            self.render_and_write_config(
                template_name='bgp_global.j2',
                data=data,
                device_name=data['device_name'],
                extension_prefix='bgp_global',
                comment='BGP global configuration'
            )


if __name__ == "__main__":
    from util.parse_excel import ReadExcel
    excel_file = "pdg_templates/spectrumx_pdg_template.xlsx"
    data_frame = ReadExcel(excel_file)
    device_store.reinitialize(excel_file, "cumulus_config")
    #
    for sheet in ["BGPGlobal", "LeafSpineInterface", "BGPSession"]:
        print ("Processing Sheet....", sheet)
        rows = data_frame.excel_generate_line(sheet)
        cumulus_config = CreateCumulusConfig(rows, 'cumulus_config')
        cumulus_config.create_config(sheet)

    for device in device_store.device_list:
        cumulus_config.merge_config(device.name)