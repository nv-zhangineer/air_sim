from abc import ABC, abstractmethod
from data_handler.payload_handler import render_jinja
from device_store import DeviceStore
import os

device_store = DeviceStore()


class BaseConfigManager(ABC):
    def __init__(self, rows, file_dir):
        self.rows = rows
        self.file_dir = file_dir
        self.initialized_files = set()  # Set to keep track of initialized files
        self.function_map = {}  # To be defined in subclasses

    @abstractmethod
    def get_template_folder(self):
        """Abstract method to define the template folder for specific vendors."""
        pass

    def create_generic_config(self, sheet_name):
        """
        Applies generic configurations to devices, handling both role-based and non-role-based configurations.
        Role-based meaning a configuration is for a specific device role such as Leaf, or Spine, but not for both
        For DNS, NTP these are applied universally, but for route reflectors, they are for Spine only.
        :param sheet_name: The name of the configuration sheet (e.g., 'NTP').
        """
        rows = list(self.rows)  # Convert generator to list for multiple iterations

        # Determine if the configuration is role-based by checking for role keywords
        target_role = self.extract_role_from_sheet(sheet_name)

        if target_role:
            # Role-based configuration: Filter devices by role
            filtered_devices = [device for device in device_store.device_list if target_role in device.role.lower()]
        else:
            # Non-role-based configuration: Apply to all devices
            filtered_devices = device_store.device_list

        # Apply configurations to the filtered devices
        for device in filtered_devices:
            for row in rows:
                config_payload = str(row.get('Configuration').strip())  # Direct config value
                self.render_and_write_config(
                    config_payload=config_payload,
                    device_name=device.name,
                    extension_prefix=f"01-{sheet_name}".lower(),
                    comment=f"{sheet_name} Configurations"
                )

    @staticmethod
    def extract_role_from_sheet(sheet_name):
        """
        Extracts the device role from the sheet name if it contains a role keyword.

        :param sheet_name: The name of the configuration sheet.
        :return: The role string (e.g., 'spine', 'leaf'), or None if no role is detected.
        """
        for role in ['spine', 'leaf', 'core', 'access']:
            if role in sheet_name.lower():
                return role
        return None  # Return None for non-role-based configurations

    def initialize_file(self, device_name, extension_prefix, comment=""):
        """
        Initialize file with optional comments.
        """
        file_path = f'{self.file_dir}/{device_name}/{device_name}-{extension_prefix}.txt'
        if file_path not in self.initialized_files:
            with open(file_path, 'w') as ouf:
                ouf.write(f"#{comment}\n")
            self.initialized_files.add(file_path)
        return file_path

    def create_config(self, config_type):
        """
        Dynamically execute a configuration creation method based on the function_map.
        """
        if config_type in self.function_map:
            self.function_map[config_type]()
        else:
            raise ValueError(f"Unknown configuration type: {config_type}")

    def render_and_write_config(self, config_payload=None, template_name=None, data=None, device_name=None, extension_prefix=None, comment=None):
        """
        Render the Jinja template and write to the appropriate file.
        If config payload is provided then we don't need Jinja template to crate configuration.
            This is for simple configurations such as the generic configuration
        """
        if not device_name or not extension_prefix:
            raise ValueError("device_name and extension must be provided")

        # Render payload based on whether a template is provided
        if template_name:
            if not data:
                raise ValueError("Data must be provided when using a template")
            payload = render_jinja(template_name=template_name, data=data, folder=self.get_template_folder())
        elif config_payload:
            payload = config_payload
        else:
            raise ValueError("Either config_payload or template_name must be provided")

        # Write to the file
        file_path = self.initialize_file(device_name=device_name, extension_prefix=extension_prefix, comment=comment)
        with open(file_path, 'a') as ouf:
            ouf.write(payload)
            ouf.write('\n')

    def merge_config(self, device_name):
        """
        Merge a list of type-specific (e.g. DNS, NTP..etc.) to a single configuration file
        :param device_name:
        :return:
        """

        device_dir = f'{self.file_dir}/{device_name}'
        if os.listdir(device_dir):
            with open(f'{device_dir}/{device_name}.txt', 'w') as outfile:
                # Iterate over all files in the input directory
                for filename in sorted(os.listdir(device_dir)):
                    # Check if the file is a text file
                    if filename.endswith('.txt') and filename != f"{device_name}.txt":
                        file_path = os.path.join(device_dir, filename)
                        # Open and read the content of the text file
                        with open(file_path, 'r') as infile:
                            lines = infile.readlines()
                            non_empty_lines = [line for line in lines if line.strip() != ""]
                            # Write the content to the output file
                            outfile.writelines(non_empty_lines)
                            outfile.writelines('\n')