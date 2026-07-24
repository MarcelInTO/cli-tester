# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test whose command sleeps far longer than its per-command timeout.
# Used as input to a meta-test verifying that a hung command is killed and
# its check fails rather than stalling the suite. sys.executable keeps the
# hang portable across platforms (no reliance on a `sleep` binary).
import sys

from wct import checkRunCommand

checkRunCommand({
    "cmd": [sys.executable, "-c", "import time; time.sleep(30)"],
    "timeout": 1,
    "expect_returncode": 0,
})
