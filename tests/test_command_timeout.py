# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os
import sys

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Per-command timeout: a hung command must be killed and reported as a failed
# check (non-zero exit, "timed out" diagnostic), not stall the suite.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_timeout_percommand.py")],
    "expect_returncode": 1,
    "expect_stdout": [xAnywhere(xEscape("timed out")), xAnywhere(xEscape("0/1 passed"))],
})

# Suite-wide --timeout flag: the same hang, no per-command timeout set, must be
# killed by the CLI-level default instead.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_timeout_default.py"), "--timeout", "1"],
    "expect_returncode": 1,
    "expect_stdout": [xAnywhere(xEscape("timed out")), xAnywhere(xEscape("0/1 passed"))],
})

# A command that finishes well within its timeout must still pass — the timeout
# machinery must not disturb the normal path.
checkRunCommand({
    "cmd": [sys.executable, "-c", "print('quick')"],
    "timeout": 30,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("quick")),
})

# An invalid timeout (not a positive number) must be rejected up front as a
# malformed descriptor, before the command runs.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_timeout_invalid.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("must be a positive number of seconds")),
        xAnywhere(xEscape("invalid test command descriptor")),
    ],
})
