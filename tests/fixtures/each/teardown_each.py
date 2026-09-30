# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Per-test teardown: reports whether it finds setup-each's marker in its cwd,
# which must be the test's workspace wherever the test left the cwd.
import os

from wct import passTest

passTest(f"teardown-each ran, marker {'present' if os.path.exists('marker.txt') else 'absent'}")
