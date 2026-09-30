# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os
import re
import socket

from wct import checkEqual, checkRunCommand, checkTrue, retryUntilPass, xAnywhere, xEscape

_BG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "background")


def _fixture(name) :
    return os.path.join(_BG, name)


def _portIsFree(port) :
    # Deliberately without SO_REUSEADDR, which on Windows would let the bind
    # succeed over a live listener.
    s = socket.socket()
    try :
        s.bind(("127.0.0.1", port))
        return True
    except OSError :
        return False
    finally :
        s.close()


# The handle end to end: waitForOutput, stderr capture, env, stop, and the
# process tree going away for a launcher and in shell mode.
checkRunCommand({
    "cmd": ["wct", _fixture("t_lifecycle.py")],
    "timeout": 120,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("1/1 passed")),
})

# A test that fails, and one that errors, with a server still running: the
# runner stops each when its test ends, so the next test finds their ports
# free. The launcher case also checks the child holding the port goes too.
rc, out, err = checkRunCommand({
    "cmd": ["wct", _fixture("t_fails_running.py"), _fixture("t_errors_running.py"), _fixture("t_ports_free.py")],
    "timeout": 120,
    "expect_returncode": 1,
    "expect_stdout": xAnywhere(xEscape("1/3 passed, 1 failed, 1 errored")),
})
checkEqual(out.count("Stopped background command:"), 2, "the runner stopped both leftover commands")

# A wait that times out shows the command's output, stderr included.
checkRunCommand({
    "cmd": ["wct", _fixture("t_wait_timeout.py")],
    "timeout": 120,
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape('BAD:  waitForOutput [no match for r"listening on port" within 0.5s]')),
        xAnywhere(xEscape("note on stderr")),
        xAnywhere(xEscape("0/1 passed")),
    ],
})

# A command that exits fails the wait at once, well inside the wait's 60s.
checkRunCommand({
    "cmd": ["wct", _fixture("t_wait_exited.py")],
    "timeout": 30,
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape('BAD:  waitForOutput [exited with code 3 before output matched r"never printed"]')),
        xAnywhere(xEscape("about to exit")),
    ],
})

# The descriptor takes only launch keys.
checkRunCommand({
    "cmd": ["wct", _fixture("t_invalid.py")],
    "timeout": 30,
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("Unrecognized entry 'expect_returncode'")),
        xAnywhere(xEscape("invalid background command descriptor")),
    ],
})

# A server started by --setup outlives every test, and is stopped when the
# run ends.
rc, out, err = checkRunCommand({
    "cmd": ["wct", "--setup", _fixture("setup_starts_server.py"),
            _fixture("t_suite_server_alive.py"), _fixture("t_suite_server_alive.py")],
    "timeout": 120,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("2/2 passed")),
})
match = re.search(r"suite server port (\d+)", out)
checkTrue(match is not None, "setup reported the suite server's port")
suitePort = int(match.group(1))
retryUntilPass(lambda : checkTrue(_portIsFree(suitePort), f"suite server port {suitePort} is free after the run"),
               timeout=5, interval=0.1)
