import os

def merge_nxos_config(file_dir, device_name):
    # Open the output file in write mode
    if os.listdir(file_dir):
        with open(f'{file_dir}/{device_name}.txt', 'w') as outfile:
            # Iterate over all files in the input directory
            for filename in sorted(os.listdir(file_dir)):
                # Check if the file is a text file
                if filename.endswith('.txt') and filename != f"{device_name}.txt":
                    file_path = os.path.join(file_dir, filename)
                    # Open and read the content of the text file
                    with open(file_path, 'r') as infile:
                        lines = infile.readlines()
                        non_empty_lines = [line for line in lines if line.strip() != ""]
                        # Write the content to the output file
                        outfile.writelines(non_empty_lines)
                        outfile.writelines('\n')