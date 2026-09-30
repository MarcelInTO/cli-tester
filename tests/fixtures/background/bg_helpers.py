# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Shared by the background-command fixtures in this directory.
import os
import shlex
import socket
import subprocess
import sys

from wct import startBackgroundCommand

_SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")

SERVER_CMD = [sys.executable, _SERVER]
LAUNCHER_CMD = [sys.executable, _SERVER, "--spawn"]

# The same server, as one pre-quoted element for the shell to parse, since
# shell mode joins cmd with spaces and does no quoting of its own.
if os.name == "nt" :
    SHELL_SERVER_CMD = [subprocess.list2cmdline(SERVER_CMD)]
else :
    SHELL_SERVER_CMD = [shlex.join(SERVER_CMD)]
PORT_PATTERN = r"listening on port (\d+)"


def startServer(cmd=SERVER_CMD, useShell=False) :
    """Start the stand-in server and return (handle, port)."""
    bg = startBackgroundCommand({"cmd": cmd}, useShell)
    port = int(bg.waitForOutput(PORT_PATTERN, timeout=30).group(1))
    return bg, port


def portIsFree(port) :
    """True when nothing holds the port. Deliberately without SO_REUSEADDR,
    which on Windows would let the bind succeed over a live listener."""
    s = socket.socket()
    try :
        s.bind(("127.0.0.1", port))
        return True
    except OSError :
        return False
    finally :
        s.close()
