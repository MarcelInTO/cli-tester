# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test that should always fail (the file does not exist).
# Used as input to meta-tests.
from wct import checkPathExists

checkPathExists("definitely_not_here.txt")
