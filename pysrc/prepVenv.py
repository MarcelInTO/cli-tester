#!/usr/bin/env python3

# Please follow the establilshed pattern and keep the imports 
# alphabetized (logically, not pedantically)

import argparse
import getpass
import os
import pathlib
import platform
import shutil
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

def amInVenv():
    hasRealPrefix = hasattr(sys, 'real_prefix') 
    hasBasePrefix = hasattr(sys, 'base_prefix') 

    # Magic from the internet - wonky to support different versions of venv
    # and python. Probably overkill since we support only 3.8+
    return (hasRealPrefix or (hasBasePrefix and sys.base_prefix != sys.prefix))


##############################################################################
# Main script
##############################################################################

try:
    # We must not be in the virtual environment to create/update/validate it
    if amInVenv():
        print('ERROR: Cannot "prepare" the execution environment when it is activated')
        os._exit(1)

    envb = venv.EnvBuilder(system_site_packages=False, with_pip=True, upgrade=True, clear=False)
    envb.create(sys.argv[1])
except Exception as e:
    print("ERROR: Prepare command caught exception:")
    print(e)
    print("ERROR: trace:")
    print(traceback.format_exc())
    os._exit(1)
