import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Running a mix of pass + fail in one invocation should still exit non-zero,
# and the summary should reflect both outcomes. This guards the exit-code
# propagation fix; the old bootstrapper always returned 0.
checkRunCommand({
    "cmd": [
        "wct",
        os.path.join(_FIXTURES, "fixture_passes.py"),
        os.path.join(_FIXTURES, "fixture_fails.py"),
    ],
    "expect_returncode": 1,
    "expect_stdout": [
        xAnywhere(xEscape("1/2 passed")),
        xAnywhere(xEscape("1 failed")),
    ],
})
