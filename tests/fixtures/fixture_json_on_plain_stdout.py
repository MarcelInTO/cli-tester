# Exercises check_json_stdout against a command whose stdout is plain text,
# not JSON. The runner should report a clean FAIL rather than crashing with
# JSONDecodeError.
from wct import checkRunCommand

checkRunCommand({
    "cmd": ["echo", "this is not json"],
    "expect_returncode": 0,
    "check_json_stdout": [
        {"field": "anything", "test_type": "valueEqual", "test_value": "x"},
    ],
})
