# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import json
import os

from wct import getState

# Sentinel filename comes from an env var so the same teardown can be reused
# across the three meta-test variants without their sentinels colliding.
sentinel = os.environ["WCT_SUITE_SENTINEL"]

contents = {
    "resource_a": getState("resource_a"),
    "resource_b": getState("resource_b"),
}

with open(sentinel, "w") as f :
    json.dump(contents, f)
