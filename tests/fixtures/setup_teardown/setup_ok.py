# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

from wct import exportEnv, setState

exportEnv("WCT_SUITE_ENV_VAR", "from-setup")
setState("resource_a", "value-a")
setState("resource_b", "value-b")
