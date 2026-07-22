# WCT — CLI Tester

A black-box test runner for command-line programs. Tests are plain Python scripts that import helper functions from the `wct` module and call them; the first failed check stops that test, but other tests still run.

## Install

WCT requires Python 3.10 or later. The recommended installer is [uv](https://docs.astral.sh/uv/), which manages its own Python — you don't need to install one separately.

**WCT is not yet published to PyPI.** Until then, install from a clone or directly from the git URL.

### From a local clone

```sh
git clone https://github.com/MarcelInTO/cli-tester.git
uv tool install --editable cli-tester
```

### Directly from the git URL

Useful for consumers (CI jobs, other tools) that don't want a local checkout. The project is public on GitHub, so no authentication is required for read access.

For HTTPS (works anywhere, including CI jobs without any token setup):

```sh
uv tool install "git+https://github.com/MarcelInTO/cli-tester.git@v1.4.0"
```

For workstations that already have SSH set up to github.com:

```sh
uv tool install "git+ssh://git@github.com/MarcelInTO/cli-tester.git@v1.4.0"
```

A full CI snippet for a project using GitLab CI:

```yaml
test:
  image: ghcr.io/astral-sh/uv:python3.10-bookworm-slim
  script:
    - uv tool install "git+https://github.com/MarcelInTO/cli-tester.git@v1.4.0"
    - export PATH="$HOME/.local/bin:$PATH"
    - wct --junit junit.xml 'tests/test_*.py'
  artifacts:
    when: always
    paths: [junit.xml]
    reports:
      junit: junit.xml
```

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
wct <test_path_or_glob> [<test_path_or_glob> ...]
    [-p PATH] [-v] [--junit FILE] [--setup PATH] [--teardown PATH]
```

- Multiple paths or globs can be listed on one command line.
- `**` in a glob matches arbitrary subdirectories (rails/golang style). Quote your globs so wct expands them, not your shell.
- `-p PATH` prepends to `$PATH` when running the executables under test — handy when testing a locally-built binary that isn't installed yet.
- `-v` prints additional configuration and progress output.
- `--junit FILE` writes a JUnit XML report on completion; see [Continuous integration](#continuous-integration).
- `--setup PATH` / `--teardown PATH` run a script once before / after the suite; see [Suite-level setup and teardown](#suite-level-setup-and-teardown).

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

### Sharing helpers between tests

A test (or `--setup` / `--teardown` script) can `import` a Python module that lives alongside it — wct prepends the script's directory to `sys.path` for the duration of the run, the same way `python script.py` does. So a sibling `helpers.py` just works:

```python
# tests/helpers.py
MY_BIN = "/opt/myapp/bin/mytool"

# tests/test_smoke.py
from wct import checkRunCommand
from helpers import MY_BIN

checkRunCommand({"cmd": [MY_BIN, "--version"], "expect_returncode": 0})
```

Two tests in different directories can each define their own `helpers.py` with different contents; each test resolves to its own neighbor.

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

Beyond formatting the console output, sections and variants also become individual JUnit testcases (one per scope, named `<filebasename>::<scope path>`) so CI dashboards can surface them as distinct rows rather than collapsing the whole file into one. Files that don't use scopes still emit a single testcase per file.

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

## Suite-level setup and teardown

For tests that share an expensive precondition — booting a server, provisioning a transient database schema — wct can run a setup script once before the suite and a teardown script once after.

```sh
wct --setup setup.py --teardown teardown.py 'tests/test_*.py'
```

Both flags are independent — you can pass `--setup` alone if you don't need a teardown, and vice versa. Setup and teardown run in the directory you invoked `wct` from (not a clean workspace, unlike tests), so they can manage paths under `/tmp`, `~/.config`, etc. without surprise.

### Sharing data with tests and teardown

```python
# setup.py
from wct import exportEnv, setState

exportEnv("MYAPP_SERVER_PORT", "24690")        # env var visible to every test
setState("schema", "myapp_test_12345")         # state visible only to teardown
```

```python
# teardown.py
from wct import getState

schema = getState("schema")
# ... drop the schema ...
```

- `exportEnv(name, value)` sets an env var that every test (and teardown) can read. It dies with the wct process, so it doesn't leak into your shell.
- `setState(key, value)` records a JSON-serializable value in a state file. `getState(key, default=None)` reads it back. State is **not** placed in the environment, so it stays invisible to tests that don't ask for it.

### Lifecycle and failure handling

- If setup fails, tests do not run. Teardown still runs, against whatever state setup recorded before failing.
- If teardown fails, the exit code becomes `1` and the teardown failure is reported on its own line so it doesn't get conflated with the test counts.
- `Ctrl-C` during the test phase stops new tests from starting, runs teardown, and exits non-zero. A second `Ctrl-C` skips teardown.

**Teardown must tolerate missing state** because of partial-setup failures — if setup boots one server, records its PID, and then fails on a second server, teardown still needs to clean up the first one. `getState` returns `None` (or the supplied default) when a key was never set, and the natural idiom uses null-checks:

```python
# setup.py
from wct import setState

pid1 = startServer(...); setState("server1_pid", pid1)
pid2 = startServer(...); setState("server2_pid", pid2)   # might fail here
```

```python
# teardown.py
from wct import getState

if (pid := getState("server1_pid")):
    stopServer(pid)
if (pid := getState("server2_pid")):
    stopServer(pid)
```

If setup fails after booting server 1 but before recording `server2_pid`, teardown still cleans up server 1.

## Marking known-broken cases (xfail)

When a test exposes a real bug the team can't fix yet, you have three bad choices: let the test stay red (and people stop reading CI), delete or skip the test (and lose the regression signal), or rewrite the assertion to lock in the buggy behavior (and break the test for the wrong reason when somebody fixes it). The standard fix is the `xfail` pattern — say "this is expected to fail today" so the suite stays green, but the moment it starts passing, *that* is the failure signal that tells you to come delete the marker.

WCT offers two flavors. Use whichever fits.

### Per-block: `expectFail(reason)`

Wrap the known-broken section in a context manager. A `FAIL` inside the block is reported as `XFAIL` (test continues, suite exit code unaffected); if every check inside the block passes, the block is reported as `XPASS` and the suite fails — the marker is now stale.

```python
from wct import checkRunCommand, expectFail

# happy-path checks run normally
checkRunCommand({"cmd": ["./mytool", "version"], "expect_returncode": 0})

with expectFail("validation gap, tracked in issues#585") :
    checkRunCommand({
        "cmd": ["./mytool", "validate", "bad-input"],
        "expect_returncode": 1,
    })

# more happy-path checks
checkRunCommand({"cmd": ["./mytool", "help"], "expect_returncode": 0})
```

### Whole-test: `expectTestFails(reason)`

Call this near the top of a test to mark the entire test as expected-to-fail. If anything in the test produces a `FAIL`, the test is reported `XFAIL`; if the whole test passes, it's reported `XPASS` and the suite fails.

```python
from wct import checkRunCommand, expectTestFails

expectTestFails("known bug, tracked in issues#585")

checkRunCommand({...})
checkRunCommand({...})
```

### Semantics that matter

- **`XFAIL` does not change the exit code.** The whole point of the marker is to keep CI green while a known bug waits its turn.
- **`XPASS` does change the exit code** — the marker is stale and needs to be removed. Without this, xfail is just a glorified skip.
- **Only `TestFailed` (a `FAIL` line) counts as the expected failure.** An unhandled exception from your test code still surfaces as `ERROR`; a broken test is not a known bug.
- **A `FAIL` outside any xfail block still fails the suite.** Real failures aren't suppressed by the presence of xfail blocks elsewhere in the test.
- **JUnit XML reports `xfail` as `<skipped>` and `xpass` as `<failure>`** so CI systems surface stale markers without treating expected failures as regressions.

## Understanding the output

Each test prints a `Running test 'X'` header, then one line per check, then a final summary. The status markers:

- **`PASS`** — a check succeeded.
- **`FAIL`** — a check failed; the test stops here and the runner moves to the next test.
- **`OK`** — a sub-check inside a `checkRunCommand` succeeded. Only printed when *some* sub-check in the same call failed, so you can see which parts went right.
- **`BAD`** — a sub-check inside a `checkRunCommand` failed. Same context as `OK`.
- **`ERROR`** — the test script itself raised an unhandled exception (not a failed check). Reported separately from failures in the summary.
- **`XFAIL`** — a known-broken check failed as expected inside an `expectFail` block (or in a test marked with `expectTestFails`). Counts as a pass for exit-code purposes.
- **`XPASS`** — a check inside an `expectFail` block (or an `expectTestFails`-marked test) didn't fail. The bug appears fixed; remove the marker. Counts as a failure for exit-code purposes.

The final line is `N/M passed[, X failed][, Y errored][, Z xfailed][, W xpassed]`. `xfailed` tests are counted alongside `passed` in the leading fraction because they went the way the test asserted they should. Each `xpassed` test is also printed on its own line below the summary so you can see which markers to remove. When `--setup` or `--teardown` are used, a `Setup: PASS/FAIL` and/or `Teardown: PASS/FAIL` line appears just above it so suite-level outcomes don't get conflated with test counts. The process exits `0` if everything passed (including xfailed), `1` if anything failed, errored, or xpassed, `2` if no tests matched.

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

Test files that use `sectionBegin` / `variantBegin` emit one testcase per scope rather than one per file, so the Tests tab shows each labeled sub-test as its own row. If a section fails, sections that ran before it appear as passing and sections after it are absent (they were never reached). Files that don't use scopes emit a single testcase per file.

When `--setup` or `--teardown` are used, the JUnit report includes synthetic testcases `__suite_setup__` and `__suite_teardown__` (under classname `wct.suite`) so failures there surface in CI alongside the real tests.

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

Indexes may be negative (`items[-1]` is the last element) and may chain
(`matrix[1][2]`). When stdout is a bare top-level JSON array rather than an
object, start the path with an index; an empty path (`""`) addresses the root
value itself, which is how you assert on the bare array as a whole:

```python
# stdout: [{"name": "alpha"}, {"name": "beta"}]
"check_json_stdout": [
    {"field": "",         "test_type": "arraySize",  "test_value": 2},
    {"field": "[0].name", "test_type": "valueEqual", "test_value": "alpha"},
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

### Known-broken cases

See [Marking known-broken cases (xfail)](#marking-known-broken-cases-xfail) for the rationale and semantics.

- **`expectFail(reason)`** — context manager. A `FAIL` inside the block is reported as `XFAIL` (and swallowed); if every check inside passes, the block is reported as `XPASS` (and the suite fails). Only `TestFailed` is swallowed; other exceptions still propagate as `ERROR`.
- **`expectTestFails(reason)`** — mark the entire current test as expected-to-fail. Same semantics as `expectFail`, applied to the whole test.

### Output grouping

- **`sectionBegin(msg)`** / **`sectionEnd()`** — wrap a group of checks with a labeled banner.
- **`variantBegin(msg)`** / **`variantEnd()`** — wrap a sub-block within a section, typically used to run the same logic with different inputs.

### Suite-level setup and teardown

Intended for use from a `--setup` or `--teardown` script. See [Suite-level setup and teardown](#suite-level-setup-and-teardown) for the lifecycle.

- **`exportEnv(name, value)`** — set an env var that every test (and teardown) in this run can read.
- **`setState(key, value)`** — record a JSON-serializable value for teardown to read back later.
- **`getState(key, default=None)`** — read a value set by `setState`. Returns `default` when the key was never set.

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
