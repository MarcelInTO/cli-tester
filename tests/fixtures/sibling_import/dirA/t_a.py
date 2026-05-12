# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

from helpers import TAG
from wct import failTest, passTest

if TAG != "A" :
    failTest(f"dirA test saw TAG={TAG!r}, expected 'A' (sys.modules leak from another dir?)")
passTest(f"dirA imported its own helpers.TAG=={TAG}")
