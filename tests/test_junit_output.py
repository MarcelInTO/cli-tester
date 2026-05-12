# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os
import xml.etree.ElementTree as ET

from wct import checkPathExists, checkRunCommand, failTest, passTest

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Run wct against a mix of pass / fail / error fixtures with --junit. The
# output file is written to the meta-test's workspace (current cwd).
_JUNIT_OUT = "junit_output.xml"

checkRunCommand({
    "cmd": [
        "wct",
        "--junit", _JUNIT_OUT,
        os.path.join(_FIXTURES, "fixture_passes.py"),
        os.path.join(_FIXTURES, "fixture_fails.py"),
        os.path.join(_FIXTURES, "fixture_crashes.py"),
    ],
    "expect_returncode": 1,
})

checkPathExists(_JUNIT_OUT)

# Parse the XML and verify the structure GitLab CI expects.
root = ET.parse(_JUNIT_OUT).getroot()

if root.tag != "testsuites" :
    failTest(f"root element is <{root.tag}>, expected <testsuites>")

suite = root.find("testsuite")
if suite is None :
    failTest("no <testsuite> child of <testsuites>")

if int(suite.get("tests", "0")) != 3 :
    failTest(f"tests attribute is {suite.get('tests')}, expected 3")
if int(suite.get("failures", "0")) != 1 :
    failTest(f"failures attribute is {suite.get('failures')}, expected 1")
if int(suite.get("errors", "0")) != 1 :
    failTest(f"errors attribute is {suite.get('errors')}, expected 1")

cases = suite.findall("testcase")
if len(cases) != 3 :
    failTest(f"got {len(cases)} <testcase> elements, expected 3")

# Verify we have one of each outcome shape: a clean pass (no child), a failure
# (has <failure>), and an error (has <error>).
hasPass = any(c.find("failure") is None and c.find("error") is None for c in cases)
hasFail = any(c.find("failure") is not None for c in cases)
hasError = any(c.find("error") is not None for c in cases)

if not hasPass :
    failTest("no testcase represents a clean pass (no failure/error child)")
if not hasFail :
    failTest("no testcase has a <failure> child")
if not hasError :
    failTest("no testcase has an <error> child")

# Verify the testcase for fixture_fails carries our test name and a classname.
fails = [c for c in cases if c.get("name") == "fixture_fails"]
if not fails :
    failTest("expected a testcase with name='fixture_fails'")
if fails[0].get("classname") != "fixtures" :
    failTest(f"fixture_fails classname is {fails[0].get('classname')}, expected 'fixtures'")

passTest("JUnit XML matches expected structure")
