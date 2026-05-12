# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A fixture used by the xfail meta-test: every check inside expectFail
# passes, so wct should report XPASS and exit 1.

from wct import checkPathNotExists, expectFail

with expectFail("supposedly-broken validation, issue#999") :
    checkPathNotExists("nothing_here.txt")
