# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkPathExists, checkRunCommand, failTest, passTest, variantBegin, variantEnd

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fixtures", "sibling_import")


# ---------------------------------------------------------------------------
# Variant 1: a single test can import a sibling helper from its own directory.
# This is the basic "natural pattern" the issue calls out.
# ---------------------------------------------------------------------------
variantBegin("single test imports a sibling helpers.py")

checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "dirA", "t_a.py")],
    "expect_returncode": 0,
})

variantEnd()


# ---------------------------------------------------------------------------
# Variant 2: two tests in different directories each define their own helpers.py
# with different contents. Both must resolve to their own neighbor — if the
# sys.modules cache leaked across tests, dirB would see dirA's TAG and fail.
# ---------------------------------------------------------------------------
variantBegin("same-named helpers in different test dirs don't collide")

checkRunCommand({
    "cmd": [
        "wct",
        os.path.join(_FIXTURES, "dirA", "t_a.py"),
        os.path.join(_FIXTURES, "dirB", "t_b.py"),
    ],
    "expect_returncode": 0,
})

variantEnd()


# ---------------------------------------------------------------------------
# Variant 3: setup and teardown scripts can also import a sibling module. The
# teardown writes a sentinel containing the MAGIC it imported; we verify it
# matches the suite-level helpers.py value (not a test subdir's value).
# ---------------------------------------------------------------------------
variantBegin("setup and teardown can import sibling modules")

sentinelPath = os.path.abspath("sibling_sentinel.txt")
os.environ["WCT_SIBLING_SENTINEL"] = sentinelPath

checkRunCommand({
    "cmd": [
        "wct",
        "--setup", os.path.join(_FIXTURES, "setup.py"),
        "--teardown", os.path.join(_FIXTURES, "teardown.py"),
        os.path.join(_FIXTURES, "dirA", "t_a.py"),
    ],
    "expect_returncode": 0,
})

checkPathExists(sentinelPath)
with open(sentinelPath) as f :
    v = f.read()
if v != "suite" :
    failTest(f"teardown sentinel was {v!r}, expected 'suite' — sibling import resolved wrong")
passTest("teardown's sibling import resolved to its own helpers.py (MAGIC=='suite')")

variantEnd()
