# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

import os

from xml.etree.ElementTree import parse

from wct import checkEqual, checkRunCommand, xAnywhere, xEscape

_RETRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "retry")


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


# A flapping command passes on attempt 3. The failed attempts print nothing;
# the passing one is shown with the attempt count.
checkRunCommand({
    "cmd": ["wct", os.path.join(_RETRY, "t_flaps.py")],
    "expect_returncode": 0,
    "expect_stdout": [
        xAnywhere(xEscape("Retry: passed on attempt 3")),
        xAnywhere(xEscape("PASS: (retryUntilPass returned the passing attempt's result)")),
        xAnywhere(xEscape("1/1 passed")),
    ],
    "dontexpect_stdout": [xAnywhere(xEscape("FAIL")), xAnywhere(xEscape("BAD"))],
})

# A section inside the retried function is recorded once, not nested inside
# itself once per failed attempt.
checkRunCommand({
    "cmd": ["wct", os.path.join(_RETRY, "t_section.py"), "--junit", "section.xml"],
    "expect_returncode": 0,
})
checkEqual(_junitCases("section.xml"), {"t_section::probe": "passed"},
           "the retried section is a single passing testcase")

# Giving up shows the last attempt's failure (once, not once per attempt),
# fails the test, and attributes it to the section that attempt left open.
rc, out, err = checkRunCommand({
    "cmd": ["wct", os.path.join(_RETRY, "t_gives_up.py"), "--junit", "gives_up.xml"],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("Retry: gave up after")),
        xAnywhere(xEscape("BAD:  expect_returncode")),
        xAnywhere(xEscape("0/1 passed")),
    ],
})
checkEqual(out.count("FAIL:"), 1, "only the last attempt's failure is shown")
checkEqual(_junitCases("gives_up.xml"), {"t_gives_up::probe": "failed"},
           "the failure is attributed to the open section")

# Any other exception propagates at once, with the attempt's output shown.
rc, out, err = checkRunCommand({
    "cmd": ["wct", os.path.join(_RETRY, "t_error.py")],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("PASS: (broken() call number 1)")),
        xAnywhere(xEscape("1 errored")),
    ],
    "dontexpect_stdout": [xAnywhere(xEscape("call number 2")), xAnywhere(xEscape("Retry:"))],
})
