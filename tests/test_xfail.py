# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os
import xml.etree.ElementTree as ET

from wct import (
    checkPathExists,
    checkRunCommand,
    failTest,
    passTest,
    sectionBegin,
    sectionEnd,
    xAnywhere,
    xEscape,
)

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


sectionBegin("per-block xfail: block fails as expected -> XFAIL, suite exit 0")
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_xfail_block_fails.py")],
    "expect_returncode": 0,
    "expect_stdout": [
        xAnywhere(xEscape("XFAIL: known bug, tracked in issue#999")),
        xAnywhere(xEscape("1 xfailed")),
    ],
    "dontexpect_stdout": [
        xAnywhere(xEscape(" failed")),
        xAnywhere(xEscape("xpassed")),
    ],
})
sectionEnd()


sectionBegin("per-block xfail: block does not fail -> XPASS, suite exit 1")
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_xfail_block_passes.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("XPASS: supposedly-broken validation, issue#999")),
        xAnywhere(xEscape("1 xpassed")),
        xAnywhere(xEscape("remove the expectFail wrapper")),
    ],
})
sectionEnd()


sectionBegin("whole-test xfail: test fails -> XFAIL, suite exit 0")
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_xfail_whole_test_fails.py")],
    "expect_returncode": 0,
    "expect_stdout": [
        xAnywhere(xEscape("Expecting test to fail: whole-test known bug, issue#999")),
        xAnywhere(xEscape("1 xfailed")),
    ],
})
sectionEnd()


sectionBegin("whole-test xfail: test passes -> XPASS, suite exit 1")
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_xfail_whole_test_passes.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("1 xpassed")),
        xAnywhere(xEscape("remove the expectTestFails() call")),
    ],
})
sectionEnd()


sectionBegin("real FAIL outside any xfail block still fails the suite")
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_xfail_real_fail_outside.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("1 failed")),
    ],
})
sectionEnd()


sectionBegin("JUnit XML: xfail -> <skipped>, xpass -> <failure>")
_JUNIT_OUT = "junit_xfail.xml"
checkRunCommand({
    "cmd": [
        "wct",
        "--junit", _JUNIT_OUT,
        os.path.join(_FIXTURES, "fixture_xfail_block_fails.py"),
        os.path.join(_FIXTURES, "fixture_xfail_block_passes.py"),
    ],
    "expect_returncode": 1,
})

checkPathExists(_JUNIT_OUT)

root = ET.parse(_JUNIT_OUT).getroot()
suite = root.find("testsuite")
if suite is None :
    failTest("missing <testsuite>")

if int(suite.get("skipped", "0")) != 1 :
    failTest(f"skipped attribute is {suite.get('skipped')}, expected 1")
if int(suite.get("failures", "0")) != 1 :
    failTest(f"failures attribute is {suite.get('failures')}, expected 1")

xfailCase = suite.find("./testcase[@name='fixture_xfail_block_fails']")
if xfailCase is None :
    failTest("missing testcase for fixture_xfail_block_fails")
if xfailCase.find("skipped") is None :
    failTest("xfail testcase is missing <skipped> child")

xpassCase = suite.find("./testcase[@name='fixture_xfail_block_passes']")
if xpassCase is None :
    failTest("missing testcase for fixture_xfail_block_passes")
if xpassCase.find("failure") is None :
    failTest("xpass testcase is missing <failure> child")

passTest("JUnit XML carries xfail as <skipped> and xpass as <failure>")
sectionEnd()
