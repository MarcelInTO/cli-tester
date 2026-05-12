# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A real failure outside any xfail block must still fail the suite, even if
# a passing xfail block existed earlier.

from wct import checkPathExists, expectFail

with expectFail("known bug, issue#999") :
    checkPathExists("definitely_not_here.txt")

# This one really fails — no xfail context.
checkPathExists("also_not_here.txt")
