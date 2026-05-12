# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A sibling import in a setup script: only works if the script's directory
# is on sys.path for the duration of the run (issue #4).
from helpers import MAGIC

assert MAGIC == "suite", f"setup got MAGIC={MAGIC!r}"
