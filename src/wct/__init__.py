# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Please follow the established pattern and keep the imports
# alphabetized (logically, not pedantically)

import json
import os
import platform
import re
import shutil
import stat
import subprocess
import textwrap

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


def _resetIndentLevel() :
    """Reset indent state between tests. Called by the runner; not part of the
    test-facing API."""
    global _g_indentLevel
    _g_indentLevel = 1


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
# Internal command-descriptor validation
##############################################################################

def _endTest() :
    raise TestFailed()


# Table of recognised keys in a checkRunCommand testvals dict. Each entry maps
# the key name to (validator, human description). A None value for any key is
# always accepted (treated as 'not set'). Length-having values must also be
# non-empty.
_DESCRIPTOR_VALIDATORS = {
    "cmd":                   (_isListOfStrings,    "a non-empty list of strings"),
    "expect_stdout":         (_isStringOrList,     "a non-empty string or list of strings"),
    "dontexpect_stdout":     (_isStringOrList,     "a non-empty string or list of strings"),
    "expect_stderr":         (_isStringOrList,     "a non-empty string or list of strings"),
    "dontexpect_stderr":     (_isStringOrList,     "a non-empty string or list of strings"),
    "expect_returncode":     (_isInteger,          "an integer"),
    "dontexpect_returncode": (_isInteger,          "an integer"),
    "check_json_stdout":     (_isListOfJsonFields, "a non-empty list of JSON field tests"),
}


def _validateCommandStruct(v) -> bool :
    if not isinstance(v, dict) :
        print("WARNING: invalid command descriptor. Must be a dict.")
        return False
    for key, val in v.items() :
        if key not in _DESCRIPTOR_VALIDATORS :
            print(f"    WARN: Unrecognized entry '{key}' found.")
            return False
        if val is None :
            continue
        check, desc = _DESCRIPTOR_VALIDATORS[key]
        if not check(val) :
            print(f"    WARN: '{key}' must be {desc}.")
            return False
        if hasattr(val, '__len__') and len(val) == 0 :
            print(f"    WARN: '{key}' must be {desc} (got empty).")
            return False
    return True


##############################################################################
# Internal filesystem and JSON helpers
##############################################################################

def _funcDeleteRw(action, name, exc) :
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)


def _findJsonField(jsonString: str, fieldSpec: str) -> tuple[bool, object] :
    # Return (False, None) on non-JSON input rather than letting JSONDecodeError
    # bubble up. checkRunCommand also validates JSON once up front so the user
    # gets a single clear "not valid JSON" message instead of a flood of
    # "invalid field" messages.
    try :
        data = json.loads(jsonString)
    except json.JSONDecodeError :
        return False, None

    currentValue = data
    for field in fieldSpec.split('.') :
        if '[' in field and ']' in field :
            fieldName, arrayIndex = field.split('[')
            arrayIndex = int(arrayIndex.replace(']', ''))
            if fieldName in currentValue and isinstance(currentValue[fieldName], list) and len(currentValue[fieldName]) > arrayIndex :
                currentValue = currentValue[fieldName][arrayIndex]
            else :
                return False, None
        elif field in currentValue :
            currentValue = currentValue[field]
        else :
            return False, None
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

    # The executable might not be found and subprocess.run does not deal with
    # that gracefully. Skip the existence check in shell mode because cmd[0]
    # may legitimately contain shell syntax (pipelines, redirects, etc.)
    # that shutil.which cannot resolve.
    if not useShell and not shutil.which(testvals["cmd"][0]) :
        firstFailFunc()
        print(f"{_doIndentString()}        {Fore.RED}BAD:  command not found '{testvals['cmd'][0]}'{Style.RESET_ALL}")
        _endTest()

    # subprocess.run with shell=True expects a single command string, not a
    # list. Passing a list with shell=True silently runs cmd[0] as the script
    # with cmd[1:] as positional args to the shell, which is never what the
    # caller wants. Join to a string so shell features like pipes and
    # redirects work as expected.
    cmdToRun = " ".join(testvals["cmd"]) if useShell else testvals["cmd"]
    result = subprocess.run(cmdToRun, capture_output=True, shell=useShell)

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
                  f"— bug appears fixed, remove the expectFail wrapper{Style.RESET_ALL}")
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


def variantEnd() :
    global _g_indentLevel
    _g_indentLevel -= 1


def sectionBegin(msg: str) :
    global _g_indentLevel
    print(f"{Fore.BLUE}{indentAndWrap(msg, _doIndentString() + '    ', 72)}{Style.RESET_ALL}")
    _g_indentLevel += 1


def sectionEnd() :
    global _g_indentLevel
    _g_indentLevel -= 1


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
