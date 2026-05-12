# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Please follow the established pattern and keep the imports
# alphabetized (logically, not pedantically)

import argparse
import glob
import os
import runpy
import signal
import sys
import time
import traceback

from colorama import Fore, Style
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from . import TestFailed, _resetIndentLevel
from ._workspace import getRunRoot, getStateFilePath, resetRunRoot


def _parseArgs() :
    parser = argparse.ArgumentParser(
        description="Automated black-box testing for CLI programs. "
                    "Glob patterns supported by 'testname' are rails/golang style; "
                    "'**' is intended to match arbitrary subdirectories."
    )
    parser.add_argument('testname', type=str, nargs='+',
                        help='path to test; can be a glob pattern')
    parser.add_argument('-p', '--path', type=str,
                        help='path to prepend to PATH when searching for executables')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show more status messages while executing')
    parser.add_argument('--junit', type=str, metavar='FILE',
                        help='write a JUnit XML report to FILE on completion')
    parser.add_argument('--setup', type=str, metavar='PATH',
                        help='script to run once before any tests')
    parser.add_argument('--teardown', type=str, metavar='PATH',
                        help='script to run once after all tests (runs even if setup or tests failed)')
    return parser.parse_args()


def _expandTests(patterns) :
    expanded = []
    for pat in patterns :
        # recursive=True makes '**' match arbitrary subdirectories, matching the
        # rails/golang-style semantics the README has always documented.
        for v in glob.glob(pat, recursive=True) :
            expanded.append(v)
    return expanded


def _testName(displayPath) :
    return os.path.splitext(os.path.basename(displayPath))[0]


def _testClassname(displayPath) :
    # GitLab CI groups testcases by classname. Use just the immediate parent
    # directory name, defaulting to 'wct' for tests with no parent component.
    parent = os.path.basename(os.path.dirname(displayPath))
    return parent or "wct"


def _writeJunit(path, results) :
    failures = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["status"] == "errored")
    totalTime = sum(r["duration"] for r in results)

    suites = Element("testsuites")
    suite = SubElement(suites, "testsuite", attrib={
        "name": "wct",
        "tests": str(len(results)),
        "failures": str(failures),
        "errors": str(errors),
        "time": f"{totalTime:.3f}",
    })
    for r in results :
        case = SubElement(suite, "testcase", attrib={
            "name": r["name"],
            "classname": r["classname"],
            "time": f"{r['duration']:.3f}",
        })
        if r["status"] == "failed" :
            fail = SubElement(case, "failure", attrib={
                "message": r["message"] or "check failed",
                "type": "TestFailed",
            })
            fail.text = r["message"]
        elif r["status"] == "errored" :
            err = SubElement(case, "error", attrib={
                "message": (r["message"].splitlines()[0] if r["message"] else "unexpected exception"),
                "type": "Exception",
            })
            err.text = r["message"]

    parent = os.path.dirname(path)
    if parent :
        os.makedirs(parent, exist_ok=True)
    ElementTree(suites).write(path, encoding="utf-8", xml_declaration=True)


# Module-global so the SIGINT handler can flip it without ceremony.
_g_stopFlag = False


def _installSigintHandler() :
    """First Ctrl-C sets a flag; the test loop checks it between tests and
    breaks out so teardown still gets to run. A second Ctrl-C restores the
    default handler and re-raises, giving the user an emergency abort path
    (matching the doc: 'a second Ctrl-C or SIGKILL skips teardown')."""
    def handler(sig, frame) :
        global _g_stopFlag
        if _g_stopFlag :
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGINT)
            return
        _g_stopFlag = True
        print(f"\n{Fore.YELLOW}Interrupted; stopping after current test, then running teardown. "
              f"Press Ctrl-C again to abort.{Style.RESET_ALL}", file=sys.stderr)
    signal.signal(signal.SIGINT, handler)


def _runPath(absPath) :
    """Wrap runpy.run_path so the script's directory is on sys.path for the
    duration of the call, mirroring how `python script.py` makes a sibling
    `from helpers import X` just work. On exit, restore sys.path AND drop any
    modules loaded from scriptDir — restoring sys.path alone is not enough
    because Python's sys.modules cache would still mask a same-named sibling
    in a different test directory on the next invocation."""
    scriptDir = os.path.dirname(absPath)
    prevPath = list(sys.path)
    prevModules = set(sys.modules)
    sys.path.insert(0, scriptDir)
    try :
        runpy.run_path(absPath, run_name="__main__")
    finally :
        sys.path[:] = prevPath
        for name in [n for n in sys.modules if n not in prevModules] :
            mod = sys.modules.get(name)
            modFile = getattr(mod, "__file__", None) if mod is not None else None
            if not modFile :
                continue
            modDir = os.path.dirname(os.path.abspath(modFile))
            if modDir == scriptDir or modDir.startswith(scriptDir + os.sep) :
                del sys.modules[name]


def _runScript(displayPath, absPath, header, name, classname) -> dict :
    """Run a setup or teardown script using the same in-process runpy mechanism
    as tests, but without a workspace reset — these scripts run in the caller's
    cwd so they can manage paths outside the per-PID workspace."""
    _resetIndentLevel()
    print(f"    {Fore.YELLOW}{header} '{Path(displayPath).as_posix()}'{Style.RESET_ALL}")

    status = "passed"
    message = ""
    startTime = time.monotonic()

    try :
        _runPath(absPath)
    except TestFailed as e :
        status = "failed"
        message = str(e)
    except SystemExit as e :
        if e.code not in (0, None) :
            status = "failed"
            message = f"sys.exit({e.code!r})"
    except Exception :
        status = "errored"
        message = traceback.format_exc()
        print(f"    {Fore.RED}ERROR: {header.lower()} raised an unexpected exception{Style.RESET_ALL}",
              file=sys.stderr)
        traceback.print_exc()

    duration = time.monotonic() - startTime
    return {
        "name": name,
        "classname": classname,
        "duration": duration,
        "status": status,
        "message": message,
    }


def _printScriptOutcome(label, result) :
    if result["status"] == "passed" :
        print(f"{label}: {Fore.GREEN}PASS{Style.RESET_ALL}")
    elif result["status"] == "failed" :
        print(f"{label}: {Fore.RED}FAIL{Style.RESET_ALL}")
    else :
        print(f"{label}: {Fore.RED}ERROR{Style.RESET_ALL}")


def main() -> int :
    args = _parseArgs()

    if args.path :
        os.environ["PATH"] = args.path + os.pathsep + os.environ.get("PATH", "")

    if args.verbose :
        print("Configuration:")
        print(f"    workroot: {getRunRoot()}")
        print(f"    testnames: {args.testname}")
        if args.path :
            print(f"    path prepend: {args.path}")
        if args.junit :
            print(f"    junit output: {args.junit}")
        if args.setup :
            print(f"    setup: {args.setup}")
        if args.teardown :
            print(f"    teardown: {args.teardown}")

    tests = _expandTests(args.testname)
    if not tests :
        print(f"{Fore.RED}No tests matched.{Style.RESET_ALL}", file=sys.stderr)
        return 2

    # Resolve test paths to absolute now, before the loop body chdirs into the
    # workspace. Doing this inside the loop would resolve later iterations
    # relative to the workspace, and the test file would appear missing.
    testsAbs = [(t, os.path.abspath(t)) for t in tests]

    # Same reasoning for the junit/setup/teardown paths: resolve against the
    # caller's cwd, not the workspace we are about to chdir into.
    junitPath = os.path.abspath(args.junit) if args.junit else None
    setupAbs = os.path.abspath(args.setup) if args.setup else None
    teardownAbs = os.path.abspath(args.teardown) if args.teardown else None
    callerCwd = Path.cwd()

    # Drop any leftover state.json from a hard-killed prior wct that happened
    # to share this PID. Belt-and-braces; atexit handles the normal case.
    try :
        getStateFilePath().unlink()
    except FileNotFoundError :
        pass

    _installSigintHandler()

    setupResult = None
    teardownResult = None
    testResults = []

    if setupAbs :
        os.chdir(callerCwd)
        setupResult = _runScript(args.setup, setupAbs, "Running setup",
                                 "__suite_setup__", "wct.suite")

    setupFailed = setupResult is not None and setupResult["status"] != "passed"

    if setupFailed :
        # Skip the test loop, but mark each collected test as errored so the
        # JUnit report and summary reflect that nothing in the suite ran.
        for displayPath, _ in testsAbs :
            testResults.append({
                "name": _testName(displayPath),
                "classname": _testClassname(displayPath),
                "duration": 0.0,
                "status": "errored",
                "message": "suite setup failed; test did not run",
            })
    else :
        for displayPath, absTest in testsAbs :
            if _g_stopFlag :
                break

            # Clean workspace and chdir into it so the test starts from a known empty cwd.
            workspace = resetRunRoot()
            os.chdir(workspace)

            # Tests can leave the indent counter unbalanced (e.g. variantBegin without
            # variantEnd). Reset so the next test's output is not corrupted.
            _resetIndentLevel()

            print(f"    {Fore.YELLOW}Running test '{Path(displayPath).as_posix()}'{Style.RESET_ALL}")

            status = "passed"
            message = ""
            startTime = time.monotonic()

            try :
                _runPath(absTest)
            except TestFailed as e :
                status = "failed"
                message = str(e)
            except SystemExit as e :
                if e.code not in (0, None) :
                    status = "failed"
                    message = f"sys.exit({e.code!r})"
            except Exception :
                status = "errored"
                message = traceback.format_exc()
                print(f"    {Fore.RED}ERROR: test raised an unexpected exception{Style.RESET_ALL}",
                      file=sys.stderr)
                traceback.print_exc()

            duration = time.monotonic() - startTime

            testResults.append({
                "name": _testName(displayPath),
                "classname": _testClassname(displayPath),
                "duration": duration,
                "status": status,
                "message": message,
            })

    if teardownAbs :
        os.chdir(callerCwd)
        teardownResult = _runScript(args.teardown, teardownAbs, "Running teardown",
                                    "__suite_teardown__", "wct.suite")

    passed = sum(1 for r in testResults if r["status"] == "passed")
    failed = sum(1 for r in testResults if r["status"] == "failed")
    errored = sum(1 for r in testResults if r["status"] == "errored")
    total = len(testResults)

    print()
    if setupResult is not None :
        _printScriptOutcome("Setup   ", setupResult)
    if teardownResult is not None :
        _printScriptOutcome("Teardown", teardownResult)

    summary = f"{passed}/{total} passed"
    if failed :
        summary += f", {Fore.RED}{failed} failed{Style.RESET_ALL}"
    if errored :
        summary += f", {Fore.RED}{errored} errored{Style.RESET_ALL}"
    print(summary)

    if junitPath :
        allResults = []
        if setupResult is not None :
            allResults.append(setupResult)
        allResults.extend(testResults)
        if teardownResult is not None :
            allResults.append(teardownResult)
        _writeJunit(junitPath, allResults)

    teardownFailed = teardownResult is not None and teardownResult["status"] != "passed"
    if setupFailed or failed or errored or teardownFailed or _g_stopFlag :
        return 1
    return 0


if __name__ == "__main__" :
    sys.exit(main())
