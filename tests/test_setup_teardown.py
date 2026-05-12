# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import json
import os
import xml.etree.ElementTree as ET

from wct import checkPathExists, checkRunCommand, failTest, passTest, variantBegin, variantEnd

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fixtures", "setup_teardown")


def _findCase(suite, name) :
    for c in suite.findall("testcase") :
        if c.get("name") == name :
            return c
    return None


# ---------------------------------------------------------------------------
# Variant 1: happy path. Setup exports env var and sets state, three tests run
# (one passes, one fails, one verifies the env var), teardown writes a sentinel
# JSON containing what it saw via getState.
# ---------------------------------------------------------------------------
variantBegin("happy path: setup + 3 tests + teardown")

os.environ["WCT_SUITE_SENTINEL"] = os.path.abspath("sentinel_happy.json")
junitPath = "junit_happy.xml"

checkRunCommand({
    "cmd": [
        "wct",
        "--setup", os.path.join(_FIXTURES, "setup_ok.py"),
        "--teardown", os.path.join(_FIXTURES, "teardown.py"),
        "--junit", junitPath,
        os.path.join(_FIXTURES, "t_pass.py"),
        os.path.join(_FIXTURES, "t_fail.py"),
        os.path.join(_FIXTURES, "t_check_env.py"),
    ],
    # Exit 1 because t_fail fails. Setup and teardown both succeed.
    "expect_returncode": 1,
})

checkPathExists("sentinel_happy.json")
checkPathExists(junitPath)

# Teardown saw both state keys exactly as setup recorded them.
with open("sentinel_happy.json") as f :
    sentinel = json.load(f)
if sentinel.get("resource_a") != "value-a" :
    failTest(f"sentinel.resource_a was {sentinel.get('resource_a')!r}, expected 'value-a'")
if sentinel.get("resource_b") != "value-b" :
    failTest(f"sentinel.resource_b was {sentinel.get('resource_b')!r}, expected 'value-b'")
passTest("teardown read both state keys")

# JUnit XML contains synthetic setup/teardown testcases plus the three real
# tests. Setup and teardown both pass; t_fail has a <failure> child.
root = ET.parse(junitPath).getroot()
suite = root.find("testsuite")
if suite is None :
    failTest("no <testsuite> in JUnit output")

setupCase = _findCase(suite, "__suite_setup__")
teardownCase = _findCase(suite, "__suite_teardown__")
if setupCase is None :
    failTest("no __suite_setup__ testcase in JUnit output")
if teardownCase is None :
    failTest("no __suite_teardown__ testcase in JUnit output")
if setupCase.get("classname") != "wct.suite" :
    failTest(f"setup classname was {setupCase.get('classname')!r}, expected 'wct.suite'")
if setupCase.find("failure") is not None or setupCase.find("error") is not None :
    failTest("__suite_setup__ should be a clean pass in the happy path")
if teardownCase.find("failure") is not None or teardownCase.find("error") is not None :
    failTest("__suite_teardown__ should be a clean pass in the happy path")

failCase = _findCase(suite, "t_fail")
if failCase is None or failCase.find("failure") is None :
    failTest("t_fail testcase missing or has no <failure> child")

envCase = _findCase(suite, "t_check_env")
if envCase is None or envCase.find("failure") is not None or envCase.find("error") is not None :
    failTest("t_check_env should have passed (proving the env var reached it)")
passTest("happy-path JUnit structure correct")

variantEnd()


# ---------------------------------------------------------------------------
# Variant 2: setup fails before recording any state. Tests do not run; every
# collected test is reported as errored. Teardown still runs and sees both
# state keys as None.
# ---------------------------------------------------------------------------
variantBegin("setup fails immediately: no tests run, teardown still runs")

os.environ["WCT_SUITE_SENTINEL"] = os.path.abspath("sentinel_fail_imm.json")
junitPath = "junit_fail_imm.xml"

checkRunCommand({
    "cmd": [
        "wct",
        "--setup", os.path.join(_FIXTURES, "setup_fail_immediately.py"),
        "--teardown", os.path.join(_FIXTURES, "teardown.py"),
        "--junit", junitPath,
        os.path.join(_FIXTURES, "t_pass.py"),
        os.path.join(_FIXTURES, "t_fail.py"),
        os.path.join(_FIXTURES, "t_check_env.py"),
    ],
    "expect_returncode": 1,
    # t_pass.py was collected but should be reported errored, not passed, so
    # its "PASS" string from passTest() should not appear in stdout.
    "dontexpect_stdout": "trivially",
})

checkPathExists("sentinel_fail_imm.json")

with open("sentinel_fail_imm.json") as f :
    sentinel = json.load(f)
if sentinel.get("resource_a") is not None :
    failTest(f"sentinel.resource_a was {sentinel.get('resource_a')!r}, expected None")
if sentinel.get("resource_b") is not None :
    failTest(f"sentinel.resource_b was {sentinel.get('resource_b')!r}, expected None")
passTest("teardown saw no state (setup failed before any setState)")

root = ET.parse(junitPath).getroot()
suite = root.find("testsuite")
setupCase = _findCase(suite, "__suite_setup__")
teardownCase = _findCase(suite, "__suite_teardown__")
if setupCase.find("failure") is None and setupCase.find("error") is None :
    failTest("__suite_setup__ should have a <failure> or <error> child")
if teardownCase.find("failure") is not None or teardownCase.find("error") is not None :
    failTest("__suite_teardown__ should have passed in this variant")

# Every real test should be present as a testcase with an <error> child.
for testName in ("t_pass", "t_fail", "t_check_env") :
    c = _findCase(suite, testName)
    if c is None :
        failTest(f"{testName} testcase missing from JUnit output")
    if c.find("error") is None :
        failTest(f"{testName} should have an <error> child (setup failed)")
passTest("setup-fails variant: tests reported as errored, teardown ran")

variantEnd()


# ---------------------------------------------------------------------------
# Variant 3: setup records resource_a then fails before recording resource_b.
# Teardown null-checks both and writes a sentinel reflecting the partial state.
# ---------------------------------------------------------------------------
variantBegin("partial-setup cleanup: teardown sees resource_a but not resource_b")

os.environ["WCT_SUITE_SENTINEL"] = os.path.abspath("sentinel_partial.json")

checkRunCommand({
    "cmd": [
        "wct",
        "--setup", os.path.join(_FIXTURES, "setup_fail_partial.py"),
        "--teardown", os.path.join(_FIXTURES, "teardown.py"),
        os.path.join(_FIXTURES, "t_pass.py"),
    ],
    "expect_returncode": 1,
})

checkPathExists("sentinel_partial.json")

with open("sentinel_partial.json") as f :
    sentinel = json.load(f)
if sentinel.get("resource_a") != "value-a" :
    failTest(f"sentinel.resource_a was {sentinel.get('resource_a')!r}, expected 'value-a'")
if sentinel.get("resource_b") is not None :
    failTest(f"sentinel.resource_b was {sentinel.get('resource_b')!r}, expected None")
passTest("teardown saw partial state: resource_a present, resource_b absent")

variantEnd()
