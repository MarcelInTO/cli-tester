# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# A passing test that uses a section, so it reports per-scope testcases.
from wct import passTest, sectionBegin, sectionEnd

sectionBegin("only section")
passTest("inside the section")
sectionEnd()
