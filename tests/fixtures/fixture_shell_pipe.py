# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Exercises checkRunShellCommand with a real shell feature (pipe).
# Verifies the bug fix that joins the cmd list when shell=True.
#
# `grep` is not on a default Windows install, so we use cmd.exe's builtin
# `findstr` there. The point is to exercise a shell pipe end-to-end; the
# specific filter tool doesn't matter.
from wct import checkRunShellCommand, operatingSystem, xAnywhere, xEscape

if operatingSystem() == "Windows" :
    cmd = ["echo", "alpha beta gamma", "|", "findstr", "beta"]
else :
    cmd = ["echo", "alpha beta gamma", "|", "grep", "beta"]

checkRunShellCommand({
    "cmd": cmd,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("beta")),
})
