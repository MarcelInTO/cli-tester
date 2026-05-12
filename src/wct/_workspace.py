# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Please follow the established pattern and keep the imports
# alphabetized (logically, not pedantically)

import atexit
import os
import shutil
import stat

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


def _cleanupPerRunBase() :
    if _perRunBase.exists() :
        _stepOutOfWorkspace()
        shutil.rmtree(_perRunBase, onerror=_onDeleteRw)


atexit.register(_cleanupPerRunBase)


def getRunRoot() -> Path :
    """The single per-run workspace directory. Currently shared across all tests
    in a run and wiped between them; per-test isolation is a future polish item."""
    return _perRunBase / "runroot"


def resetRunRoot() -> Path :
    """Wipe and recreate the workspace. Returns the workspace path."""
    root = getRunRoot()
    _stepOutOfWorkspace()
    if root.exists() :
        if root.is_dir() :
            shutil.rmtree(root, onerror=_onDeleteRw)
        else :
            raise RuntimeError(f"'{root}' exists but is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    return root
