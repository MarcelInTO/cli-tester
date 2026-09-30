# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A wct test whose checkEqual fails. Used as input to meta-tests; the string
# expected value checks that both values are shown with their repr.
from wct import checkEqual

checkEqual(5, "0", "ETA is zero")
