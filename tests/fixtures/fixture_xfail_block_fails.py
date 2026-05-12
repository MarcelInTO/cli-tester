# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A fixture used by the xfail meta-test: a check inside expectFail fails as
# expected, so wct should report XFAIL and exit 0.

from wct import checkPathExists, expectFail

with expectFail("known bug, tracked in issue#999") :
    checkPathExists("definitely_not_here.txt")
