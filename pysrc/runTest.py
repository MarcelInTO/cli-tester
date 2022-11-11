#!/usr/bin/env python3

# Please follow the establilshed pattern and keep the imports 
# alphabetized (logically, not pedantically)

import argparse
import getpass
import os
import pathlib
import platform
import requests
import shutil
import subprocess
import sys
import time
import traceback
import venv

from pathlib import Path


# Setting the interpreter up above does not force the correct version
# of python if the user invoked the script with a specific version of
# python on the command line. So we check here
if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 8):
    print("Fatal Error: Python 3.8 or a more recent version is required.")
    os._exit(1)


##############################################################################
# Helper functions
##############################################################################

def printPhase(str):
    print(f"{str}")

def printStatus(str):
    if g_verbose:
        print(f"    Status: {str}")

def printError(str):
    print(f"ERROR: {str}")

def doProcessInputArgs():
    global g_args
    global g_providedPassword
    global g_providedUser
    global g_testname
    global g_verbose

    parser = argparse.ArgumentParser(description='Automated tests for WVS CLI')
    parser.add_argument('workroot',  type=str, nargs=1, help='Workspace folder')
    parser.add_argument('testname',  type=str, nargs=1, help='Test(s) to run')
    parser.add_argument('--password', type=str, help='Password')
    parser.add_argument('--user', type=str, help='User')
    parser.add_argument('--verbose', action='store_true')

    g_args = parser.parse_args()

    # For now we just assume this is valid and does not have cruft in it,
    # but we really should validate
    g_workRoot = g_args.workroot
    g_verbose = g_args.verbose

    # validate that the optional arguments are appropriate to the command
    g_testname = g_args.testname[0]

    # Password and user are optional but if we have provided a password, we must
    # have also provided a user
    if g_args.password is not None and g_args.user is None:
        print("ERROR: --password can only be used if --user is used as well")
        os._exit(1)
    g_providedUser = g_args.user
    g_providedPassword = g_args.password

"""     # Print out the configuration - its useful 
    printPhase("Starting test runner...")
    printStatus("Configuration")
    printStatus(f"    Tworkroot: {g_workRoot}")
    printStatus(f"    testname: {g_testname}")
    printStatus(f"    user: {g_providedUser}")
    printStatus(f"    password: {g_providedPassword}")
 """

##############################################################################
# Main script
##############################################################################

# globals we use
g_args = None
g_providedPassword = None
g_providedUser = None
g_testname = None
g_workRoot = None
g_verbose = False


# Process input arguments - output is g_args
doProcessInputArgs()

# run the appropirate test

printPhase(f"Running test '{g_args.testname[0]}'.")

incfile = g_args.testname[0]
returnLocals = {}
exec(compile(open(incfile, "rb").read(), incfile, 'exec'), None, returnLocals)

# prepare()
# run()
# clean()


