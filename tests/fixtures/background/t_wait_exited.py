# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A command that exits before writing the awaited output: the wait must fail
# at once with the exit code, not sit out its 60s timeout.
import sys

from wct import startBackgroundCommand

bg = startBackgroundCommand({"cmd": [sys.executable, "-c", "print('about to exit'); raise SystemExit(3)"]})
bg.waitForOutput(r"never printed", timeout=60)
