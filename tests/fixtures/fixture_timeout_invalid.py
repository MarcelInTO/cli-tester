# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test with an invalid (non-positive) per-command timeout. Used as input
# to a meta-test verifying the descriptor is rejected up front rather than
# passed through to subprocess.
from wct import checkRunCommand

checkRunCommand({
    "cmd": ["wct", "--version"],
    "timeout": -5,
    "expect_returncode": 0,
})
