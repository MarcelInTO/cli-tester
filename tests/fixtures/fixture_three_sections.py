# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Used by test_section_junit.py. First section passes; second section fails;
# third section never runs because failTest aborts the whole file. Confirms
# that the JUnit report carries the names of the sections that *did* run,
# and that the unreached section is silently absent rather than spuriously
# marked.

from wct import failTest, passTest, sectionBegin, sectionEnd

sectionBegin("alpha: this section passes")
passTest("alpha checkpoint")
sectionEnd()

sectionBegin("beta: this section fails")
failTest("simulated failure in beta")
sectionEnd()

sectionBegin("gamma: this section never runs")
passTest("gamma checkpoint")
sectionEnd()
