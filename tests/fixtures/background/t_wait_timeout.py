# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Waits for output that never comes: must fail after the timeout and show
# what the command did write, stderr included. The earlier wait consumes the
# port line, so a wait for it again finds nothing new.
from bg_helpers import startServer

bg, port = startServer()
bg.waitForOutput(r"listening on port", timeout=0.5)
