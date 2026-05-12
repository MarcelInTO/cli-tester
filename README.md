# WCT — CLI Tester

A black-box test runner for command-line programs. Tests are plain Python scripts that import helper functions from the `wct` module and call them; the first failed check stops that test, but other tests still run.

## Install

WCT requires Python 3.10 or later. The recommended installer is [uv](https://docs.astral.sh/uv/), which manages its own Python — you don't need to install one separately.

**WCT is not yet published to PyPI.** Until then, install from a clone or directly from the git URL.

### From a local clone

```sh
git clone <repository-url>
uv tool install --editable cli-tester
```

### Directly from the git URL

Useful for consumers (CI jobs, other tools) that don't want a local checkout. For workstations with SSH access to studio.wevr.com:

```sh
uv tool install "git+ssh://git@studio.wevr.com/wevr-public/cli-tester.git@v0.2.0"
```

For another project's GitLab CI job, using the auto-injected `CI_JOB_TOKEN`:

```yaml
test:
  image: ghcr.io/astral-sh/uv:python3.10-bookworm-slim
  script:
    - uv tool install "git+https://gitlab-ci-token:${CI_JOB_TOKEN}@studio.wevr.com/wevr-public/cli-tester.git@v0.2.0"
    - export PATH="$HOME/.local/bin:$PATH"
    - wct --junit junit.xml 'tests/test_*.py'
  artifacts:
    when: always
    paths: [junit.xml]
    reports:
      junit: junit.xml
```

A one-time setup on the wct project is required for `CI_JOB_TOKEN` to grant the consumer access: **Settings → CI/CD → Token Access → Allowed projects/groups**, and add each consumer project (or its parent group). GitLab's default since 16.0 is to deny cross-project token access; you have to opt in.

Pin to a tag (above) for stability against main-branch churn.

### Once published to PyPI

```sh
uv tool install wct
```

`pipx install ...` and `pip install ...` will also work — `pyproject.toml` is standard.

## Quick start

Save this as `test_smoke.py`:

```python
from wct import checkRunCommand, xAnywhere, xEscape

checkRunCommand({
    "cmd": ["echo", "hello, wct"],
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("hello, wct")),
})
```

Then run it:

```sh
wct test_smoke.py
```

You should see a green `PASS` line and `1/1 passed` at the end, with exit code `0`.

For a more thorough sanity check, run wct's own meta-test suite from a clone of this repository:

```sh
wct 'tests/test_*.py'
```

## Running tests

```
wct <test_path_or_glob> [<test_path_or_glob> ...] [-p PATH] [-v] [--junit FILE]
```

- Multiple paths or globs can be listed on one command line.
- `**` in a glob matches arbitrary subdirectories (rails/golang style). Quote your globs so wct expands them, not your shell.
- `-p PATH` prepends to `$PATH` when running the executables under test — handy when testing a locally-built binary that isn't installed yet.
- `-v` prints additional configuration and progress output.
- `--junit FILE` writes a JUnit XML report on completion; see [Continuous integration](#continuous-integration).

Each test runs in a clean workspace under `~/.cache/wct/`. The workspace is wiped between tests, so tests cannot rely on prior state.

Exit codes: `0` if all tests passed, `1` if any test failed or errored, `2` if no tests matched the given paths.

## Writing a test

Each test is a Python file. Import what you need from `wct` and call check functions in sequence. If a check fails, that test stops; the runner moves to the next test.

```python
from wct import checkRunCommand, checkPathExists, xFullLine, xEscape

checkRunCommand({
    "cmd": ["./mytool", "build", "release"],
    "expect_returncode": 0,
    "expect_stdout": xFullLine(xEscape("build: ok")),
})

checkPathExists("build/output.bin")
```

### Working directory and fixture files

Each test runs with `cwd` set to a fresh empty workspace, **not** the directory the test file lives in. This means:

- Your test can freely write files (`./build/output.bin` above is created in the workspace and disappears before the next test).
- Your test **cannot** reach fixture files via paths relative to the test source. Use `__file__` to resolve them:

```python
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIXTURE = os.path.join(_HERE, "fixtures", "input.json")

checkRunCommand({
    "cmd": ["./mytool", "--input", _FIXTURE],
    "expect_returncode": 0,
})
```

### Organizing tests

A common convention is to keep tests under `tests/`, named `test_*.py`, with any shared inputs under `tests/fixtures/`. Run them all with one glob:

```sh
wct 'tests/test_*.py'              # all top-level test files
wct 'tests/**/test_*.py'           # recurse into subdirectories
```

Quote the glob so the pattern reaches wct unexpanded.

### Output grouping

`sectionBegin(msg)` / `sectionEnd()` and `variantBegin(msg)` / `variantEnd()` wrap groups of checks with labeled banners and indent nested output. Use sections for major test phases and variants for "the same checks with different inputs":

```python
sectionBegin("Build phase")
checkRunCommand({"cmd": ["./mytool", "build"], "expect_returncode": 0})
sectionEnd()

sectionBegin("Per-target output verification")
for target in ("linux", "macos", "windows"):
    variantBegin(f"target={target}")
    checkRunCommand({"cmd": ["./mytool", "build", target], "expect_returncode": 0})
    checkPathExists(f"build/{target}/out.bin")
    variantEnd()
sectionEnd()
```

### Shell features (pipes, redirects, glob expansion)

`checkRunShellCommand` runs the command via the shell so shell syntax works:

```python
from wct import checkRunShellCommand, xAnywhere, xEscape

checkRunShellCommand({
    "cmd": ["./mytool", "list", "|", "grep", "active"],
    "expect_returncode": 0,
    "expect_stdout": xAnywhere(xEscape("active")),
})
```

The `cmd` list is joined with spaces and passed to the shell — there is no automatic quoting, so if you need a literal argument with spaces or special characters, quote it yourself within the list element.

## Understanding the output

Each test prints a `Running test 'X'` header, then one line per check, then a final summary. The status markers:

- **`PASS`** — a check succeeded.
- **`FAIL`** — a check failed; the test stops here and the runner moves to the next test.
- **`OK`** — a sub-check inside a `checkRunCommand` succeeded. Only printed when *some* sub-check in the same call failed, so you can see which parts went right.
- **`BAD`** — a sub-check inside a `checkRunCommand` failed. Same context as `OK`.
- **`ERROR`** — the test script itself raised an unhandled exception (not a failed check). Reported separately from failures in the summary.

The final line is `N/M passed[, X failed][, Y errored]`. The process exits `0` if everything passed, `1` if anything failed or errored, `2` if no tests matched.

## Continuous integration

WCT emits a JUnit XML report via `--junit FILE`. Most CI systems consume JUnit XML; the example below is for GitLab, but the same pattern (install wct, run with `--junit`, hand the file to the CI's test reporter) works on GitHub Actions, Jenkins, CircleCI, and others.

```yaml
# .gitlab-ci.yml
image: ghcr.io/astral-sh/uv:python3.10-bookworm-slim

stages:
  - test

test:
  stage: test
  script:
    - uv tool install wct          # pre-PyPI: substitute your editable install
    - export PATH="$HOME/.local/bin:$PATH"
    - wct --junit junit.xml 'tests/test_*.py'
  artifacts:
    when: always
    paths:
      - junit.xml
    reports:
      junit: junit.xml
```

GitLab surfaces per-test results in the merge-request widget via `artifacts:reports:junit`, and tracks flakiness over time. `when: always` ensures the report is uploaded even when the job fails — which is when you most want it.

## API reference

### Running commands

- **`checkRunCommand(testvals)`** — run a process and assert on its output.
- **`checkRunShellCommand(testvals)`** — same, but the command runs via the shell (so pipes, redirects, glob expansion, etc. work).

`testvals` is a dict with the following keys (all optional except `cmd`):

| Key | Type | Meaning |
|---|---|---|
| `cmd` | `list[str]` | Command and arguments. For `checkRunShellCommand`, the list is joined with spaces and passed to the shell. |
| `expect_returncode` | `int` | Process must exit with this code. |
| `dontexpect_returncode` | `int` | Process must NOT exit with this code. |
| `expect_stdout` | `str` or `list[str]` | Regex(es) that must all match stdout. |
| `dontexpect_stdout` | `str` or `list[str]` | Regex(es) that must NOT match stdout. |
| `expect_stderr` | `str` or `list[str]` | Regex(es) that must all match stderr. |
| `dontexpect_stderr` | `str` or `list[str]` | Regex(es) that must NOT match stderr. |
| `check_json_stdout` | `list[dict]` | JSON field assertions (see below). |

#### JSON field assertions

Use field paths like `data.items[0].name`. Supported `test_type` values:

```python
"check_json_stdout": [
    {"field": "status",  "test_type": "valueEqual",          "test_value": "ok"},
    {"field": "error",   "test_type": "valueNotEqual",       "test_value": ""},
    {"field": "items",   "test_type": "arraySize",           "test_value": 3},
    {"field": "tags",    "test_type": "unorderedArrayMatch", "test_value": ["a", "b"]},
]
```

### Filesystem checks

- **`checkPathExists(path)`** — path must exist.
- **`checkPathNotExists(path)`** — path must not exist.
- **`checkFileWriteable(path)`** — file must be writable by the current user.
- **`checkFileReadOnly(path)`** — file must not be writable by the current user.

### Test flow

- **`failTest(message)`** — fail the current test with `message`. Does not return.
- **`passTest(message)`** — log an informational pass. Does not terminate the test; use for recording checkpoints that don't fit the `check*` functions.
- **`operatingSystem()`** — returns `"Linux"`, `"Darwin"`, or `"Windows"`. Use to branch test logic across platforms.
- **`deleteFolder(path)`** — remove a directory tree, including read-only files.

### Output grouping

- **`sectionBegin(msg)`** / **`sectionEnd()`** — wrap a group of checks with a labeled banner.
- **`variantBegin(msg)`** / **`variantEnd()`** — wrap a sub-block within a section, typically used to run the same logic with different inputs.

### Regex helpers

`expect_stdout` / `expect_stderr` take regular expressions. These helpers build common patterns so you don't have to write them by hand. None of them escape their argument — if you want to match literal text, wrap it in `xEscape`:

- **`xEscape(s)`** — escape literal text for use inside a regex.
- **`xAnywhere(p)`** — match `p` anywhere in the output. (Marker only — returns `p` unchanged. Use it to document intent.)
- **`xFullLine(p)`** — match `p` as an entire line.
- **`xLastFullLine(p)`** — match `p` as the last full line of output.
- **`xBeginningOfLine(p)`** — match `p` at the start of any line.
- **`xAnywhereSameLine(p1, p2)`** — match `p1` followed by `p2` on the same line.
- **`xAnywhereConsecutiveLines(p1, p2)`** — match `p1` followed by `p2` on the next line.

Because these helpers return raw regex strings (and don't escape), you can compose them:

```python
xFullLine(xEscape("build: ok"))
xAnywhereSameLine(xEscape("status:"), xEscape("ok"))
```
