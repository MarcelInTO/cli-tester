# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from wct import failTest, passTest

v = os.environ.get("WCT_SUITE_ENV_VAR")
if v != "from-setup" :
    failTest(f"env var WCT_SUITE_ENV_VAR was {v!r}, expected 'from-setup'")
passTest(f"WCT_SUITE_ENV_VAR={v}")
