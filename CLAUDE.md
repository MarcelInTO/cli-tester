# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

WCT is a black-box test runner for command-line programs. It *is* the test infrastructure, and has a meta-test suite under `tests/` that exercises wct using wct. There is no separate build or lint step — run the meta-tests via `wct 'tests/test_*.py'`.

Tests are plain Python files that `from wct import ...` and call check functions. The first failed check raises `TestFailed`, which the runner catches at the per-test boundary so other tests still run.

## Running

```
wct <test_path_or_glob> [<test_path_or_glob> ...] [-p PATH] [-v] [--setup PATH] [--teardown PATH]
```

Globs use `**` to match arbitrary subdirectories. The runner exits `0` on full pass, `1` if anything failed or errored, `2` if no tests matched.

## Architecture

- **`src/wct/__init__.py`** — the test API surface. Tests `from wct import ...` and call check functions. The failure model: each `check*` prints a FAIL line, then calls `_endTest` which raises `TestFailed`. Output indentation is tracked by a module-global `_g_indentLevel` and reset between tests by `_resetIndentLevel`. Also exports the suite-level helpers used by `--setup` / `--teardown` scripts: `exportEnv` (env var that propagates to every test) and `setState` / `getState` (write-through state channel routed through a JSON file — deliberately *not* placed in the environment so it stays invisible to tests that don't ask for it).
- **`src/wct/cli.py`** — the `wct` entry point. Parses args, glob-expands test paths, then loops in-process: reset workspace, `chdir` into it, reset indent, `runpy.run_path(testfile, run_name="__main__")` via the `_runPath` wrapper, catch `TestFailed`/`SystemExit`/`Exception`. `_runPath` prepends the script's directory to `sys.path` for the duration of the call (so `from helpers import X` works for a sibling module, matching `python script.py`) and on exit drops any modules loaded from that directory — restoring `sys.path` alone would not be enough because Python's `sys.modules` cache would otherwise mask a same-named sibling in a different test directory on the next test. Summarizes counts and returns a non-zero exit code if anything failed. When `--setup` / `--teardown` are present, those scripts run via the same `runpy` mechanism but in the caller's cwd (not a per-test workspace), bracketing the test loop. Teardown always runs — even on setup failure (every collected test is then reported as errored) and on SIGINT. A SIGINT handler flips a stop-flag the loop checks between tests so teardown still gets to clean up; a second SIGINT restores the default handler and aborts.
- **`src/wct/_workspace.py`** — wipes and recreates the workspace at `~/.cache/wct/run-<pid>/runroot/`, and exposes `getStateFilePath()` returning `~/.cache/wct/run-<pid>/state.json` for the setup/teardown state channel. Both share the per-PID base, so the same `atexit` cleanup handles them. Two cross-platform invariants:
  - *Per-PID isolation*: the per-PID path segment ensures a wct subprocess (e.g. a meta-test invoking wct against a fixture) gets its own workspace and can't wipe the outer wct's. Without it, the outer's cwd becomes a stale inode on Linux and the inner's `rmtree` fails outright on Windows.
  - *Step out before deleting*: `_stepOutOfWorkspace()` chdir's to `Path.home()` before any `shutil.rmtree`. Windows refuses to delete a directory in use as cwd (WinError 32); Linux is lenient and silently leaves a stale inode. The chdir-out is required for Windows and harmless on Unix.

  An `atexit` hook cleans up the per-PID dir on normal exit. Hard kills (`taskkill /F` on Windows, `kill -9` on Unix) skip atexit and leak the dir.

A previous two-stage bootstrapper spawned a subprocess per test inside a self-managed venv. That pattern was inherited from another project (where it supported self-upgrade) and was deleted in the v0.2 restructure. Do not reintroduce it.

## Key conventions

- **Imports are kept alphabetized "logically, not pedantically"** — there's a comment to this effect at the top of every `.py` file. Preserve it when adding imports.
- **Output goes through the indent helper.** Never `print()` raw from API functions; route through `_doIndentString()` so the output of `variantBegin/End` and `sectionBegin/End` stays aligned.
- **Regex helpers do not escape their input.** `xAnywhere`, `xFullLine`, etc. expect the caller to have wrapped literal text in `xEscape` if needed. This lets the helpers nest and lets callers pass raw regex. Do not put escaping back inside the helpers.
- **Failure model is exception-based.** `check*` and `failTest` raise `TestFailed`. The diagnostic message is printed *before* raising — the exception itself is just the control-flow signal. Do not use `sys.exit()` or `quit()` from inside the API; either would terminate the whole runner, not just the current test.

## Intentional API asymmetries

The following look like inconsistencies but were reviewed in the step-7 API polish and deliberately preserved. Don't "fix" them in a future cleanup pass — each reflects a specific design choice:

- **`failTest` terminates, `passTest` doesn't.** They serve different purposes — `failTest` is an assertion that aborts on failure, `passTest` is informational logging. Pairing them via shared semantics would be wrong.
- **`checkRunCommand` returns `(rc, stdout, stderr)` only on success.** On failure it raises `TestFailed`. This is normal Python exception flow; the assignment in `rc, out, err = checkRunCommand(...)` is simply unreachable on failure, no separate handling needed.
- **`xAnywhere(v)` returns `v` unchanged.** Pure readability marker — documents intent that a regex is meant to match anywhere.
- **`xAnywhereSameLine(p1, p2)` and `xAnywhereConsecutiveLines(p1, p2)` are two-arg while siblings are one-arg.** The two-arg form honestly describes the relational operation; making them variadic would imply N-way relations they don't actually support.

## Workspace

`~/.cache/wct/run-<pid>/runroot/` (via `platformdirs.user_cache_dir` plus PID segment for nested-wct isolation; see the Architecture section). Wiped between every test. Tests cannot rely on prior state. Preserving the workspace of a failing test for inspection is a future polish item — currently if test 3 fails, test 4 wipes the evidence.

The setup/teardown state file (`~/.cache/wct/run-<pid>/state.json`) lives alongside `runroot/` in the per-PID base, so it is not affected by the per-test wipe but is cleaned up by the same `atexit` hook on normal exit.
