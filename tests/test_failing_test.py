# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# A failing fixture should exit with code 1, print a FAIL line, and the
# summary should mention "1 failed".
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_fails.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("FAIL")),
        xAnywhere(xEscape("1 failed")),
    ],
})
