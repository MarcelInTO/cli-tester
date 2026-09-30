# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A command that never passes: retryUntilPass must give up after its timeout
# and fail the test with the last attempt's failure, attributed to the
# section that attempt left open.
from retry_helpers import FAIL_CMD
from wct import checkRunCommand, retryUntilPass, sectionBegin, sectionEnd


def probe() :
    sectionBegin("probe")
    checkRunCommand({"cmd": FAIL_CMD, "expect_returncode": 0})
    sectionEnd()


retryUntilPass(probe, timeout=1, interval=0.2)
