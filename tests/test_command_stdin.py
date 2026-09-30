# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import sys

from wct import checkRunCommand, checkRunShellCommand, operatingSystem, xAnywhere, xEscape

# A child that reads its stdin to EOF and writes it back, bracketed, as raw
# bytes (so neither side's text-mode newline or codepage handling interferes).
# Every call sets a timeout: if stdin were left open instead of closed, the
# child would wait on it forever, and the check must fail rather than hang.
_ECHO_STDIN = [sys.executable, "-c",
               "import sys; sys.stdout.buffer.write(b'[' + sys.stdin.buffer.read() + b']')"]

checkRunCommand({
    "cmd": _ECHO_STDIN,
    "stdin": "line one\nline two\n",
    "timeout": 30,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("[line one\nline two\n]")),
})

# Text is sent as UTF-8, so localized input round-trips.
checkRunCommand({
    "cmd": _ECHO_STDIN,
    "stdin": "héllo 日本語",
    "timeout": 30,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("[héllo 日本語]")),
})

# bytes are sent as-is.
checkRunCommand({
    "cmd": _ECHO_STDIN,
    "stdin": b"raw bytes",
    "timeout": 30,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("[raw bytes]")),
})

# An empty stdin is valid: the child sees EOF at once.
checkRunCommand({
    "cmd": _ECHO_STDIN,
    "stdin": "",
    "timeout": 30,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("[]")),
})

# stdin applies in shell mode too. `grep` is not on a default Windows
# install, so cmd.exe's builtin `findstr` stands in there.
if operatingSystem() == "Windows" :
    filterCmd = ["findstr", "keep"]
else :
    filterCmd = ["grep", "keep"]
checkRunShellCommand({
    "cmd": filterCmd,
    "stdin": "keep this\ndrop this\n",
    "timeout": 30,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("keep this")),
    "dontexpect_stdout": xAnywhere(xEscape("drop this")),
})
