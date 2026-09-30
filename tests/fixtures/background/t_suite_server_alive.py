# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A server started by suite setup must outlive each test.
import os

from bg_helpers import portIsFree
from wct import checkTrue

port = int(os.environ["WCT_META_SUITE_PORT"])
checkTrue(not portIsFree(port), f"suite server still holds port {port}")
