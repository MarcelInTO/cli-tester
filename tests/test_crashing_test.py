# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# A fixture that raises an unhandled exception should be caught by the
# runner and reported as 'errored' (not as a passing test, not as a runner
# crash). Exit code should still be non-zero.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_crashes.py")],
    "expect_returncode": 1,
    "expect_stderr": xAnywhere(xEscape("ERROR: test raised an unexpected exception")),
    "expect_stdout": xAnywhere(xEscape("1 errored")),
})
