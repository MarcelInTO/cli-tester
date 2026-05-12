# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

# Sibling import from the teardown script. The MAGIC value gets written to a
# sentinel path the meta-test reads back, proving the import resolved to *this*
# directory's helpers.py and not one belonging to a test subdir.
from helpers import MAGIC

with open(os.environ["WCT_SIBLING_SENTINEL"], "w") as f :
    f.write(MAGIC)
