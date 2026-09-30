# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from xml.etree.ElementTree import parse

from wct import checkEqual, checkRunCommand, checkTrue, xAnywhere, xEscape, xFullLine

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_EACH = os.path.join(_FIXTURES, "each")
_BG = os.path.join(_FIXTURES, "background")


def _each(name) :
    return os.path.join(_EACH, name)


def _junitCases(path) :
    """Map each testcase name in a JUnit report to its outcome."""
    cases = {}
    for case in parse(path).getroot().iter("testcase") :
        if case.find("failure") is not None :
            cases[case.get("name")] = "failed"
        elif case.find("error") is not None :
            cases[case.get("name")] = "errored"
        else :
            cases[case.get("name")] = "passed"
    return cases


def _inOrder(text, *needles) :
    """True when every needle occurs in text, each after the one before."""
    pos = 0
    for needle in needles :
        pos = text.find(needle, pos)
        if pos < 0 :
            return False
        pos += len(needle)
    return True


# Both hooks run around every test, in its fresh workspace: setup-each's
# marker is there for the test, and for teardown-each even though the test
# left the cwd elsewhere. Hook output is nested under its own header.
rc, out, err = checkRunCommand({
    "cmd": ["wct", "--setup-each", _each("setup_each.py"), "--teardown-each", _each("teardown_each.py"),
            _each("t_uses_marker.py"), _each("t_uses_marker.py")],
    "expect_returncode": 0,
    "expect_stdout": [
        xFullLine(xEscape("        Running setup-each '") + ".*" + xEscape("setup_each.py'")),
        xFullLine(xEscape("            PASS: (setup-each ran)")),
        xFullLine(xEscape("        PASS: (test body ran)")),
        xAnywhere(xEscape("2/2 passed")),
    ],
})
checkTrue(_inOrder(out, "PASS: (setup-each ran)", "PASS: (test body ran)", "Running teardown-each",
                   "teardown-each ran, marker present"),
          "setup-each, the test and teardown-each ran in that order")
checkEqual(out.count("teardown-each ran, marker present"), 2, "both hooks ran for each test")

# A failed setup-each skips the test and reports it as errored; teardown-each
# still runs.
rc, out, err = checkRunCommand({
    "cmd": ["wct", "--setup-each", _each("setup_each_fails.py"), "--teardown-each", _each("teardown_each.py"),
            _each("t_uses_marker.py"), "--junit", "setup_fails.xml"],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("setup-each failed; test did not run")),
        xAnywhere(xEscape("teardown-each ran, marker absent")),
        xAnywhere(xEscape("0/1 passed, 1 errored")),
    ],
    "dontexpect_stdout": xAnywhere(xEscape("test body ran")),
})
checkEqual(_junitCases("setup_fails.xml"), {"t_uses_marker": "errored"},
           "the skipped test is reported as errored")

# A failed teardown-each is a testcase of its own, for a plain test and for
# one reporting per-scope testcases alike; the tests themselves still pass.
checkRunCommand({
    "cmd": ["wct", "--teardown-each", _each("teardown_each_fails.py"),
            os.path.join(_FIXTURES, "fixture_passes.py"), _each("t_sections.py"), "--junit", "teardown_fails.xml"],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("FAIL: (teardown-each failing on purpose)")),
        xAnywhere(xEscape("2/4 passed, 2 failed")),
    ],
})
checkEqual(_junitCases("teardown_fails.xml"), {
    "fixture_passes": "passed",
    "fixture_passes::__teardown_each__": "failed",
    "t_sections::only section": "passed",
    "t_sections::__teardown_each__": "failed",
}, "teardown-each failures are reported beside the tests, not over them")

# A background command started by setup-each belongs to the test: it is
# still running in the test and in teardown-each, and is stopped after
# teardown-each. (The background fixtures' "suite server" is reused here as
# a per-test one.)
rc, out, err = checkRunCommand({
    "cmd": ["wct", "--setup-each", os.path.join(_BG, "setup_starts_server.py"),
            "--teardown-each", os.path.join(_BG, "t_suite_server_alive.py"),
            os.path.join(_BG, "t_suite_server_alive.py"), os.path.join(_BG, "t_suite_server_alive.py")],
    "timeout": 120,
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("2/2 passed")),
})
checkEqual(out.count("Stopped background command:"), 2, "each test's server was stopped")
checkTrue(_inOrder(out, "Running teardown-each", "Stopped background command:",
                   "Running teardown-each", "Stopped background command:"),
          "each server was stopped after its teardown-each")
