# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Bare top-level JSON arrays are addressable: "" is the root value itself,
# "[N]" indexes into it (negative indexes allowed), and index chains like
# "[2][1]" work at any depth.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_json_root_array.py")],
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("1/1 passed")),
})

# An out-of-range root index fails cleanly as an invalid field — no traceback.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_json_root_array_bad_index.py")],
    "expect_returncode": 1,
    "expect_stdout": xAnywhere(xEscape("invalid field name '[5]'")),
    "dontexpect_stdout": xAnywhere(xEscape("Traceback")),
    "dontexpect_stderr": xAnywhere(xEscape("Traceback")),
})
