# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os
import stat
import sys

from wct import (
    checkEqual,
    checkRunCommand,
    checkRunShellCommand,
    checkTrue,
    operatingSystem,
    xAnywhere,
    xEscape,
    xFullLine,
)

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _printVars(*names) :
    """A child that prints NAME=value for each named variable, or NAME=<unset>."""
    code = "import os, sys; [print(n + '=' + os.environ.get(n, '<unset>')) for n in sys.argv[1:]]"
    return [sys.executable, "-c", code, *names]


def _line(text) :
    return xFullLine(xEscape(text))


# Setting a variable reaches the child, and does not touch the runner's own
# environment or leak into the next command.
checkRunCommand({
    "cmd": _printVars("WCT_META_SET"),
    "env": {"WCT_META_SET": "set-value"},
    "expect_returncode": 0,
    "expect_stdout": _line("WCT_META_SET=set-value"),
})
checkTrue("WCT_META_SET" not in os.environ, "env did not leak into the runner's environment")
checkRunCommand({
    "cmd": _printVars("WCT_META_SET"),
    "expect_returncode": 0,
    "expect_stdout": _line("WCT_META_SET=<unset>"),
})

# Overriding and removing inherited variables (the case of a suite that
# exports variables one command must run without). Removing a variable that
# is not set at all is not an error.
os.environ["WCT_META_OVERRIDE"] = "inherited"
os.environ["WCT_META_REMOVE"] = "inherited"
checkRunCommand({
    "cmd": _printVars("WCT_META_OVERRIDE", "WCT_META_REMOVE", "WCT_META_NEVER_SET"),
    "env": {"WCT_META_OVERRIDE": "overridden", "WCT_META_REMOVE": None, "WCT_META_NEVER_SET": None},
    "expect_returncode": 0,
    "expect_stdout": [
        _line("WCT_META_OVERRIDE=overridden"),
        _line("WCT_META_REMOVE=<unset>"),
        _line("WCT_META_NEVER_SET=<unset>"),
    ],
})
checkEqual(os.environ.get("WCT_META_OVERRIDE"), "inherited", "override left the runner's value alone")
checkEqual(os.environ.get("WCT_META_REMOVE"), "inherited", "removal left the runner's value alone")
checkRunCommand({
    "cmd": _printVars("WCT_META_OVERRIDE", "WCT_META_REMOVE"),
    "expect_returncode": 0,
    "expect_stdout": [_line("WCT_META_OVERRIDE=inherited"), _line("WCT_META_REMOVE=inherited")],
})

# An empty env is accepted and inherits everything.
checkRunCommand({
    "cmd": _printVars("WCT_META_OVERRIDE"),
    "env": {},
    "expect_returncode": 0,
    "expect_stdout": _line("WCT_META_OVERRIDE=inherited"),
})
del os.environ["WCT_META_OVERRIDE"]
del os.environ["WCT_META_REMOVE"]

# env applies in shell mode too.
if operatingSystem() == "Windows" :
    shellCmd = ["echo", "%WCT_META_SHELL%"]
else :
    shellCmd = ["echo", "$WCT_META_SHELL"]
checkRunShellCommand({
    "cmd": shellCmd,
    "env": {"WCT_META_SHELL": "via-shell"},
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("via-shell")),
})

# On POSIX the executable is looked up on the child's PATH, so an env that
# puts a directory on PATH makes a tool there runnable. (CreateProcess on
# Windows searches the runner's own PATH instead, so this does not apply.)
if operatingSystem() != "Windows" :
    binDir = os.path.abspath("bin")
    os.mkdir(binDir)
    tool = os.path.join(binDir, "wct-meta-tool")
    with open(tool, "w") as f :
        f.write("#!/bin/sh\necho found on the child PATH\n")
    os.chmod(tool, os.stat(tool).st_mode | stat.S_IXUSR)
    checkRunCommand({
        "cmd": ["wct-meta-tool"],
        "env": {"PATH": binDir + os.pathsep + os.environ.get("PATH", "")},
        "expect_returncode": 0,
        "expect_stdout": xAnywhere(xEscape("found on the child PATH")),
    })

# A malformed env or stdin is rejected up front as an invalid descriptor.
checkRunCommand({
    "cmd": ["wct",
            os.path.join(_FIXTURES, "fixture_env_invalid.py"),
            os.path.join(_FIXTURES, "fixture_stdin_invalid.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("'env' must be a dict mapping variable names to strings, or to None to remove them")),
        xAnywhere(xEscape("'stdin' must be a string or bytes")),
        xAnywhere(xEscape("0/2 passed")),
    ],
})
