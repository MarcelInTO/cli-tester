# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test whose command sleeps forever with NO per-command timeout set.
# Used as input to a meta-test that runs wct with --timeout, verifying the
# suite-wide default kills the hung command. sys.executable keeps the hang
# portable across platforms.
import sys

from wct import checkRunCommand

checkRunCommand({
    "cmd": [sys.executable, "-c", "import time; time.sleep(30)"],
    "expect_returncode": 0,
})
