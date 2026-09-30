# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Relies on setup-each's marker, then leaves the cwd somewhere else to check
# that teardown-each still runs in the workspace.
import os

from wct import checkPathExists, passTest

checkPathExists("marker.txt")
passTest("test body ran")
os.mkdir("elsewhere")
os.chdir("elsewhere")
