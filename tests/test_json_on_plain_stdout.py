import os

from wct import checkRunCommand, xAnywhere, xEscape

_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# When check_json_stdout is set but the command's stdout is not valid JSON,
# the runner must fail cleanly (exit 1, no Python traceback). Guards the
# bug fix that catches JSONDecodeError in _findJsonField.
checkRunCommand({
    "cmd": ["wct", os.path.join(_FIXTURES, "fixture_json_on_plain_stdout.py")],
    "expect_returncode": 1,
    "expect_stdout": xAnywhere(xEscape("stdout is not valid JSON")),
    "dontexpect_stdout": xAnywhere(xEscape("Traceback")),
    "dontexpect_stderr": xAnywhere(xEscape("JSONDecodeError")),
})
