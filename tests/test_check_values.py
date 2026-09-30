# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkEqual, checkRunCommand, checkTrue, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Passing checks on Python values must not stop the test.
checkTrue(2 + 2 == 4, "checkTrue passes on a true condition")
checkEqual([1, 2], [1, 2], "checkEqual passes on equal values")

# A failing checkTrue fails the test with its message.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_check_true_fails.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("FAIL: (arithmetic still works)")),
        xAnywhere(xEscape("0/1 passed")),
    ],
})

# A failing checkEqual also shows both values, using their repr so that 5
# and "0" are told apart from 5 and 0.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_check_equal_fails.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("FAIL: (ETA is zero [got 5, expected '0'])")),
        xAnywhere(xEscape("0/1 passed")),
    ],
})
