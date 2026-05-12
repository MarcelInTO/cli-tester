# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A normal pass alongside an xfail block — the test as a whole should be
# reported xfail, not pass, because the block did fire.

from wct import checkPathExists, checkPathNotExists, expectFail

checkPathNotExists("nothing_here.txt")

with expectFail("known bug, issue#999") :
    checkPathExists("definitely_not_here.txt")
