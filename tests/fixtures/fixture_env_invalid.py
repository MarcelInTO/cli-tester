# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test whose 'env' maps a variable to a non-string. Used as input to a
# meta-test verifying the descriptor is rejected before the command runs.
import sys

from wct import checkRunCommand

checkRunCommand({
    "cmd": [sys.executable, "-c", "pass"],
    "env": {"WCT_META_NUMBER": 5},
    "expect_returncode": 0,
})
