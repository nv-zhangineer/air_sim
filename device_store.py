import os
import openpyxl
from typing import List, Optional
from ipaddress import IPv4Interface
from pydantic import BaseModel, Field, field_validator
import streamlit as st
import sys

# Device class to hold device attributes

class Device(BaseModel):
    name: str = Field(default=..., description="The name of the device")
    role: str = Field(default=..., description="The role of the device")
    make: Optional[str] = Field(default=None, description="The make of the device")
    model: Optional[str] = Field(default=None, description="The model of the device")
    serial_num: Optional[str] = Field(default=None, description="The serial number of the device")
    mgmt_ip: IPv4Interface = Field(default=..., description="The management IP address of the device")
    node_id: int = Field(default=..., description="The node ID of the device")

    def __repr__(self):
        return (f"Device(name={self.name}, role={self.role}, make={self.make}, model={self.model}, "
                f"serial_num={self.serial_num}, mgmt_ip={self.mgmt_ip}, node_id={self.node_id})")


class DeviceStore:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DeviceStore, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):  # Ensure initialization happens only once
            self.devices: List[Device] = []  # List to store Device objects
            self.excel_file = None
            self.output_directory = None
            self.initialized = True

    def reinitialize(self, excel_file=None, output_directory=None):
        """
        Reinitialize the DeviceStore with new excel_file and output_directory.
        This method should be called from main.py after user input is received.
        """
        self.excel_file = excel_file
        self.output_directory = output_directory
        if self.excel_file and self.output_directory:
            self.devices = self._read_devices_from_excel()
            self._initialize_directory(output_directory)

    def get_device_by_id(self, device_id):
        # Find the device by ID from the list of devices
        for device in self.devices:
            if device.node_id == device_id:
                return device.name
        return None

    def _read_devices_from_excel(self):
        try:
            # Load the workbook and select the 'Devices' sheet
            workbook = openpyxl.load_workbook(self.excel_file)
            sheet = workbook['Devices']
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
            sys.exit(1)

        devices = []
        headers = [cell.value for cell in sheet[1]]  # Get headers from the first row
        for row in sheet.iter_rows(min_row=2, values_only=True):
            row_data = dict(zip(headers, row))  # Create a dictionary for each row
            if row_data.get('Role'):
                mgmt_ip = row_data.get('MgmtIP')
                try:
                    mgmt_ip = IPv4Interface(mgmt_ip)
                except ValueError as e:
                    st.error(f"{e}\nIP address value error: {mgmt_ip} does not appear to be a valid IPv4 address")
                device = Device(
                    name=row_data.get('DeviceName').strip(),
                    role=row_data.get('Role', '').strip(),
                    make=row_data.get('Make', '').strip() if row_data.get('Make') else None,
                    model=row_data.get('Model', '').strip() if row_data.get('Model') else None,
                    serial_num=row_data.get('SerialNum').strip(),
                    mgmt_ip=IPv4Interface(row_data.get('MgmtIP')),
                    node_id=row_data.get('NodeID')
                )
                devices.append(device)
        return devices

    def _initialize_directory(self, output_directory):
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        config_diff_dir = os.path.join(output_directory, "config_diffs")
        if not os.path.exists(config_diff_dir):
            os.makedirs(config_diff_dir)
        for device in self.devices:
            device_dir = os.path.join(output_directory, device.name)
            if not os.path.exists(device_dir):
                os.makedirs(device_dir)


# Singleton instance of DeviceStore
device_store = DeviceStore()
