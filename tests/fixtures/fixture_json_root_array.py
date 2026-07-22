# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Exercises check_json_stdout against a command whose stdout is a bare
# top-level JSON array (no enclosing object): "" addresses the root itself,
# "[N]" indexes into it, and indexes chain to any depth. We use
# `python -c "print(...)"` rather than `echo` so the fixture works on
# Windows too (see fixture_json_on_plain_stdout.py).
import sys

from wct import checkRunCommand

_PAYLOAD = '[{"name": "alpha", "tags": ["x", "y"]}, {"name": "beta", "tags": []}, [10, 20]]'

checkRunCommand({
    "cmd": [sys.executable, "-c", f"print('{_PAYLOAD}')"],
    "expect_returncode": 0,
    "check_json_stdout": [
        {"field": "",            "test_type": "arraySize",           "test_value": 3},
        {"field": "[0].name",    "test_type": "valueEqual",          "test_value": "alpha"},
        {"field": "[1].name",    "test_type": "valueNotEqual",       "test_value": "alpha"},
        {"field": "[0].tags",    "test_type": "unorderedArrayMatch", "test_value": ["y", "x"]},
        {"field": "[0].tags[1]", "test_type": "valueEqual",          "test_value": "y"},
        {"field": "[2][1]",      "test_type": "valueEqual",          "test_value": 20},
        {"field": "[-1][0]",     "test_type": "valueEqual",          "test_value": 10},
    ],
})
