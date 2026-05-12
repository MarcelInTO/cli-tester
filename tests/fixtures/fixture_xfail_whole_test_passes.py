# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Whole-test xfail: every check passes despite expectTestFails. wct should
# report XPASS and exit 1.

from wct import checkPathNotExists, expectTestFails

expectTestFails("whole-test marker that is now stale, issue#999")

checkPathNotExists("nothing_here.txt")
