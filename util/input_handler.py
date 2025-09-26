#! /usr/bin/env python3
"""
     Copyright (c) 2018 World Wide Technology, Inc.
     All rights reserved.
     author:
        Peter Zhang     zhangp@wwt.com
"""

import argparse
import logging
import os
import datetime
import shutil
import sys

# check input for node ID

def select_sheet(input_list):
    print("loaded the following sheets:\n")
    for count, sheet_name in enumerate(input_list, 1):
        print ('{}: {}'.format(count, str(sheet_name)))
    else:
        pass
    print('99: Atomic (Process all tabs and combine them into a single JSON file)')

    while True:
        try:
            # convert to "input" in python 3
            user_input = int(input("\nwhich one would you like to process? '0' to exit:  "),10)
            if 0 < user_input <= len(input_list) or user_input == 99:
                return user_input
            if user_input == 0:
                return 0
            else:
                print ("selection must be within 0 - {}".format(len(input_list)))
        except (NameError, SyntaxError, ValueError):
            print ("you must input a number")


def get_user_input():
    parser = argparse.ArgumentParser(
        description='ACI Tenant Policy JSON Configuration builder.'
    )

    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING
    )
    parser.add_argument(
        '-F', '--file',
        help='Input file',
        required=True
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO
    )
    args = parser.parse_args()
    return args


def setup_directory(file, target):
    # Get Date and Time for LogFile
    this_date = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M')
    # log file will be stored in current directory with script
    script_dir = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..'))


    if sys.platform == "win32":
        separator = "\\"
    else:
        separator = "/"


    log_path = separator.join([script_dir,target,"log"])
    log_file = separator.join([log_path,this_date+".json"])
    json_path = separator.join([script_dir,target,"json"])
    relative_json_path = separator.join([target,"json"])
    if not os.path.isdir(json_path):
        os.mkdir(json_path)
    else:
        print("*"*10,f"Files detected under {relative_json_path}, removing directory and recreating...","*"*10,"\n")
        shutil.rmtree(json_path)
        os.mkdir(json_path)

    try:
        logging.basicConfig(
            filename=log_file,
            filemode='w',
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M'
        )
    except IOError as e:
        print("Directory log/ not found")
        os.mkdir(log_path)
        print(log_path + 'created successfully')

    logging.info("Start of Script")

    logging.debug(f"Input Filename : {file}")

    file_dir = json_path + separator
    return file_dir