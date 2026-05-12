# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Exercises check_json_stdout against a command whose stdout is plain text,
# not JSON. The runner should report a clean FAIL rather than crashing with
# JSONDecodeError.
#
# We use `python -c "print(...)"` rather than `echo` so the fixture works on
# Windows too, where `echo` is a cmd.exe builtin (not a standalone executable
# that shutil.which can find).
import sys

from wct import checkRunCommand

checkRunCommand({
    "cmd": [sys.executable, "-c", "print('this is not json')"],
    "expect_returncode": 0,
    "check_json_stdout": [
        {"field": "anything", "test_type": "valueEqual", "test_value": "x"},
    ],
})
