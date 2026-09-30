# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Starts a launcher whose child holds a port, then fails without stopping it.
# The runner must stop the whole tree when the test ends.
from bg_helpers import LAUNCHER_CMD, startServer
from wct import failTest, setState

bg, port = startServer(LAUNCHER_CMD)
setState("launcher_port", port)
failTest("failing with the launcher still running")
