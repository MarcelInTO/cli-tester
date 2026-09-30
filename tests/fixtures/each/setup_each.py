# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Per-test setup: leaves a marker in the test's workspace.
from wct import passTest

with open("marker.txt", "w") as f :
    f.write("from setup-each")
passTest("setup-each ran")
