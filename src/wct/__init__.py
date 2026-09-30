# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Please follow the established pattern and keep the imports
# alphabetized (logically, not pedantically)

import atexit
import codecs
import contextlib
import io
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import textwrap
import threading
import time

from colorama import Fore, Style, init as _colorama_init

from ._workspace import getStateFilePath

# Initialize colorama at import so any consumer importing the API gets working
# color output without needing to call init() themselves. Safe to call repeatedly.
_colorama_init()


##############################################################################
# Public exception used to signal a single failing test
##############################################################################

class TestFailed(Exception):
    """Raised when a check fails. Caught at the per-test boundary in the runner
    so one failing test does not terminate the whole run."""
    pass


##############################################################################
# Internal utilities for formatted output
##############################################################################

_g_indentLevel = 1

def _doIndentString() -> str :
    global _g_indentLevel
    return "    " * _g_indentLevel


def _resetIndentLevel(level: int = 1) :
    """Reset indent state between tests. Called by the runner; not part of the
    test-facing API. The runner passes a deeper level to nest a per-test
    hook's output under its header."""
    global _g_indentLevel
    _g_indentLevel = level


##############################################################################
# Internal scope state (variants + sections)
##############################################################################

# A "scope" is a named span opened by variantBegin or sectionBegin and closed
# by the matching End call. When a test uses scopes, the runner emits one
# JUnit testcase per scope rather than one per file, giving GitLab's Tests tab
# the granularity to surface individual sub-tests by their section/variant
# names. Scopes nest: each stack entry records its own start time, label,
# and kind. Closed scopes are appended to _g_scopeResults in close order;
# the runner consumes that list after each test.

_g_scopeStack = []
_g_scopeResults = []


def _resetScopeState() :
    """Reset scope bookkeeping between tests. Called by the runner."""
    global _g_scopeStack, _g_scopeResults
    _g_scopeStack = []
    _g_scopeResults = []


def _getScopeResults() :
    """Return a snapshot of closed-scope outcomes for the current test."""
    return list(_g_scopeResults)


def _currentScopePath() -> str :
    """Joined label path of currently-open scopes, for naming the testcase
    that will own a not-yet-recorded outcome."""
    return " / ".join(s["label"] for s in _g_scopeStack)


def _pushScope(label: str, kind: str) :
    _g_scopeStack.append({"label": label, "kind": kind, "startTime": time.monotonic()})


def _popScopeAsPassed() :
    """Pop the innermost open scope and record it as a passing testcase.
    Called from variantEnd / sectionEnd. A stray End with no matching Begin
    (test author bug) is ignored rather than raising — we don't want to
    obscure a real failure with a runner exception."""
    if not _g_scopeStack :
        return
    scope = _g_scopeStack.pop()
    _g_scopeResults.append({
        "scopePath": " / ".join(s["label"] for s in _g_scopeStack + [scope]),
        "duration": time.monotonic() - scope["startTime"],
        "status": "passed",
        "message": "",
    })


def _closeInnermostScopeAs(status: str, message: str) :
    """Close the innermost open scope as the given status, recording it as a
    testcase result. Outer open scopes are discarded without emitting a
    separate testcase — their content is the failing inner scope plus
    whatever closed cleanly inside them, both of which are already counted.
    No-op if no scope is open (the caller falls back to a file-level result)."""
    if not _g_scopeStack :
        return False
    scope = _g_scopeStack[-1]
    _g_scopeResults.append({
        "scopePath": " / ".join(s["label"] for s in _g_scopeStack),
        "duration": time.monotonic() - scope["startTime"],
        "status": status,
        "message": message,
    })
    _g_scopeStack.clear()
    return True


##############################################################################
# Internal xfail state
##############################################################################

# Each entry is {"outcome": "xfail" | "xpass", "reason": str}, recorded by the
# expectFail context manager as it exits. The runner reads this after the test
# returns to compute the test-level status. expectTestFails sets the
# whole-test reason; the runner consults it when the test ends in TestFailed
# (xfail) or without it (xpass).
_g_xfailBlocks = []
_g_xfailWholeTestReason = None


def _resetXfailState() :
    """Reset xfail bookkeeping between tests. Called by the runner."""
    global _g_xfailBlocks, _g_xfailWholeTestReason
    _g_xfailBlocks = []
    _g_xfailWholeTestReason = None


def _getXfailState() :
    """Return a snapshot of the current test's xfail state. The runner uses
    this to compute the test-level outcome (passed / failed / xfailed /
    xpassed)."""
    return {
        "blocks": list(_g_xfailBlocks),
        "wholeTestReason": _g_xfailWholeTestReason,
    }


##############################################################################
# Internal background-command registry
##############################################################################

# Every BackgroundCommand not yet stopped is listed here, tagged with its
# owner: "test" when a test (or a per-test hook) started it, "suite" when a
# --setup or --teardown script did. The runner stops a test's commands when
# that test ends and the suite's after teardown, so a test that fails or
# errors before stopping its server cannot leave it running, holding a port.
_g_backgroundCommands = []
_g_backgroundOwner = "test"


def _setBackgroundOwner(owner: str) :
    """Set the owner recorded for commands started from now on: "suite"
    around setup and teardown, "test" around tests. Called by the runner."""
    global _g_backgroundOwner
    _g_backgroundOwner = owner


def _stopBackgroundCommands(owner=None) :
    """Stop the registered background commands of the given owner, or all of
    them. Called by the runner; not part of the test-facing API."""
    for bg in [b for b in _g_backgroundCommands if owner is None or b._owner == owner] :
        # One command that cannot be stopped must not keep the runner from
        # stopping the rest, or from reporting.
        try :
            bg.stop()
        except Exception as e :
            print(f"{_doIndentString()}    {Fore.RED}ERROR: could not stop background command "
                  f"{bg.cmd}: {e}{Style.RESET_ALL}")
            if bg in _g_backgroundCommands :
                _g_backgroundCommands.remove(bg)


def _killBackgroundCommands() :
    """Kill every registered background command's process tree at once,
    without waiting or printing. For the runner's emergency-abort path (a
    second Ctrl-C), which runs inside a signal handler: waiting on a Popen
    there could deadlock against the interrupted main thread, and printing
    could re-enter a write already in progress."""
    for bg in list(_g_backgroundCommands) :
        _killProcessTree(bg._popen.pid)


# Normal runs stop everything explicitly; this covers wct being used outside
# the runner and abnormal exits. Registered after _workspace's cleanup, so it
# runs first (atexit is LIFO): processes stop before their cwd is deleted.
atexit.register(_stopBackgroundCommands)


##############################################################################
# Internal snapshot of per-test bookkeeping (for retryUntilPass)
##############################################################################

# A failed retryUntilPass attempt may have opened scopes, closed some, bumped
# the indent, recorded xfail blocks or started background commands. Rolling
# that back before the next attempt keeps a section inside the retried
# function from nesting inside itself ("probe / probe") or being counted once
# per attempt, and a server it starts from running once per attempt.

def _snapshotTestState() :
    return {
        "indentLevel": _g_indentLevel,
        "scopeStack": list(_g_scopeStack),
        "scopeResultCount": len(_g_scopeResults),
        "xfailBlockCount": len(_g_xfailBlocks),
        "xfailWholeTestReason": _g_xfailWholeTestReason,
        "backgroundCommands": list(_g_backgroundCommands),
    }


def _restoreTestState(snapshot) :
    global _g_indentLevel, _g_xfailWholeTestReason
    _g_indentLevel = snapshot["indentLevel"]
    _g_scopeStack[:] = snapshot["scopeStack"]
    del _g_scopeResults[snapshot["scopeResultCount"]:]
    del _g_xfailBlocks[snapshot["xfailBlockCount"]:]
    _g_xfailWholeTestReason = snapshot["xfailWholeTestReason"]
    for bg in [b for b in _g_backgroundCommands if b not in snapshot["backgroundCommands"]] :
        bg._stop(announce=False)


##############################################################################
# Internal type-check utilities
##############################################################################

def _isString(v) -> bool :
    return isinstance(v, str)


def _isListOfStrings(v) -> bool :
    if hasattr(v, '__len__') and not isinstance(v, str) :
        for x in v :
            if not _isString(x) :
                return False
        return True
    return False


def _isListOfJsonFields(v) -> bool :
    if not hasattr(v, '__len__') :
        return False
    for x in v :
        if not isinstance(x, dict) :
            return False
        if "field" not in x or "test_value" not in x :
            return False
        if x.get("test_type") not in ("unorderedArrayMatch", "arraySize", "valueEqual", "valueNotEqual") :
            return False
    return True


def _isStringOrList(v) -> bool :
    return _isString(v) or _isListOfStrings(v)


def _isInteger(n) -> bool :
    # Booleans are technically ints in Python; exclude them so True/False
    # cannot be silently accepted as a returncode value.
    return isinstance(n, int) and not isinstance(n, bool)


def _isPositiveNumber(n) -> bool :
    # Accept int or float seconds. Exclude bool (a bool is an int subclass) and
    # require strictly positive — a zero or negative timeout would kill the
    # command instantly, which is never what a test author means.
    return isinstance(n, (int, float)) and not isinstance(n, bool) and n > 0


def _isEnvDict(v) -> bool :
    # Variable names map to a string value, or to None to remove the variable.
    if not isinstance(v, dict) :
        return False
    for name, value in v.items() :
        if not _isString(name) or name == "" :
            return False
        if value is not None and not _isString(value) :
            return False
    return True


def _isStringOrBytes(v) -> bool :
    return isinstance(v, (str, bytes))


##############################################################################
# Internal regex matching helpers
##############################################################################

def _matchBasic(pattern, theString) -> tuple[bool, str] :
    return re.search(pattern, theString, flags=re.MULTILINE) is not None, pattern


def _matchAll(patternList, theString) -> tuple[bool, str] :
    if _isListOfStrings(patternList) :
        for x in patternList :
            ret, pat = _matchBasic(x, theString)
            if not ret :
                return False, pat
        return True, "All"
    else :
        return _matchBasic(patternList, theString)


def _matchOne(patternList, theString) -> tuple[bool, str] :
    if _isListOfStrings(patternList) :
        for x in patternList :
            ret, pat = _matchBasic(x, theString)
            if ret :
                return True, pat
        return False, "None"
    else :
        return _matchBasic(patternList, theString)


##############################################################################
# Suite-wide command timeout default
##############################################################################

# Default per-command timeout (seconds) applied to every checkRunCommand when
# the descriptor does not set its own 'timeout'. None means "no timeout" — the
# historical behavior. The runner sets this once from the --timeout CLI flag
# before the test loop; it deliberately persists across tests (it is a
# suite-wide default, not per-test state) so there is no reset hook.
_g_defaultTimeout = None


def _setDefaultTimeout(seconds) :
    """Set the suite-wide default command timeout. Called by the runner from
    the --timeout CLI flag. Not part of the test-facing API."""
    global _g_defaultTimeout
    _g_defaultTimeout = seconds


##############################################################################
# Internal command-descriptor validation
##############################################################################

def _endTest() :
    raise TestFailed()


# Table of recognised keys in a checkRunCommand testvals dict. Each entry maps
# the key name to (validator, human description). A None value for any key is
# always accepted (treated as 'not set'). Length-having values must also be
# non-empty, except for the keys in _DESCRIPTOR_EMPTY_OK.
_DESCRIPTOR_VALIDATORS = {
    "cmd":                   (_isListOfStrings,    "a non-empty list of strings"),
    "timeout":               (_isPositiveNumber,   "a positive number of seconds"),
    "env":                   (_isEnvDict,          "a dict mapping variable names to strings, or to None to remove them"),
    "stdin":                 (_isStringOrBytes,    "a string or bytes"),
    "expect_stdout":         (_isStringOrList,     "a non-empty string or list of strings"),
    "dontexpect_stdout":     (_isStringOrList,     "a non-empty string or list of strings"),
    "expect_stderr":         (_isStringOrList,     "a non-empty string or list of strings"),
    "dontexpect_stderr":     (_isStringOrList,     "a non-empty string or list of strings"),
    "expect_returncode":     (_isInteger,          "an integer"),
    "dontexpect_returncode": (_isInteger,          "an integer"),
    "check_json_stdout":     (_isListOfJsonFields, "a non-empty list of JSON field tests"),
}

# An empty stdin is a meaningful input (the child sees EOF at once), and an
# empty env is a harmless no-op that a test building its overrides
# programmatically produces naturally, e.g. removing only those suite
# variables that happen to be set.
_DESCRIPTOR_EMPTY_OK = {"env", "stdin"}


def _validateCommandStruct(v, allowedKeys=None) -> bool :
    """Validate a command descriptor. allowedKeys narrows the recognised keys
    to a subset of _DESCRIPTOR_VALIDATORS (startBackgroundCommand takes only
    the launch keys); None allows them all."""
    if not isinstance(v, dict) :
        print("WARNING: invalid command descriptor. Must be a dict.")
        return False
    for key, val in v.items() :
        if key not in _DESCRIPTOR_VALIDATORS or (allowedKeys is not None and key not in allowedKeys) :
            print(f"    WARN: Unrecognized entry '{key}' found.")
            return False
        if val is None :
            continue
        check, desc = _DESCRIPTOR_VALIDATORS[key]
        if not check(val) :
            print(f"    WARN: '{key}' must be {desc}.")
            return False
        if hasattr(val, '__len__') and len(val) == 0 and key not in _DESCRIPTOR_EMPTY_OK :
            print(f"    WARN: '{key}' must be {desc} (got empty).")
            return False
    return True


def _childEnv(overrides) :
    """The environment for a child process: the runner's own environment with
    the descriptor's 'env' overrides merged over it, where a value of None
    removes the variable. Returns None when there are no overrides, which
    subprocess takes to mean 'inherit' — exactly the behavior without the key.
    The runner's os.environ is never modified."""
    if overrides is None :
        return None
    env = os.environ.copy()
    for name, value in overrides.items() :
        # Windows variable names are case-insensitive, and os.environ.copy()
        # there yields upper-cased names. Match that, so that overriding or
        # removing "Path" acts on the inherited "PATH" rather than adding a
        # second, differently-cased entry.
        if os.name == "nt" :
            name = name.upper()
        if value is None :
            env.pop(name, None)
        else :
            env[name] = value
    return env


def _commandFound(cmd, useShell, childEnv) -> bool :
    """Whether cmd[0] can be found before trying to launch it, since the
    subprocess functions do not deal with a missing executable gracefully.
    Always true in shell mode, because cmd[0] may legitimately contain shell
    syntax (pipelines, redirects, etc.) that shutil.which cannot resolve.
    Looks where the launch will look: subprocess searches the child's PATH on
    POSIX, but CreateProcess on Windows searches the runner's own."""
    if useShell :
        return True
    whichPath = None
    if childEnv is not None and os.name != "nt" :
        whichPath = childEnv.get("PATH", os.defpath)
    return shutil.which(cmd[0], path=whichPath) is not None


##############################################################################
# Internal process-tree termination (for background commands)
##############################################################################

# A background command runs as the leader of its own process group on POSIX
# (start_new_session), so signalling the group reaches everything it started,
# e.g. the real server behind a launcher script. On Windows, taskkill /T walks
# the tree from the command's PID instead.

def _signalGroup(pgid, sig) -> bool :
    """Send sig to a POSIX process group. False once the group is gone. A
    PermissionError means the ID now belongs to someone else's process, which
    is as gone as far as this command is concerned."""
    try :
        os.killpg(pgid, sig)
        return True
    except (ProcessLookupError, PermissionError) :
        return False


def _killProcessTree(pid) :
    """Kill a background command's whole tree at once, without waiting."""
    if os.name == "nt" :
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else :
        _signalGroup(pid, signal.SIGKILL)


def _terminateProcessTree(popen, timeout) :
    """Stop a background command and everything it started, then reap it."""
    if os.name == "nt" :
        # There is no portable graceful stop for a Windows console process
        # that is not attached to our console, so this is a hard kill.
        _killProcessTree(popen.pid)
    else :
        # Ask the whole group to exit, and give it (not just the leader) until
        # the timeout. Polling the leader reaps it once it exits, so that its
        # zombie does not keep the group looking alive; then kill whatever of
        # the group remains.
        deadline = time.monotonic() + timeout
        if _signalGroup(popen.pid, signal.SIGTERM) :
            while time.monotonic() < deadline :
                popen.poll()
                if not _signalGroup(popen.pid, 0) :
                    break
                time.sleep(0.05)
        _killProcessTree(popen.pid)
    try :
        popen.wait(timeout=max(timeout, 5))
    except subprocess.TimeoutExpired :
        popen.kill()
        popen.wait()


##############################################################################
# Internal filesystem and JSON helpers
##############################################################################

def _funcDeleteRw(action, name, exc) :
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)


# A path segment is an optional field name followed by any number of [N]
# indexes. A segment with no field name ("[0]") indexes the current value
# directly — that's what makes a bare top-level array addressable. Indexes
# may be negative (Python semantics).
_JSON_PATH_SEGMENT = re.compile(r'([^\[\]]*)((?:\[-?\d+\])*)')
_JSON_PATH_INDEX = re.compile(r'\[(-?\d+)\]')


def _findJsonField(jsonString: str, fieldSpec: str) -> tuple[bool, object] :
    # Return (False, None) on non-JSON input rather than letting JSONDecodeError
    # bubble up. checkRunCommand also validates JSON once up front so the user
    # gets a single clear "not valid JSON" message instead of a flood of
    # "invalid field" messages.
    try :
        data = json.loads(jsonString)
    except json.JSONDecodeError :
        return False, None

    # An empty field spec addresses the root value itself — the only way to
    # run arraySize/unorderedArrayMatch against a bare top-level array.
    if fieldSpec == "" :
        return True, data

    currentValue = data
    for segment in fieldSpec.split('.') :
        m = _JSON_PATH_SEGMENT.fullmatch(segment)
        if segment == "" or m is None :
            return False, None
        fieldName = m.group(1)
        if fieldName != "" :
            if not isinstance(currentValue, dict) or fieldName not in currentValue :
                return False, None
            currentValue = currentValue[fieldName]
        for indexText in _JSON_PATH_INDEX.findall(m.group(2)) :
            index = int(indexText)
            if not isinstance(currentValue, list) or not (-len(currentValue) <= index < len(currentValue)) :
                return False, None
            currentValue = currentValue[index]
    return True, currentValue


##############################################################################
# Public functions for generating regex
##############################################################################

def xEscape(v: str) -> str :
    return re.escape(v)


def xAnywhere(v: str) -> str :
    """No-op marker: returns v unchanged. Use to document intent that a regex
    is meant to match anywhere in the output."""
    return v


def xAnywhereSameLine(v1: str, v2: str) -> str :
    return v1 + r".*" + v2


def xAnywhereConsecutiveLines(v1: str, v2: str) -> str :
    return v1 + r".*\r?\n.*" + v2


def xFullLine(v: str) -> str :
    return r"^" + v + r"\r?\n"


def xLastFullLine(v: str) -> str :
    return xFullLine(v) + r"\Z"


def xBeginningOfLine(v: str) -> str :
    return r"^" + v


##############################################################################
# Public functions for writing and controlling tests
##############################################################################

def operatingSystem() -> str :
    return platform.system()


def deleteFolder(name: str) :
    shutil.rmtree(name, onerror=_funcDeleteRw)


def failTest(message: str) :
    """Fail the current test with the given message. Does not return."""
    print(f"{_doIndentString()}    {Fore.RED}FAIL: ({message}){Style.RESET_ALL}")
    raise TestFailed(message)


def passTest(message: str) :
    """Log an informational pass. Does not terminate the test. Useful when you
    want to record a passing checkpoint that does not fit any of the check*
    functions; unlike failTest this is for logging only, not assertion."""
    print(f"{_doIndentString()}    {Fore.GREEN}PASS: ({message}){Style.RESET_ALL}")


def checkTrue(condition, message: str) :
    """Assert a condition computed in Python. Prints a PASS line with the
    message when the condition is truthy; otherwise fails the test with it.
    Use for custom checks that no check* function covers, so that a passing
    result still shows up in the report."""
    if condition :
        passTest(message)
    else :
        failTest(message)


def checkEqual(actual, expected, message: str) :
    """Assert that a value computed in Python equals the expected one. Like
    checkTrue, but a failure also shows both values."""
    if actual == expected :
        passTest(message)
    else :
        failTest(f"{message} [got {actual!r}, expected {expected!r}]")


def checkRunCommand(testvals: dict, useShell: bool = False) -> tuple[int, str, str] :
    firstfail = True
    def firstFailFunc() :
        nonlocal firstfail
        if firstfail :
            firstfail = False
            print(f"{_doIndentString()}    {Fore.RED}FAIL: {testvals['cmd']}{Style.RESET_ALL}")

    def entryExists(k: str) -> bool :
        return k in testvals and testvals[k] is not None

    # If the descriptor itself is malformed there is no point running anything.
    # Validation prints any per-key warnings before we get here.
    if not _validateCommandStruct(testvals) :
        firstFailFunc()
        print("        invalid test command descriptor")
        _endTest()

    childEnv = _childEnv(testvals.get("env"))

    if not _commandFound(testvals["cmd"], useShell, childEnv) :
        firstFailFunc()
        print(f"{_doIndentString()}        {Fore.RED}BAD:  command not found '{testvals['cmd'][0]}'{Style.RESET_ALL}")
        _endTest()

    # subprocess.run with shell=True expects a single command string, not a
    # list. Passing a list with shell=True silently runs cmd[0] as the script
    # with cmd[1:] as positional args to the shell, which is never what the
    # caller wants. Join to a string so shell features like pipes and
    # redirects work as expected.
    cmdToRun = " ".join(testvals["cmd"]) if useShell else testvals["cmd"]

    # Resolve the effective timeout: a per-command 'timeout' wins over the
    # suite-wide default set from --timeout; None means wait forever (the
    # historical behavior). A hung command otherwise stalls the whole suite,
    # which is especially costly on CI.
    effectiveTimeout = testvals["timeout"] if entryExists("timeout") else _g_defaultTimeout

    # 'stdin' is written to the child's stdin, which is then closed, so a
    # child that reads to EOF finishes. Without the key the child inherits the
    # runner's stdin, as it always has. Text goes as UTF-8, the encoding the
    # child's output is decoded with.
    stdinData = testvals.get("stdin")
    if isinstance(stdinData, str) :
        stdinData = stdinData.encode("utf-8")

    try :
        result = subprocess.run(cmdToRun, capture_output=True, shell=useShell,
                                timeout=effectiveTimeout, env=childEnv, input=stdinData)
    except subprocess.TimeoutExpired :
        # subprocess.run kills the direct child before re-raising. With
        # shell=True a pipeline's grandchildren can outlive the shell — that
        # narrower case is a documented subprocess limitation we don't paper
        # over here.
        firstFailFunc()
        print(f"{_doIndentString()}        {Fore.RED}BAD:  timed out after {effectiveTimeout}s{Style.RESET_ALL}")
        _endTest()

    stdoutText = result.stdout.decode('utf-8')
    stderrText = result.stderr.decode('utf-8')

    oklist = []

    if entryExists("expect_returncode") :
        if result.returncode != testvals["expect_returncode"] :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  expect_returncode [got {result.returncode}, expected {testvals['expect_returncode']}]{Style.RESET_ALL}")
        else :
            oklist.append("expect_returncode")

    if entryExists("dontexpect_returncode") :
        if result.returncode == testvals["dontexpect_returncode"] :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  dontexpect_returncode{Style.RESET_ALL}")
        else :
            oklist.append("dontexpect_returncode")

    if entryExists("expect_stdout") :
        ret, pat = _matchAll(testvals["expect_stdout"], stdoutText)
        if not ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  expect_stdout [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else :
            oklist.append("expect_stdout")

    if entryExists("check_json_stdout") :
        # Validate stdout is JSON once, up front, so a non-JSON stdout produces
        # a single clear message instead of a flood of "invalid field" lines.
        jsonValid = True
        try :
            json.loads(stdoutText)
        except json.JSONDecodeError as e :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [stdout is not valid JSON: {e.msg}]{Style.RESET_ALL}")
            jsonValid = False

        if jsonValid :
            allOk = True
            for ftest in testvals["check_json_stdout"] :
                ftestField = ftest['field']
                ftestType = ftest['test_type']
                ftestValue = ftest['test_value']

                resultFieldExists, resultFieldValue = _findJsonField(stdoutText, ftestField)
                if resultFieldExists :
                    if ftestType == "unorderedArrayMatch" :
                        if set(ftestValue) != set(resultFieldValue) :
                            firstFailFunc()
                            print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [sets do not match for field '{ftestField}']{Style.RESET_ALL}")
                            allOk = False
                    elif ftestType == "arraySize" :
                        if resultFieldValue is None :
                            if ftestValue != 0 :
                                firstFailFunc()
                                print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [array size is 0 for field '{ftestField}']{Style.RESET_ALL}")
                                allOk = False
                        elif ftestValue != len(resultFieldValue) :
                            firstFailFunc()
                            print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [array sizes do not match for field '{ftestField}']{Style.RESET_ALL}")
                            allOk = False
                    elif ftestType == "valueEqual" :
                        if ftestValue != resultFieldValue :
                            firstFailFunc()
                            print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [values do not match for field '{ftestField}']{Style.RESET_ALL}")
                            allOk = False
                    elif ftestType == "valueNotEqual" :
                        if ftestValue == resultFieldValue :
                            firstFailFunc()
                            print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [values match for field '{ftestField}']{Style.RESET_ALL}")
                            allOk = False
                    else :
                        firstFailFunc()
                        print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [invalid test type '{ftestType}']{Style.RESET_ALL}")
                        allOk = False
                else :
                    firstFailFunc()
                    print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [invalid field name '{ftest['field']}']{Style.RESET_ALL}")
                    allOk = False
            if allOk :
                oklist.append("check_json_stdout")

    if entryExists("dontexpect_stdout") :
        ret, pat = _matchOne(testvals["dontexpect_stdout"], stdoutText)
        if ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  dontexpect_stdout [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else :
            oklist.append("dontexpect_stdout")

    if entryExists("expect_stderr") :
        ret, pat = _matchAll(testvals["expect_stderr"], stderrText)
        if not ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  expect_stderr [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else :
            oklist.append("expect_stderr")

    if entryExists("dontexpect_stderr") :
        ret, pat = _matchOne(testvals["dontexpect_stderr"], stderrText)
        if ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  dontexpect_stderr [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else :
            oklist.append("dontexpect_stderr")

    if not firstfail :
        for x in oklist :
            print(f"{_doIndentString()}        {Fore.GREEN}OK:   {x}{Style.RESET_ALL}")

        if result.returncode != 0 :
            print(f"{_doIndentString()}        {Fore.RED}STDERR:{Style.RESET_ALL}")
            for line in stderrText.splitlines() :
                print(f"{_doIndentString()}            {line}")
            print(f"{_doIndentString()}        {Fore.RED}STDOUT:{Style.RESET_ALL}")
            for line in stdoutText.splitlines() :
                print(f"{_doIndentString()}            {line}")

        _endTest()

    print(f"{_doIndentString()}    {Fore.GREEN}PASS: {testvals['cmd']}{Style.RESET_ALL}")
    return result.returncode, stdoutText, stderrText


def checkRunShellCommand(testvals: dict) -> tuple[int, str, str] :
    return checkRunCommand(testvals, True)


# The descriptor keys startBackgroundCommand takes: how to launch the command.
# What to expect of it is asked afterwards, through waitForOutput.
_BACKGROUND_KEYS = ("cmd", "env")

# How much of a background command's output a failed waitForOutput shows.
_BACKGROUND_OUTPUT_TAIL_LINES = 100


class BackgroundCommand :
    """A command started by startBackgroundCommand, running alongside the
    test. Its stdout and stderr are captured together, as it writes them."""

    def __init__(self, cmd, popen, owner) :
        self.cmd = cmd
        self._popen = popen
        self._owner = owner
        self._cond = threading.Condition()
        self._text = ""
        self._eof = False
        self._cursor = 0
        # Drain the pipe continuously: otherwise a chatty command fills the OS
        # pipe buffer and blocks. Daemon, so it can never hold up exit.
        self._reader = threading.Thread(target=self._readOutput, daemon=True)
        self._reader.start()

    @property
    def pid(self) -> int :
        return self._popen.pid

    @property
    def returncode(self) :
        """The exit code once the command has exited, otherwise None."""
        return self._popen.poll()

    def isRunning(self) -> bool :
        return self._popen.poll() is None

    def output(self) -> str :
        """Everything the command has written so far, stdout and stderr
        interleaved as they arrived."""
        with self._cond :
            return self._text

    def _readOutput(self) :
        # Decode leniently: an undecodable byte in a server's log must not
        # kill the reader and leave the pipe to fill up.
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try :
            while True :
                data = self._popen.stdout.read1(65536)
                if not data :
                    break
                text = decoder.decode(data)
                with self._cond :
                    self._text += text
                    self._cond.notify_all()
        except (OSError, ValueError) :
            pass
        finally :
            with self._cond :
                self._text += decoder.decode(b"", final=True)
                self._eof = True
                self._cond.notify_all()

    def waitForOutput(self, pattern: str, timeout: float = 30) :
        """Wait until the command's output matches the regex pattern, and
        return the re.Match, so a value such as a port can be read from a
        group. Each successful wait consumes the output up to the end of its
        match, and the next wait looks only at what comes after it. Fails the
        test if timeout seconds pass, or the command exits, first."""
        regex = re.compile(pattern, flags=re.MULTILINE)
        deadline = time.monotonic() + timeout
        with self._cond :
            while True :
                match = regex.search(self._text, self._cursor)
                if match or self._eof :
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0 :
                    break
                self._cond.wait(remaining)
            text = self._text
            eof = self._eof

        if match :
            self._cursor = match.end()
            print(f"{_doIndentString()}    {Fore.GREEN}PASS: {self.cmd} output matched r\"{pattern}\"{Style.RESET_ALL}")
            return match

        if eof :
            # The output closes as the command exits; give the exit a moment
            # to become visible so the code can be reported.
            try :
                reason = f"exited with code {self._popen.wait(timeout=1)} before output matched r\"{pattern}\""
            except subprocess.TimeoutExpired :
                reason = f"closed its output before it matched r\"{pattern}\""
        else :
            reason = f"no match for r\"{pattern}\" within {timeout}s"
        print(f"{_doIndentString()}    {Fore.RED}FAIL: {self.cmd}{Style.RESET_ALL}")
        print(f"{_doIndentString()}        {Fore.RED}BAD:  waitForOutput [{reason}]{Style.RESET_ALL}")
        print(f"{_doIndentString()}        {Fore.RED}OUTPUT:{Style.RESET_ALL}")
        lines = text.splitlines()
        if len(lines) > _BACKGROUND_OUTPUT_TAIL_LINES :
            print(f"{_doIndentString()}            ({len(lines) - _BACKGROUND_OUTPUT_TAIL_LINES} earlier lines not shown)")
            lines = lines[-_BACKGROUND_OUTPUT_TAIL_LINES:]
        for line in lines :
            print(f"{_doIndentString()}            {line}")
        _endTest()

    def stop(self, timeout: float = 5) -> int :
        """Stop the command and everything it started, and return its exit
        code. On POSIX it is sent SIGTERM and killed if it has not exited
        within timeout seconds; on Windows it is killed at once. Stopping a
        command that has already stopped or exited just returns its code."""
        self._stop(timeout)
        return self._popen.returncode

    def _stop(self, timeout: float = 5, announce: bool = True) :
        wasRunning = self._popen.poll() is None
        # Even when the command itself has exited, what it started may not
        # have, so the tree is always terminated.
        _terminateProcessTree(self._popen, timeout)
        self._reader.join(timeout=1)
        if self in _g_backgroundCommands :
            _g_backgroundCommands.remove(self)
        if announce and wasRunning :
            print(f"{_doIndentString()}    {Fore.YELLOW}Stopped background command: {self.cmd}{Style.RESET_ALL}")


def startBackgroundCommand(testvals: dict, useShell: bool = False) -> BackgroundCommand :
    """Start a long-running command, such as a server the test talks to, and
    return a BackgroundCommand for it without waiting. The descriptor takes
    'cmd' and 'env' as checkRunCommand does; stdin is empty. The command runs
    until stopped: by BackgroundCommand.stop, or by the runner when the test
    that started it ends (for a --setup or --teardown script, when the run
    ends), whether the test passed, failed or errored."""
    if not _validateCommandStruct(testvals, _BACKGROUND_KEYS) :
        print(f"{_doIndentString()}    {Fore.RED}FAIL: {testvals.get('cmd')}{Style.RESET_ALL}")
        print("        invalid background command descriptor")
        _endTest()

    childEnv = _childEnv(testvals.get("env"))
    if not _commandFound(testvals["cmd"], useShell, childEnv) :
        print(f"{_doIndentString()}    {Fore.RED}FAIL: {testvals['cmd']}{Style.RESET_ALL}")
        print(f"{_doIndentString()}        {Fore.RED}BAD:  command not found '{testvals['cmd'][0]}'{Style.RESET_ALL}")
        _endTest()

    # Joined for the shell, as in checkRunCommand. Its own process group (see
    # _terminateProcessTree) also keeps a Ctrl-C at the terminal from reaching
    # it directly; the runner stops it instead.
    cmdToRun = " ".join(testvals["cmd"]) if useShell else testvals["cmd"]
    if os.name == "nt" :
        groupArgs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    else :
        groupArgs = {"start_new_session": True}
    try :
        popen = subprocess.Popen(cmdToRun, shell=useShell, env=childEnv,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, **groupArgs)
    except OSError as e :
        print(f"{_doIndentString()}    {Fore.RED}FAIL: {testvals['cmd']}{Style.RESET_ALL}")
        print(f"{_doIndentString()}        {Fore.RED}BAD:  could not start [{e}]{Style.RESET_ALL}")
        _endTest()

    bg = BackgroundCommand(testvals["cmd"], popen, _g_backgroundOwner)
    _g_backgroundCommands.append(bg)
    print(f"{_doIndentString()}    {Fore.YELLOW}Started background command: {testvals['cmd']} (pid {popen.pid}){Style.RESET_ALL}")
    return bg


def checkPathExists(fn: str) :
    if os.path.exists(fn) :
        passTest(f"File exists - '{fn}'")
    else :
        failTest(f"File missing - '{fn}'")


def checkPathNotExists(fn: str) :
    if not os.path.exists(fn) :
        passTest(f"File missing - '{fn}'")
    else :
        failTest(f"File exists - '{fn}'")


def checkFileWriteable(fn: str) :
    if os.access(fn, os.W_OK) :
        passTest(f"File writeable - '{fn}'")
    else :
        failTest(f"File not writeable - '{fn}'")


def checkFileReadOnly(fn: str) :
    if not os.access(fn, os.W_OK) :
        passTest(f"File read only - '{fn}'")
    else :
        failTest(f"File writeable - '{fn}'")


def retryUntilPass(fn, timeout, interval: float = 1.0) :
    """Call fn (with no arguments) until it returns without a failed check, or
    until timeout seconds have passed, and return what fn returned. For checks
    that pass only once the system under test settles, such as a command that
    flaps while a service registers.

    Output of failed attempts is suppressed. A pass on the first attempt looks
    exactly like calling fn directly; a later pass also notes the attempt
    count. When no attempt passes, the last attempt's output is shown and its
    failure fails the test. Waits interval seconds between attempts and starts
    none after the timeout. Only a failed check is retried: any other
    exception propagates at once, as a broken test rather than a flap."""
    if not _isPositiveNumber(timeout) :
        failTest("retryUntilPass: timeout must be a positive number of seconds")
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval < 0 :
        failTest("retryUntilPass: interval must be a non-negative number of seconds")

    noteIndent = _doIndentString()
    startTime = time.monotonic()
    deadline = startTime + timeout
    attempt = 0
    while True :
        attempt += 1
        snapshot = _snapshotTestState()
        captured = io.StringIO()
        try :
            with contextlib.redirect_stdout(captured) :
                result = fn()
        except TestFailed as e :
            failure = e
        except BaseException :
            # Not a flap: show what the attempt printed and let it propagate.
            print(captured.getvalue(), end="")
            raise
        else :
            if attempt > 1 :
                print(f"{noteIndent}    {Fore.YELLOW}Retry: passed on attempt {attempt} "
                      f"after {time.monotonic() - startTime:.1f}s{Style.RESET_ALL}")
            print(captured.getvalue(), end="")
            return result

        if time.monotonic() + interval >= deadline :
            break
        _restoreTestState(snapshot)
        time.sleep(interval)

    # The last attempt's state is left as it failed, so that, as for a direct
    # call, the runner attributes the failure to any scope it left open.
    print(f"{noteIndent}    {Fore.YELLOW}Retry: gave up after {attempt} attempts over "
          f"{time.monotonic() - startTime:.1f}s; last attempt:{Style.RESET_ALL}")
    print(captured.getvalue(), end="")
    raise failure


class expectFail :
    """Context manager that marks a block of checks as "known broken". A FAIL
    inside the block is swallowed and reported as XFAIL (test continues, suite
    exit code is not affected). If the block runs without any FAIL the
    outcome is XPASS — the bug appears fixed and the wrapper should be
    removed; XPASS counts as a suite failure.

    Only TestFailed is treated as the expected failure. Other exceptions
    propagate normally and are reported as ERROR; an unhandled exception
    indicates a broken test, not a known bug."""

    def __init__(self, reason: str) :
        self._reason = reason

    def __enter__(self) :
        global _g_indentLevel
        print(f"{_doIndentString()}    {Fore.YELLOW}Expecting failure: {self._reason}{Style.RESET_ALL}")
        _g_indentLevel += 1
        return self

    def __exit__(self, excType, excVal, tb) :
        global _g_indentLevel, _g_xfailBlocks
        _g_indentLevel -= 1
        if excType is TestFailed :
            _g_xfailBlocks.append({"outcome": "xfail", "reason": self._reason})
            print(f"{_doIndentString()}    {Fore.YELLOW}XFAIL: {self._reason}{Style.RESET_ALL}")
            return True
        if excType is None :
            _g_xfailBlocks.append({"outcome": "xpass", "reason": self._reason})
            print(f"{_doIndentString()}    {Fore.RED}XPASS: {self._reason} "
                  f"- bug appears fixed, remove the expectFail wrapper{Style.RESET_ALL}")
            return False
        # Any other exception (test error, KeyboardInterrupt, etc.) propagates
        # untouched; an unhandled exception means a broken test, not a known bug.
        return False


def expectTestFails(reason: str) :
    """Mark the entire current test as expected-to-fail. If the test ends in
    TestFailed the outcome is XFAIL; if the test ends without any FAIL the
    outcome is XPASS (and the suite fails). Call this near the top of the
    test; the marker stays in effect until the test ends."""
    global _g_xfailWholeTestReason
    _g_xfailWholeTestReason = reason
    print(f"{_doIndentString()}    {Fore.YELLOW}Expecting test to fail: {reason}{Style.RESET_ALL}")


def variantBegin(msg: str) :
    global _g_indentLevel
    print(f"{_doIndentString()}    {Fore.YELLOW}Executing variant: {msg}{Style.RESET_ALL}")
    _g_indentLevel += 1
    _pushScope(msg, "variant")


def variantEnd() :
    global _g_indentLevel
    _g_indentLevel -= 1
    _popScopeAsPassed()


def sectionBegin(msg: str) :
    global _g_indentLevel
    print(f"{Fore.BLUE}{indentAndWrap(msg, _doIndentString() + '    ', 72)}{Style.RESET_ALL}")
    _g_indentLevel += 1
    _pushScope(msg, "section")


def sectionEnd() :
    global _g_indentLevel
    _g_indentLevel -= 1
    _popScopeAsPassed()


def indentAndWrap(inputString: str, indentPrefix: str, maxLineLength: int = 72) -> str :
    # Replace both Unix-style and Windows-style line breaks with spaces
    inputString = inputString.replace('\n', ' ').replace('\r', '')

    # Remove leading space if it was originally a line break
    inputString = inputString.lstrip()

    wrappedLines = textwrap.wrap(inputString, width=maxLineLength - len(indentPrefix))
    outputLines = [indentPrefix + line for line in wrappedLines]
    return '\n'.join(outputLines)


##############################################################################
# Public functions for suite-level setup/teardown scripts
##############################################################################

def exportEnv(name: str, value: str) :
    """Make an env var visible to every test (and to teardown) for this wct run.
    Dies with the wct process; does not leak back into the user's shell."""
    os.environ[name] = value


def setState(key: str, value) :
    """Record a JSON-serializable value for teardown to read via getState.
    Flushed to disk per call so a partial-setup failure leaves usable state."""
    path = getStateFilePath()
    path.parent.mkdir(parents=True, exist_ok=True)
    try :
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) :
        data = {}
    data[key] = value
    # Write-then-rename so a crash mid-write cannot corrupt the file teardown reads.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, path)


def getState(key: str, default=None) :
    """Read a value recorded by setState. Returns default when the key was never
    set or when setup never ran far enough to create the state file."""
    path = getStateFilePath()
    try :
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) :
        return default
    return data.get(key, default)
