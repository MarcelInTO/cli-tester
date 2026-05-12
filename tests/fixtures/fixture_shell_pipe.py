# Exercises checkRunShellCommand with a real shell feature (pipe).
# Verifies the bug fix that joins the cmd list when shell=True.
from wct import checkRunShellCommand, xAnywhere, xEscape

checkRunShellCommand({
    "cmd": ["echo", "alpha beta gamma", "|", "grep", "beta"],
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("beta")),
})
