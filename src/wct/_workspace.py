# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Please follow the established pattern and keep the imports
# alphabetized (logically, not pedantically)

import atexit
import os
import shutil
import stat
import time

from pathlib import Path
from platformdirs import user_cache_dir


def _onDeleteRw(action, name, exc) :
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)


# Include the PID in the per-run base so that a wct subprocess invoked from
# inside a wct test (e.g. the meta-test suite) gets its own workspace and
# does not wipe the directory the outer wct is currently chdir'd into.
# Without this, the outer wct's cwd becomes a stale inode the moment the
# inner wct calls resetRunRoot, and relative-path operations afterward fail.
_perRunBase = Path(user_cache_dir("wct")) / f"run-{os.getpid()}"


def _stepOutOfWorkspace() :
    # Windows refuses to delete a directory that is anyone's current working
    # directory (WinError 32). The runner chdir's into the workspace before
    # running each test, so by the time we come around to reset it we are
    # standing in the directory we are about to delete. Step out to the user's
    # home (always exists, never the workspace) before any rmtree call.
    # Harmless on Unix, where deleting your own cwd just produces a stale inode.
    try :
        os.chdir(Path.home())
    except OSError :
        pass


def _rmtreeWithRetry(path) :
    # On Windows a process that has just been killed can keep its cwd (and
    # open files) in use for a moment while its termination completes, and
    # Windows refuses to delete a directory in use. That is the normal case
    # for the child of a background command stopped at the end of a test or
    # of the run: taskkill returns before the child is fully gone. Retry
    # briefly rather than let it abort the whole run.
    deadline = time.monotonic() + 3
    while True :
        try :
            shutil.rmtree(path, onerror=_onDeleteRw)
            return
        except OSError :
            if time.monotonic() >= deadline :
                raise
            time.sleep(0.1)


def _cleanupPerRunBase() :
    if _perRunBase.exists() :
        _stepOutOfWorkspace()
        _rmtreeWithRetry(_perRunBase)


atexit.register(_cleanupPerRunBase)


def getRunRoot() -> Path :
    """The single per-run workspace directory. Currently shared across all tests
    in a run and wiped between them; per-test isolation is a future polish item."""
    return _perRunBase / "runroot"


def getStateFilePath() -> Path :
    """Path to the JSON file used by setState/getState to ferry data from the
    suite-level setup script to teardown. Lives inside the per-PID base so it
    is naturally isolated from nested wct invocations and removed by the
    atexit cleanup on normal exit. The parent directory is created on demand
    by the first writer; readers may see a non-existent file before setup has
    written anything, which getState treats as 'no state yet'."""
    return _perRunBase / "state.json"


def resetRunRoot() -> Path :
    """Wipe and recreate the workspace. Returns the workspace path."""
    root = getRunRoot()
    _stepOutOfWorkspace()
    if root.exists() :
        if root.is_dir() :
            _rmtreeWithRetry(root)
        else :
            raise RuntimeError(f"'{root}' exists but is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    return root
