# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A background descriptor may only say how to launch the command; an expect_*
# key is rejected before anything starts.
from bg_helpers import SERVER_CMD
from wct import startBackgroundCommand

startBackgroundCommand({"cmd": SERVER_CMD, "expect_returncode": 0})
