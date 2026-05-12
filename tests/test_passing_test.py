# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# A passing fixture should yield exit code 0 and a "1/1 passed" summary.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_passes.py")],
    "expect_returncode": 0,
    "expect_stdout": [
        xAnywhere(xEscape("PASS")),
        xAnywhere(xEscape("1/1 passed")),
    ],
})
