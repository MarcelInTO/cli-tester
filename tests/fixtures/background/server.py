# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A stand-in for a long-running server: listens on a free local port, reports
# it on stdout and a note on stderr, then runs until stopped. The sleep is a
# backstop, so an orphan left by a broken stop still goes away eventually.
#
# With --spawn it starts a copy of itself and waits on it instead, standing in
# for a launcher whose child does the real work (and holds the port).
import socket
import subprocess
import sys
import time

if "--spawn" in sys.argv :
    sys.exit(subprocess.call([sys.executable, __file__]))

s = socket.socket()
s.bind(("127.0.0.1", 0))
s.listen()
print("listening on port", s.getsockname()[1], flush=True)
print("note on stderr", file=sys.stderr, flush=True)
print("ready", flush=True)
time.sleep(120)
