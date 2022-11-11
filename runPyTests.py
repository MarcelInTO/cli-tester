#!/usr/bin/env python3

# Please follow the establilshed pattern and keep the imports 
# alphabetized (logically, not pedantically)

import argparse
import glob
import os
import platform
import shutil
import stat
import subprocess
import sys

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
    global g_testnames
    global g_verbose

    theHelpDescription = """
Automated black box testing for CLI programs. The current implementation
does not support testing of programs that require interactive input. The
glob patterns supported by the 'testname' argument are like those 
supported by rails and golang in that '**' will match files any files
and subdirectories.
    """

    parser = argparse.ArgumentParser(description=theHelpDescription)
    parser.add_argument('testname',  type=str, nargs='+', help='path to test; can be a glob pattern')
    parser.add_argument('-v', '--verbose', action='store_true', help='show more status messages while executing')
    g_args = parser.parse_args()

    # For now we just assume this is valid and does not have cruft in it,
    # but we really should validate
    g_testnames = g_args.testname
    g_verbose = g_args.verbose

    # Print out the configuration - its useful 
    printPhase("Starting bootstrapper...")
    printStatus("Configuration")
    printStatus(f"    workroot: {g_workRoot}")
    printStatus(f"    testnames: {g_testnames}")
 
def funcDeleteRw(action, name, exc) :
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)

##############################################################################
# Main script
##############################################################################

# globals we use
g_workRoot = Path().home().joinpath(".wvsRunPyTests")
g_venvPath = g_workRoot.joinpath("venv")
g_runTestRoot = g_workRoot.joinpath("runroot")

g_args = None
g_testname = None
g_verbose = False

# Has to be done first because the verbose flag controls what is printed
# in subsequent steps.
doProcessInputArgs()

printPhase("Preparing for running tests...")

# In verbose mod print out the configuration - its useful 
printStatus("Configuration")
printStatus(f"    Test runner work directory: {g_workRoot}")
printStatus(f"    Individual test workspace: {g_runTestRoot}")

# Create a python vritual environment to run in. Don't want to
# mess with the user's global python environment if we install things.
printStatus("Creating python virtual environment")
cmd = f"{sys.executable} pysrc/prepVenv.py {g_venvPath}"
subprocess.run(cmd.split())

# Get the correct python executable path for the platform
if platform.system() == "Windows":
    pPath = str(g_venvPath.joinpath("Scripts/python"))
elif platform.system() == "Linux":
    pPath = str(g_venvPath.joinpath("bin/python"))
else:
    printError(f"Unsupported platform '{platform.system()}'")
    os._exit(3)

# In the virtual environment, makes sure pip is current
printStatus("Checking for python upgrades")
cmd = f"{pPath} -m pip -q install --upgrade pip"
subprocess.run(cmd.split())

# In the virtual environment, makes sure requirements are up to date
printStatus("Checking for venv python prerequisites")
cmd = f"{pPath} -m pip -q install -r pysrc/requirements.txt"
subprocess.run(cmd.split())

# in the virtual environment run test tester
printStatus("Starting Test Runner")

# We Break down the input test names into individual tests here so that we can invoke
# the test runner with one test at a time and provide a clean workspace foldeer to
# it. That way the test runner does not have to know about where workspace folders
# are, whether they are deleted or retained, etc. All that configuration management
# is done here and the runner only worries about running the test.
for pat in g_testnames :
    vg = glob.glob(pat)
    for v in vg :
        # Purge any previous work data. Right now we are reusing the same directory
        # as the clean workspace for each test. In a future state, we might provide
        # a new directory for each test and retain those directories for some period
        # of time so that data can be left behind by the tests.
        printStatus("Cleaning workspace")
        if os.path.exists(g_runTestRoot) :
            if os.path.isdir(g_runTestRoot) :
                shutil.rmtree(g_runTestRoot, onerror=funcDeleteRw)
            else:
                printError(f"'{g_runTestRoot}' exists but is not a directory")
                os._exit(7)
        os.makedirs(g_runTestRoot)

        if g_verbose:
            vstring = "--verbose"
        else:
            vstring = ""

        cmd = f"{pPath} {os.path.abspath('pysrc/runTest.py')} {g_runTestRoot} {os.path.abspath(v)}  {vstring}"
        subprocess.run(cmd.split(), cwd=g_runTestRoot)

        # The tests change working directories, so before we can clean anything for
        # the next test, we have to get out of the directory we will clean
        #os.chdir(Path("g_runTestRoot").joinpath(".."))



