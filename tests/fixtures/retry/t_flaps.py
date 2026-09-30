# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A flapping command retried until it passes on its third attempt; the value
# retryUntilPass returns must be the passing attempt's.
from retry_helpers import FLAP_CMD
from wct import checkEqual, checkRunCommand, retryUntilPass

rc, out, err = retryUntilPass(
    lambda : checkRunCommand({"cmd": FLAP_CMD, "expect_returncode": 0}),
    timeout=30, interval=0.1)
checkEqual(out.strip(), "attempt 3", "retryUntilPass returned the passing attempt's result")
