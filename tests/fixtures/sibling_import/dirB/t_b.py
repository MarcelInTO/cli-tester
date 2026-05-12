# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

from helpers import TAG
from wct import failTest, passTest

if TAG != "B" :
    failTest(f"dirB test saw TAG={TAG!r}, expected 'B' (sys.modules leak from dirA?)")
passTest(f"dirB imported its own helpers.TAG=={TAG}")
