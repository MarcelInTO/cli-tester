# Please follow the established pattern and keep the imports
# alphabetized (logically, not pedantically)

import argparse
import glob
import os
import runpy
import sys
import time
import traceback

from colorama import Fore, Style
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from . import TestFailed, _resetIndentLevel
from ._workspace import getRunRoot, resetRunRoot


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

    tests = _expandTests(args.testname)
    if not tests :
        print(f"{Fore.RED}No tests matched.{Style.RESET_ALL}", file=sys.stderr)
        return 2

    # Resolve test paths to absolute now, before the loop body chdirs into the
    # workspace. Doing this inside the loop would resolve later iterations
    # relative to the workspace, and the test file would appear missing.
    testsAbs = [(t, os.path.abspath(t)) for t in tests]

    # Same reasoning for the junit output path: resolve against the caller's
    # cwd, not the workspace we are about to chdir into.
    junitPath = os.path.abspath(args.junit) if args.junit else None

    results = []

    for displayPath, absTest in testsAbs :

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
            runpy.run_path(absTest, run_name="__main__")
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

        results.append({
            "name": _testName(displayPath),
            "classname": _testClassname(displayPath),
            "duration": duration,
            "status": status,
            "message": message,
        })

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    errored = sum(1 for r in results if r["status"] == "errored")
    total = len(results)

    print()
    summary = f"{passed}/{total} passed"
    if failed :
        summary += f", {Fore.RED}{failed} failed{Style.RESET_ALL}"
    if errored :
        summary += f", {Fore.RED}{errored} errored{Style.RESET_ALL}"
    print(summary)

    if junitPath :
        _writeJunit(junitPath, results)

    return 0 if (failed == 0 and errored == 0) else 1


if __name__ == "__main__" :
    sys.exit(main())
