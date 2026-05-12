# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

from wct import checkRunCommand, xAnywhere, xEscape

# Passing a glob that matches no files should exit with code 2 and report
# "No tests matched" on stderr.
checkRunCommand({
    "cmd": ["wct", "/tmp/does_not_exist_anywhere_*.py"],
    "expect_returncode": 2,
    "expect_stderr": xAnywhere(xEscape("No tests matched")),
})
