# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Verify that test files using variantBegin / sectionBegin produce one JUnit
# <testcase> per scope (not one per file), so GitLab CI's Tests tab can
# surface individual sub-tests by their section/variant labels.

import os
import xml.etree.ElementTree as ET

from wct import (
    checkPathExists,
    checkRunCommand,
    failTest,
    passTest,
    sectionBegin,
    sectionEnd,
)

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


sectionBegin("three sections, middle one fails: alpha and beta emitted, gamma absent")
_JUNIT_OUT = "junit_three_sections.xml"
checkRunCommand({
    "cmd": [
        "wct",
        "--junit", _JUNIT_OUT,
        os.path.join(_FIXTURES, "fixture_three_sections.py"),
    ],
    "expect_returncode": 1,
})

checkPathExists(_JUNIT_OUT)

root = ET.parse(_JUNIT_OUT).getroot()
suite = root.find("testsuite")
if suite is None :
    failTest("missing <testsuite>")

cases = suite.findall("testcase")
names = [c.get("name") for c in cases]

# Expect exactly two testcases: alpha (passed) and beta (failed). The third
# section (gamma) never ran because failTest unwound the file, and should
# not appear in the report.
if len(cases) != 2 :
    failTest(f"got {len(cases)} testcases, expected 2 (got names: {names})")

alpha = suite.find("./testcase[@name='fixture_three_sections::alpha: this section passes']")
if alpha is None :
    failTest(f"missing testcase for alpha section (names seen: {names})")
if alpha.find("failure") is not None or alpha.find("error") is not None :
    failTest("alpha section was expected to pass but carries failure/error")

beta = suite.find("./testcase[@name='fixture_three_sections::beta: this section fails']")
if beta is None :
    failTest(f"missing testcase for beta section (names seen: {names})")
betaFailure = beta.find("failure")
if betaFailure is None :
    failTest("beta section was expected to carry a <failure> child")
if "simulated failure in beta" not in (betaFailure.get("message") or "") :
    failTest(f"beta failure message did not carry failTest text: {betaFailure.get('message')}")

# gamma must not be present at all — the runner only records scopes that
# either closed cleanly or were the innermost open scope at failure time.
if any("gamma" in (n or "") for n in names) :
    failTest(f"gamma section should not appear in report; names: {names}")

if int(suite.get("tests", "0")) != 2 :
    failTest(f"tests attribute is {suite.get('tests')}, expected 2")
if int(suite.get("failures", "0")) != 1 :
    failTest(f"failures attribute is {suite.get('failures')}, expected 1")

passTest("three-section file emits per-section testcases, unreached section absent")
sectionEnd()


sectionBegin("nested scopes: testcase name is the joined scope path")
_JUNIT_OUT2 = "junit_nested_scopes.xml"
checkRunCommand({
    "cmd": [
        "wct",
        "--junit", _JUNIT_OUT2,
        os.path.join(_FIXTURES, "fixture_nested_scopes.py"),
    ],
    "expect_returncode": 0,
})

checkPathExists(_JUNIT_OUT2)

root = ET.parse(_JUNIT_OUT2).getroot()
suite = root.find("testsuite")
if suite is None :
    failTest("missing <testsuite>")

cases = suite.findall("testcase")
names = [c.get("name") for c in cases]

expected = [
    "fixture_nested_scopes::outer variant / inner section one",
    "fixture_nested_scopes::outer variant / inner section two",
]
for want in expected :
    if not any(n == want for n in names) :
        failTest(f"missing testcase '{want}'; names: {names}")

passTest("nested scopes carry joined path in testcase name")
sectionEnd()


sectionBegin("file without scopes still emits one testcase per file (regression)")
_JUNIT_OUT3 = "junit_no_scopes.xml"
checkRunCommand({
    "cmd": [
        "wct",
        "--junit", _JUNIT_OUT3,
        os.path.join(_FIXTURES, "fixture_passes.py"),
    ],
    "expect_returncode": 0,
})

checkPathExists(_JUNIT_OUT3)

root = ET.parse(_JUNIT_OUT3).getroot()
suite = root.find("testsuite")
if suite is None :
    failTest("missing <testsuite>")

cases = suite.findall("testcase")
if len(cases) != 1 :
    failTest(f"got {len(cases)} testcases for scope-less file, expected 1")
if cases[0].get("name") != "fixture_passes" :
    failTest(f"scope-less testcase name is {cases[0].get('name')}, expected 'fixture_passes'")

passTest("scope-less file preserves one-testcase-per-file behavior")
sectionEnd()
