# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# An exception other than a failed check is a broken test, not a flap: it
# must propagate on the first attempt, with that attempt's output shown.
from wct import passTest, retryUntilPass

calls = []


def broken() :
    calls.append(1)
    passTest(f"broken() call number {len(calls)}")
    raise ValueError("not a flap")


retryUntilPass(broken, timeout=30, interval=0.1)
