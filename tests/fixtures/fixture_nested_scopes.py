# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Used by test_section_junit.py. Exercises nested scopes: a variant containing
# two sections. Verifies that the JUnit testcase name carries the joined
# scope path ("variant / section") so GitLab's Tests tab surfaces the leaf
# label with its enclosing context.

from wct import passTest, sectionBegin, sectionEnd, variantBegin, variantEnd

variantBegin("outer variant")

sectionBegin("inner section one")
passTest("inner one ok")
sectionEnd()

sectionBegin("inner section two")
passTest("inner two ok")
sectionEnd()

variantEnd()
