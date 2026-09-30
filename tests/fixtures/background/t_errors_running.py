# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Starts a server, then errors without stopping it. The runner must stop it
# when the test ends.
from bg_helpers import startServer
from wct import setState

bg, port = startServer()
setState("server_port", port)
raise RuntimeError("erroring with the server still running")
