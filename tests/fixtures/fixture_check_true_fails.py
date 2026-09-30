# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test whose checkTrue fails. Used as input to meta-tests.
from wct import checkTrue

checkTrue(1 + 1 == 3, "arithmetic still works")
