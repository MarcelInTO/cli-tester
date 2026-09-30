# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# The BackgroundCommand handle end to end: waiting on output, the consumed-
# output cursor, stderr capture, env, stopping, and stopping twice.
import sys

from bg_helpers import LAUNCHER_CMD, SHELL_SERVER_CMD, portIsFree, startServer
from wct import (
    checkEqual,
    checkTrue,
    retryUntilPass,
    startBackgroundCommand,
    xEscape,
    xFullLine,
)


def checkPortFreed(port) :
    # On Windows a killed process's handles can take a moment to close.
    retryUntilPass(lambda : checkTrue(portIsFree(port), f"port {port} is free after stop"),
                   timeout=5, interval=0.1)


bg, port = startServer()
checkTrue(bg.isRunning(), "server is running")
checkEqual(bg.returncode, None, "a running command has no exit code yet")
checkTrue(not portIsFree(port), f"server holds port {port}")

# stderr is captured along with stdout, and each wait carries on after the
# previous match.
bg.waitForOutput(xEscape("note on stderr"))
bg.waitForOutput(xFullLine(xEscape("ready")))
checkTrue("listening on port" in bg.output(), "output() has everything written so far")

code = bg.stop()
checkTrue(not bg.isRunning(), "server no longer running")
checkTrue(code is not None, f"stop returned the exit code ({code})")
checkEqual(bg.stop(), code, "stopping again returns the same code")
checkPortFreed(port)

# Stopping a launcher also stops the child that actually holds the port.
bg, port = startServer(LAUNCHER_CMD)
bg.stop()
checkPortFreed(port)

# Shell mode, where the shell sits between the runner and the server.
bg, port = startServer(SHELL_SERVER_CMD, useShell=True)
bg.stop()
checkPortFreed(port)

# env reaches a background command.
bg = startBackgroundCommand({
    "cmd": [sys.executable, "-c", "import os, time; print('X=' + os.environ['WCT_META_BG'], flush=True); time.sleep(120)"],
    "env": {"WCT_META_BG": "from-env"},
})
bg.waitForOutput(xEscape("X=from-env"))
bg.stop()

# A server started by a failed retryUntilPass attempt is stopped before the
# next attempt; the passing attempt's server keeps running.
ports = []


def attempt() :
    bg, port = startServer()
    ports.append(port)
    checkTrue(len(ports) >= 3, f"attempt {len(ports)} of 3")


retryUntilPass(attempt, timeout=60, interval=0.1)
for port in ports[:2] :
    checkPortFreed(port)
checkTrue(not portIsFree(ports[2]), "the passing attempt's server still runs")
