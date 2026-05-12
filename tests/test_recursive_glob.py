# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import checkRunCommand, xAnywhere, xEscape

_HERE = os.path.dirname(os.path.abspath(__file__))

# '**' should match arbitrary subdirectories. fixture_in_subdir.py lives at
# tests/fixtures/sub/, so the pattern below must descend to find it.
# Guards the bug fix that added recursive=True to glob.glob.
checkRunCommand({
    "cmd": ["wct", os.path.join(_HERE, "fixtures", "**", "fixture_in_subdir.py")],
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("fixture_in_subdir.py")),
})
