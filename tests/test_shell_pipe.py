# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# checkRunShellCommand with a pipe should work end-to-end. Guards the bug
# fix that joins the cmd list before passing to subprocess with shell=True.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_shell_pipe.py")],
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("1/1 passed")),
})
