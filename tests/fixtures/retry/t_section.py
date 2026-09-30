# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A retried function that opens a section. The failed attempts leave the
# section open; retryUntilPass must roll that back so the JUnit report has a
# single "probe" testcase rather than "probe / probe / probe".
from retry_helpers import FLAP_CMD
from wct import checkRunCommand, retryUntilPass, sectionBegin, sectionEnd


def probe() :
    sectionBegin("probe")
    checkRunCommand({"cmd": FLAP_CMD, "expect_returncode": 0})
    sectionEnd()


retryUntilPass(probe, timeout=30, interval=0.1)
