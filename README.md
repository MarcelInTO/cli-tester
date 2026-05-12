# WCT — CLI Tester

A black-box test runner for command-line programs. Tests are plain Python scripts that import helper functions from the `wct` module and call them; the first failed check stops that test, but other tests still run.

## Install

WCT requires Python 3.10 or later. The recommended installer is [uv](https://docs.astral.sh/uv/), which manages its own Python — you don't need to install one separately:

```sh
uv tool install wct
```

For development against a local checkout:

```sh
uv tool install --editable /path/to/cli-tester
```

`pipx` and `pip` will also work — `pyproject.toml` is standard.

## Running tests

```
wct <test_path_or_glob> [<test_path_or_glob> ...] [-p PATH] [-v]
```

- Multiple paths or globs can be listed on one command line.
- `**` in a glob matches arbitrary subdirectories (rails/golang style).
- `-p PATH` prepends to `$PATH` when running the executables under test — handy when testing a locally-built binary.
- `-v` prints additional configuration / progress output.

Each test runs in a clean workspace under `~/.cache/wct/`. The workspace is wiped between tests, so tests cannot rely on prior state.

Exit codes: `0` if all tests passed, `1` if any test failed or errored, `2` if no tests matched the given paths.

### Machine-readable output

`--junit FILE` writes a JUnit XML report on completion, suitable for GitLab CI's `artifacts:reports:junit` (and similar Jenkins, GitHub Actions, CircleCI consumers).

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
- **`passTest(message)`** — log a passing assertion. Does not terminate the test.
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
