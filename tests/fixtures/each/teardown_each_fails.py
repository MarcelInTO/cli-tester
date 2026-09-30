# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Per-test teardown that fails.
from wct import failTest

failTest("teardown-each failing on purpose")
