# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Lives one level deeper so meta-tests can verify '**' recursive globbing
# finds it.
from wct import passTest

passTest("found me at depth 1")
