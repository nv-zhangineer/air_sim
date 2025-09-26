import streamlit as st
import os
import zipfile
from io import BytesIO
from device_store import device_store
from util import parse_excel, diff_file
from data_handler.create_nxos_config import CreateNXOSConfig
from data_handler.merge_config import merge_nxos_config
import sys
import shutil
import uuid
import time
from util.spectrumx_netmapper import NetworkMapping
from nvidia_air.air import Air, QueryAir
import air_sdk

# Streamlit app setup with tabs
tabs = st.tabs(["PDG Generator", "Simulation", "PDG Run", "PDG Template Download", "Instructions"])


def process_sheet(wb, sheet_name, file_dir):
    progress_placeholder = st.empty()
    progress_placeholder.info(f"Processing sheet '{sheet_name}' ")
    sheet_lines = wb.excel_generate_line(sheet_name=sheet_name)
    create_nxos_config = CreateNXOSConfig(sheet_lines, file_dir)
    st.spinner("Generating configuration file....")
    generic_config_sheets = ['GlobalConfig']
    if sheet_name not in generic_config_sheets:
        create_nxos_config.function_map[f'{sheet_name}']()
    else:
        create_nxos_config.function_map[f'{sheet_name}'](f'{sheet_name}')


# Function to create a zip file
def create_zip(output_directory):
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for foldername, _, filenames in os.walk(output_directory):
            for filename in filenames:
                filepath = os.path.join(foldername, filename)
                arcname = os.path.relpath(filepath, output_directory)
                zip_file.write(filepath, arcname)
    zip_buffer.seek(0)
    return zip_buffer


def clean_up_dir(dir_path):
    print("Cleaning up directory", dir_path)
    shutil.rmtree(dir_path)  # Remove the entire directory
    success_message = st.success(f"directory {dir_path} cleaned up successfully")
    time.sleep(3)
    success_message.empty()
    st.session_state.simulation_uploader_key += 1


def copy_directory(source_dir, destination_dir):
    """
    Copies the source directory to the destination.
    If the destination exists, it deletes it before copying.

    :param source_dir: Source directory path
    :param destination_dir: Destination directory path
    """
    try:
        # Check if source exists
        if not os.path.exists(source_dir):
            print(f"Source directory '{source_dir}' does not exist. Aborting copy.")
            return

        # If the destination exists, delete it
        if os.path.exists(destination_dir):
            shutil.rmtree(destination_dir)
            print(f"Deleted existing destination directory: {destination_dir}")

        # Copy the source directory to the destination
        shutil.copytree(source_dir, destination_dir)
        print(f"Copied '{source_dir}' to '{destination_dir}' successfully.")

    except Exception as e:
        print(f"Error during copying: {e}")    #


if "disabled" not in st.session_state:
    st.session_state["disabled"] = True


def flip():
    if st.session_state["disabled"] is True:
        st.session_state["disabled"] = False
        return
    st.session_state["disabled"] = True

@st.fragment
def checkbox_fragment(sheet_names):
    st.write("Sheet names detected:")

    # Render checkboxes with session state
    for sheet in sheet_names:
        if sheet not in st.session_state.checkbox_states:
            st.session_state.checkbox_states[sheet] = True  # Default to selected

        st.session_state.checkbox_states[sheet] = st.checkbox(sheet, value=st.session_state.checkbox_states[sheet])

    # Return selected sheets
    selected_sheets = [sheet for sheet, selected in st.session_state.checkbox_states.items() if selected]
    return selected_sheets


if 'user_id' not in st.session_state:
    st.session_state['user_id'] = str(uuid.uuid4())


# User-specific directory using session-based unique ID

def get_file(filepath):
    try:
        with open(filepath, 'rb') as file:
            return BytesIO(file.read())  # Return the file content as BytesIO
    except FileNotFoundError:
        st.error(f"File {filepath}not found!")
        return None


# Track if a file has been uploaded
if "pdg_run_uploader_key" not in st.session_state:
    st.session_state.pdg_run_uploader_key = 0

if "ip_gen_uploader_key" not in st.session_state:
    st.session_state.ip_gen_uploader_key = 10

if "simulation_uploader_key" not in st.session_state:
    st.session_state.simulation_uploader_key = 20


@st.fragment
def show_download_button(data, label, file_name, mime, on_click, args):
    st.download_button(
        label=label,
        data=data,
        file_name=file_name,
        mime=mime,
        on_click=on_click,
        args=(args,)  # arguments for on_click script
    )


with tabs[0]:
    st.header("Generate PDG Data for Spectrum-X Designs")
    left, middle, right = st.columns(3, vertical_alignment="top")
    dot_file = middle.checkbox(label="Create DOT File", value=True)

    try:
        num_hosts = int(left.text_input("Number of Hosts:", value=64, max_chars=4, placeholder="(1 - 1024 (8K GPUs)"))
    except ValueError:
        st.error("Invalid value, try again")

    if num_hosts <= 32:
        nvidia_air = middle.checkbox(label="For Use with NVIDIA AIR",
                                     label_visibility="visible",
                                     help="1-Tier Air simulation is unsupported, "
                                          "enter a number > 32 to enable NVIDIA Air simualtions",
                                     disabled=True,
                                     value=False)
    else:
        nvidia_air = middle.checkbox(label="For Use with NVIDIA AIR",
                                     label_visibility="visible",
                                     help="When deploying to NVIDIA AIR"
                                          "DOT file will not contain any hosts, breakout will always be 1",
                                     value=True)

    breakout = 1
    if not nvidia_air:
        breakout = right.text_input(label="number of breakouts",
                                    value=2,
                                    disabled=True,
                                    label_visibility="visible",
                                    help="We currently do not support breakout other than 2")

    change_defaults = left.checkbox(label="Change Default Values (Not all values can be adjusted)",
                                    value=False, on_change=flip)

    digit_filler = left.text_input(label="digit filler", value=3, disabled=st.session_state.disabled)
    host_prefix = left.text_input(label="host prefix", value="dgx", disabled=st.session_state.disabled)
    leaf_prefix = left.text_input(label="leaf prefix", value="leaf", disabled=st.session_state.disabled)
    spine_prefix = left.text_input(label="spine prefix", value="spine", disabled=st.session_state.disabled)
    host_p2p_lead_octet = left.text_input(label="point-to-point lead octet for host connections", value=172,
                                          disabled=st.session_state.disabled)
    spine_base_as = left.text_input(label="Base AS for Spines", value=65200, disabled=st.session_state.disabled)
    leaf_base_as = left.text_input(label="Base AS for Leafs", value=65000, disabled=st.session_state.disabled)
    p2pmask = left.text_input(label="Mask for point-to-point connections", value="/31", disabled=True)
    start_id = left.text_input(label="starting digit number", value="0", disabled=True, label_visibility="visible",
                               help="only starting from 0 is supported for now")

    if num_hosts > 0:
        if num_hosts > 1024:
            left.error("Currently the generator only supports up to 1024 hosts")
        if st.button("Generate", key=1):
            cumulus_temp_dir = f"cumulus_{st.session_state['user_id']}"
            os.makedirs(cumulus_temp_dir, exist_ok=True)
            print(f"Creating directory {cumulus_temp_dir}")
            netmapper = NetworkMapping(num_hosts=int(num_hosts),
                                       start_id=int(start_id),
                                       digit_filler=int(digit_filler),
                                       host_prefix=host_prefix,
                                       leaf_prefix=leaf_prefix,
                                       spine_prefix=spine_prefix,
                                       host_p2p_lead_octet=int(host_p2p_lead_octet),
                                       spine_base_as=int(spine_base_as),
                                       leaf_base_as=int(leaf_base_as),
                                       p2pmask=p2pmask,
                                       breakout=breakout,
                                       nvidia_air=nvidia_air,
                                       file_dir=cumulus_temp_dir)
            netmapper.create_excel()

            if nvidia_air:
                netmapper.generate_air_script()
            if dot_file:
                netmapper.create_dot_graph()
            netmapper.generate_ansible_hosts()
            copy_directory(source_dir='cumulus_ansible/', destination_dir=f"{cumulus_temp_dir}/cumulus_ansible/")
            shutil.copy(src='nvidia_air/scripts/env_setup.sh', dst=cumulus_temp_dir)
            shutil.copy(src='cumulus_ansible/roles/ptm/files/topology.dot', dst=cumulus_temp_dir)
            zip_buffer = create_zip(cumulus_temp_dir)
            show_download_button(
                label="Download ZIP",
                data=zip_buffer,
                file_name="cumulus_gen.zip",
                mime="application/zip",
                on_click=clean_up_dir,
                args=cumulus_temp_dir     # arguments for clean_up script
            )
    else:
        left.error("number of hosts must be greater than 0")
# Tab for nvidia air page
with tabs[1]:
    left, middle, right = st.columns(3, vertical_alignment="top")
    username = left.text_input(label="Enter your Air username (email)")
    api_key = left.text_input(label="Enter your Air API Key", type="password")
    sim_title = left.text_input(label="Enter a name for the simulation", value="air simulation")
    uploaded_file = left.file_uploader("Upload DOT File", type=['dot'], key=st.session_state.simulation_uploader_key)
    if uploaded_file is not None and username and api_key:
        st.session_state['dot_file_uploaded'] = True
        from io import StringIO
        stringio = StringIO(uploaded_file.read().decode("utf-8"))
        if left.button("Run"):
            air = Air(username=username, api_key=api_key, dot_file=stringio, title=sim_title)
            with st.status("Creating simulation"):
                air_sim = air.create_simulation()
                time.sleep(5)   # allow for nvidia air to start
            with st.status("Checking the status of the simulation"):
                air_query = QueryAir(username=username, api_key=api_key, title=sim_title)
                while air_query.get_simulation_state() == "NEW":
                    air_query.start_sim()
                    st.info("trying to start simulation.....")
                    st.info(f"current state {air_query.get_simulation_state()}.....")
                    time.sleep(5)

                while air_query.get_simulation_state() != "LOADED":
                    st.info(f"Waiting for state to transition into LOADED before proceeding, "
                            f"current state is {air_query.get_simulation_state()}.....")
                    time.sleep(5)
                st.info("Successfully transitioned state to LOADED")

            with st.status("Enabling SSH service"):
                try:
                    service = air.create_service(simulation=air_sim)
                except air_sdk.AirUnexpectedResponse as air_error:
                    st.error(air_error)
            st.markdown(f"""
            NVIDIA Air environment creation is complete, here is the information you'll need to further configure the environment for ease of access
            1. Make sure you can perform SSH to the management server, you will need to wait for a few minutes before 
            the environment becomes fully operational  
            
            :orange[Wait ro 5 minutes here as NVIDIA Air sets up SSH access with your public key.]
            
            Then try to SSH to the host as follow (assuming that you have already added your public key to your NVIDIA Air account)
            You maybe prompted to update the default password, which is `nvidia`  
            
            `ssh -p {service.src_port} {service.os_default_username}@{service.host}` 
            
            2. Make sure that you have the `cumulus_ansible` and NVIDIA Air `env_setup.sh` scripts ready for transfer  
            below instruction assumes that you are in the directory where those files already exist
            
            3. Once you are able to SSH to the management server, perform the following (:red[**from your local machine**])  
            :orange[`cumulus_ansible` and `nvidia_air` directory must exist first !!]
            ```
            # Copy scripts to the remote server
            scp -P {service.src_port} -r cumulus_ansible {service.os_default_username}@{service.host}:~/
            scp -P {service.src_port} env_setup.sh {service.os_default_username}@{service.host}:~/
            
            # Execute the env_setup.sh scrip
            ssh -p {service.src_port} {service.os_default_username}@{service.host} << EOF
            sudo apt-get install expect -y
            chmod 775 env_setup.sh
            ./env_setup.sh
            sleep 20
            cd cumulus_ansible
            ansible -m ping -i inventory/hosts all
            EOF
            ```
                        
            4. If you'd like, you can run the following Ansible command to perform a PTM run from the server
            ```
            cd ~/cumulus_ansible
            ansible-playbook -i inventory/hosts playbooks/ptm.yml
            
            # To retrieve the final report 
            cat /tmp/ptm_reports/ptmctl_combined_output.txt
            ```
            """)

# PDG Run tab content
with tabs[2]:
    st.header("PDG Run")

    uploaded_file = st.file_uploader("Upload your Excel file", type=['xlsx'], key=st.session_state.pdg_run_uploader_key)

    if uploaded_file is not None:
        st.session_state['pdg_file_uploaded'] = True
        user_dir = f"configurations_{st.session_state['user_id']}"
        os.makedirs(user_dir, exist_ok=True)
        print(f"Creating configuration directory {user_dir}")
        try:
            wb = parse_excel.ReadExcel(uploaded_file)  # sheet dictionary
            device_store.reinitialize(uploaded_file, user_dir)
        except IOError as io_err:
            sys.exit(io_err)
        sheet_names = wb.sheet_names
        # Initialize session state for checkboxes if not already initialized
        if 'checkbox_states' not in st.session_state:
            st.session_state.checkbox_states = {}

        # Handle button clicks and update session state without calling the fragment again
        if st.button("Select All"):
            for sheet in sheet_names:
                st.session_state.checkbox_states[sheet] = True

        if st.button("Deselect All"):
            for sheet in sheet_names:
                st.session_state.checkbox_states[sheet] = False

        # Render checkboxes in the fragment
        selected_sheets = checkbox_fragment(sheet_names)

        # After selecting sheets, "Run" button to call the backend script
        if st.button("Run"):
            for selected_sheet in selected_sheets:
                if selected_sheet not in ['Devices', 'SFP Matrix', 'CableMatrix']:
                    process_sheet(wb=wb, sheet_name=selected_sheet, file_dir=user_dir)
            for device in device_store.devices:
                merge_nxos_config(f'{user_dir}/{device.name}', device.name)

            for device in device_store.devices:
                if device.node_id % 2 != 0:
                    file_diff_dir = f'{user_dir}/config_diffs/'
                    odd_device_name = device_store.get_device_by_id(device.node_id)
                    even_device_name = device_store.get_device_by_id(device.node_id + 1)
                    odd_device_file = f'{user_dir}/{odd_device_name}/{odd_device_name}.txt'
                    even_device_file = f'{user_dir}/{even_device_name}/{even_device_name}.txt'
                    output_file = f'{user_dir}/config_diffs/{odd_device_name}-diff-{even_device_name}'
                    file_diff = diff_file.FileComparer(odd_device_file, even_device_file, output_file)
                    file_diff.compare_files()

            # After running the backend script, present the user with the zip download button
            print("Zipping user directory", user_dir)
            zip_buffer = create_zip(user_dir)
            st.info("Creating zip file")

            st.success("Config files created successfully!")

            # Display the download button
            st.download_button(
                label="Download ZIP",
                data=zip_buffer,
                file_name=f"configuration_files.zip",
                mime="application/zip",
                on_click=clean_up_dir,
                args=(user_dir,)
            )

with tabs[3]:
    # Download button for the Excel template file
    template_file = get_file("pdg_templates/spectrumx_pdg_template.xlsx")
    if template_file:
        st.download_button(
            label="Download Template",
            data=template_file,  # Pass the file content as BytesIO
            file_name="spectrumx_pdg_template.xlsx",  # The name for the downloaded file
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # MIME type for Excel
        )

with tabs[4]:
    st.markdown("""
        
    ### PDG Generator

    Enter the number of DGX hosts to be deployed ( assuming 8 GPUs per host )  
    The following will be automatically created for you in a spreadsheet.  
    1. Device list
    2. BGP global data - used for PDG deployment
    3. BGP session - used for PDG deployment
    4. Leaf and Spine interface configurations for PDG deployment    
    5. Leaf to host port mapping information, including point-to-point IP addresses (we do not use L2 in spectrum-x design)
    6. Leaf to spine port mapping information, everything you'll need to establish a BGP session between leaf and spine
    
    5 and 6 are for informational purposes only, they give you a holistic view of device-to-device connection

    You would then need to take the generated data and merge it with the PDG excel templatized data
    
    ### Filling out the PDG WorkSheets
    - Any :blue[blue cell] header means that the data will not be used in the script, they are mostly notes
    - Any :blue[blue sheet] will :red[not] be used in the script
    - Feel free to add columns to the right as needed, they will not be used in the script.
    - There are notes in some sheets headers for your reference of accepted values

    """)