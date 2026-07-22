# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# An out-of-range index into a bare top-level array must be reported as an
# invalid field (clean FAIL), not crash the runner.
import sys

from wct import checkRunCommand

checkRunCommand({
    "cmd": [sys.executable, "-c", "print('[1, 2]')"],
    "expect_returncode": 0,
    "check_json_stdout": [
        {"field": "[5]", "test_type": "valueEqual", "test_value": 1},
    ],
})
