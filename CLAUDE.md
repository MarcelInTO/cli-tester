# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

WCT is a black-box test runner for command-line programs. It *is* the test infrastructure, and has a meta-test suite under `tests/` that exercises wct using wct. There is no separate build or lint step — run the meta-tests via `wct 'tests/test_*.py'`.

Tests are plain Python files that `from wct import ...` and call check functions. The first failed check raises `TestFailed`, which the runner catches at the per-test boundary so other tests still run.

## Running

```
wct <test_path_or_glob> [<test_path_or_glob> ...] [-p PATH] [-v] [--timeout SECONDS] [--junit FILE]
    [--setup PATH] [--teardown PATH] [--setup-each PATH] [--teardown-each PATH]
```

Globs use `**` to match arbitrary subdirectories. The runner exits `0` on full pass, `1` if anything failed or errored, `2` if no tests matched.

## Architecture

- **`src/wct/__init__.py`** — the test API surface. Tests `from wct import ...` and call check functions. The failure model: each `check*` prints a FAIL line, then calls `_endTest` which raises `TestFailed`. Output indentation is tracked by a module-global `_g_indentLevel` and reset between tests by `_resetIndentLevel`. `variantBegin`/`sectionBegin` and their `End` siblings also push/pop a module-global scope stack (`_g_scopeStack`); each closed scope appends to `_g_scopeResults`, which the runner reads after each test to emit per-scope JUnit testcases. When a test fails inside an open scope, the runner closes the innermost open scope with the failure and discards any outer open scopes (their content is the failing inner scope plus whatever closed cleanly inside them — already counted). `startBackgroundCommand` registers each `BackgroundCommand` in `_g_backgroundCommands`, tagged with the owner the runner set via `_setBackgroundOwner` ("test" or "suite"); the runner stops a test's commands when it ends and the rest after teardown. A command leads its own process group on POSIX (`start_new_session`) so stopping signals the whole group; on Windows `taskkill /T` walks the tree. A reader thread drains the merged stdout/stderr pipe continuously (a full pipe would block the child) and decodes leniently. Exit checks on a background command go through `_peekExitCode` (`os.waitid` with `WNOWAIT`), never `Popen.poll`/`wait`, until `stop` has sent its last group signal: the leader's PID is also the group ID, and reaping the leader early lets the kernel reuse that ID, so a later `killpg` could hit an unrelated process group. Don't "simplify" `isRunning`/`returncode` back to `poll()`. `retryUntilPass` snapshots the per-test bookkeeping (indent, scope stack and results, xfail state, background commands) before each attempt and restores it after a failed one — without that a section inside the retried function nests inside itself once per attempt. Also exports the suite-level helpers used by `--setup` / `--teardown` scripts: `exportEnv` (env var that propagates to every test) and `setState` / `getState` (write-through state channel routed through a JSON file — deliberately *not* placed in the environment so it stays invisible to tests that don't ask for it).
- **`src/wct/cli.py`** — the `wct` entry point. Parses args, glob-expands test paths, then loops in-process: reset workspace, `chdir` into it, reset indent, `runpy.run_path(testfile, run_name="__main__")` via the `_runPath` wrapper, catch `TestFailed`/`SystemExit`/`Exception`. `_runPath` prepends the script's directory to `sys.path` for the duration of the call (so `from helpers import X` works for a sibling module, matching `python script.py`) and on exit drops any modules loaded from that directory — restoring `sys.path` alone would not be enough because Python's `sys.modules` cache would otherwise mask a same-named sibling in a different test directory on the next test. Summarizes counts and returns a non-zero exit code if anything failed. When `--setup` / `--teardown` are present, those scripts run via the same `runpy` mechanism but in the caller's cwd (not a per-test workspace), bracketing the test loop. Teardown always runs — even on setup failure (every collected test is then reported as errored) and on SIGINT. `--setup-each` / `--teardown-each` run per test through `_runHook`, in the test's workspace, and the test's own results (xfail folding, scope attribution) are collected *before* teardown-each runs, since `_runHook` resets the per-test bookkeeping on both sides. A failed setup-each skips the test (errored); a failed teardown-each is appended as its own `<test>::__teardown_each__` row rather than relabeling the test. The test's background commands are stopped after teardown-each, so teardown-each can still use them. A SIGINT handler flips a stop-flag the loop checks between tests so teardown still gets to clean up; a second SIGINT kills background commands (their own process group means the terminal's Ctrl-C never reaches them), restores the default handler and aborts. That kill path runs inside the signal handler, so it only sends signals: waiting on a Popen there can deadlock against the interrupted main thread's hold on Popen's wait lock.
- **`src/wct/_workspace.py`** — wipes and recreates the workspace at `~/.cache/wct/run-<pid>/runroot/`, and exposes `getStateFilePath()` returning `~/.cache/wct/run-<pid>/state.json` for the setup/teardown state channel. Both share the per-PID base, so the same `atexit` cleanup handles them. Three cross-platform invariants:
  - *Per-PID isolation*: the per-PID path segment ensures a wct subprocess (e.g. a meta-test invoking wct against a fixture) gets its own workspace and can't wipe the outer wct's. Without it, the outer's cwd becomes a stale inode on Linux and the inner's `rmtree` fails outright on Windows.
  - *Step out before deleting*: `_stepOutOfWorkspace()` chdir's to `Path.home()` before any `shutil.rmtree`. Windows refuses to delete a directory in use as cwd (WinError 32); Linux is lenient and silently leaves a stale inode. The chdir-out is required for Windows and harmless on Unix.
  - *Retry the wipe*: `_rmtreeWithRetry` retries for up to 3s. `taskkill /T` returns before the processes it kills are gone, and background-command stop waits only for the command itself, so a child it started can still hold the workspace as its cwd when the next test's reset (or the atexit cleanup) deletes it.

  An `atexit` hook cleans up the per-PID dir on normal exit. Hard kills (`taskkill /F` on Windows, `kill -9` on Unix) skip atexit and leak the dir, and leave any background commands running.

A previous two-stage bootstrapper spawned a subprocess per test inside a self-managed venv. That pattern was inherited from another project (where it supported self-upgrade) and was deleted in the v0.2 restructure. Do not reintroduce it.

## Key conventions

- **Imports are kept alphabetized "logically, not pedantically"** — there's a comment to this effect at the top of every `.py` file. Preserve it when adding imports.
- **Output goes through the indent helper.** Never `print()` raw from API functions; route through `_doIndentString()` so the output of `variantBegin/End` and `sectionBegin/End` stays aligned.
- **Regex helpers do not escape their input.** `xAnywhere`, `xFullLine`, etc. expect the caller to have wrapped literal text in `xEscape` if needed. This lets the helpers nest and lets callers pass raw regex. Do not put escaping back inside the helpers.
- **Failure model is exception-based.** `check*` and `failTest` raise `TestFailed`. The diagnostic message is printed *before* raising — the exception itself is just the control-flow signal. Do not use `sys.exit()` or `quit()` from inside the API; either would terminate the whole runner, not just the current test.

## Intentional API asymmetries

The following look like inconsistencies but were deliberately chosen — in the step-7 API polish, or in 1.7.0 where marked. Don't "fix" them in a future cleanup pass — each reflects a specific design choice:

- **`failTest` terminates, `passTest` doesn't.** They serve different purposes — `failTest` is an assertion that aborts on failure, `passTest` is informational logging. Pairing them via shared semantics would be wrong.
- **`checkRunCommand` returns `(rc, stdout, stderr)` only on success.** On failure it raises `TestFailed`. This is normal Python exception flow; the assignment in `rc, out, err = checkRunCommand(...)` is simply unreachable on failure, no separate handling needed.
- **`xAnywhere(v)` returns `v` unchanged.** Pure readability marker — documents intent that a regex is meant to match anywhere.
- **`xAnywhereSameLine(p1, p2)` and `xAnywhereConsecutiveLines(p1, p2)` are two-arg while siblings are one-arg.** The two-arg form honestly describes the relational operation; making them variadic would imply N-way relations they don't actually support.
- **(1.7.0) Without a `stdin` key, `checkRunCommand` inherits the runner's stdin; a background command always gets an empty one.** Inheriting is the pre-1.7 behavior and existing tests rely on nothing else; a background process must never compete with the runner for the terminal.
- **(1.7.0) `waitForOutput` consumes output up to its match; `output()` returns everything.** A wait for the log line a command causes must not be satisfied by an older copy of that line.
- **(1.7.0) A failed teardown-each is its own `<test>::__teardown_each__` row, so the summary can count more rows than tests.** The test's checks passed or failed on their own merits and are not relabeled — the same reasoning that gives suite-level teardown its own row.
- **(1.7.0) `startBackgroundCommand` takes a descriptor dict, not kwargs, and accepts only `cmd` and `env`.** Same shape as `checkRunCommand` for consistency; `expect_*` keys are rejected because expectations are asked later, through `waitForOutput`.
- **(1.7.0) `env` and `stdin` may be empty, though every other length-having descriptor key must not be.** An empty stdin is an immediate EOF, and an empty env is what a test produces when it removes "whichever suite variables are set" and none are.

## Workspace

`~/.cache/wct/run-<pid>/runroot/` (via `platformdirs.user_cache_dir` plus PID segment for nested-wct isolation; see the Architecture section). Wiped between every test. Tests cannot rely on prior state. Preserving the workspace of a failing test for inspection is a future polish item — currently if test 3 fails, test 4 wipes the evidence.

The setup/teardown state file (`~/.cache/wct/run-<pid>/state.json`) lives alongside `runroot/` in the per-PID base, so it is not affected by the per-test wipe but is cleaned up by the same `atexit` hook on normal exit.

## Releasing

The version string lives in **two** places that must move together on every bump:

1. `version = "X.Y.Z"` in `pyproject.toml` (and the matching `uv.lock` entry).
2. The `@vX.Y.Z` install pins in `README.md` — currently four: the HTTPS example, the SSH example, and the `uv tool install` line in each of the two CI snippets (Install section and Continuous integration section).

The README pins point consumers at a real published tag, so they lag by design: bump them to the tag you are about to cut. Before committing a release, `grep -n '@v[0-9]' README.md` and confirm every hit matches the new version — the 1.4.0 bump missed this and shipped a README pointing at the superseded 1.3.0 tag. Then tag `vX.Y.Z`, push the tag, and cut the matching GitLab release.

## Mirroring

The repo is push-mirrored from studio.wevr.com (the source of truth) to a public GitHub copy at `github.com/MarcelInTO/cli-tester`. Never push to GitHub directly — the mirror overwrites divergent refs. Branch and tag changes, including deletions, propagate automatically; syncs are batched at roughly one per five minutes, so back-to-back changes may take an extra cycle. GitLab release objects do not propagate — GitHub shows tags only.
