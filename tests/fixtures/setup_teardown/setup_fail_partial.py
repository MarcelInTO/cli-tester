# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

from wct import failTest, setState

setState("resource_a", "value-a")
failTest("setup aborts after recording resource_a but before resource_b")
