# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test that should always pass. Used as input to meta-tests.
from wct import checkPathNotExists

checkPathNotExists("nothing_here.txt")
