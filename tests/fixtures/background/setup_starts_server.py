# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Suite setup that starts a server for the whole run and does not stop it.
from bg_helpers import startServer
from wct import exportEnv, passTest

bg, port = startServer()
exportEnv("WCT_META_SUITE_PORT", str(port))
passTest(f"suite server port {port}")
