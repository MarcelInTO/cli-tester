# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Whole-test xfail: a check fails after expectTestFails was declared, so
# wct should report XFAIL and exit 0.

from wct import checkPathExists, expectTestFails

expectTestFails("whole-test known bug, issue#999")

checkPathExists("definitely_not_here.txt")
