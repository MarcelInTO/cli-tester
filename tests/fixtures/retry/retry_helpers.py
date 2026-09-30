# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Shared by the retryUntilPass fixtures in this directory.
import sys

# A command that fails its first two runs and passes from the third on. Each
# run bumps a counter file in the cwd (the test's fresh workspace) and prints
# its attempt number.
FLAP_CMD = [sys.executable, "-c",
            "import os; "
            "n = int(open('count').read()) + 1 if os.path.exists('count') else 1; "
            "open('count', 'w').write(str(n)); "
            "print('attempt', n); "
            "raise SystemExit(0 if n >= 3 else 1)"]

# A command that always fails.
FAIL_CMD = [sys.executable, "-c", "raise SystemExit(1)"]
