import re
import subprocess

lastStatus = False

##############################################################################
# Useful utilities used internall in this module but also available to the 
# user when writing tests
##############################################################################

def isString(v) :
    return isinstance(v, str)


def isListOfStrings(v) :
    if hasattr(v, '__len__') and (not isinstance(v, str)):
        for x in v :
            if not isString(x) :
                return False
        return True
    return False


def isStringOrList(v) :
    return isString(v) or isListOfStrings(v)


def isInteger(n) :
    if isinstance(n, int):
        return True
    if isinstance(n, float):
        return n.is_integer()
    return False


def matchBasic(pattern, theString):
    return re.search(pattern, theString, flags=re.MULTILINE) is not None


def matchAll(patternList, theString) :
    if isListOfStrings(patternList) :
        for x in patternList:
            if not matchBasic(x, theString) :
                return False
        return True
    else:
        return matchBasic(patternList, theString)


def matchOne(patternList, theString) :
    if isListOfStrings(patternList) :
        for x in patternList:
            if matchBasic(x, theString) :
                return True
        return False
    else:
        return matchBasic(patternList, theString)


def xFullLine(v) :
    return r"^" + re.escape(v) + r"\r?\n"


def xLastFullLine(v) :
    return xFullLine(v) + r"\Z"


def xBeginningOfLine(v) :
    return r"^" + re.escape(v)


##############################################################################
# Core functions for writing/controlling tests
##############################################################################

def endTest(status : bool):
    lastStatus = True
    quit()


def validateCommandStruct(v) :
    if not isinstance(v, dict) :
        print(f"WARNING: invalid command descriptor. Must be a dict.")
        return False

    for k in v :
        match k:
            case "cmd" :
                if v[k] is not None and (not isListOfStrings(v[k]) or len(v[k]) == 0) :
                    print(f"    WARN: Must have a valid 'cmd' value which contains a list of strings.")
                    return False

            case "expect_stdout" :
                if v[k] is not None and (not isStringOrList(v[k]) or len(v[k]) == 0) :
                    print(f"    WARN: If 'expect_stdout' is not None, it must be a valid string, or list of strings.")
                    return False

            case "dontexpect_stdout" :
                if v[k] is not None and (not isStringOrList(v[k]) or len(v[k]) == 0) :
                    print(f"    WARN: If 'dontexpect_stdout' is not None, it must be a valid string, or list of strings.")
                    return False

            case "expect_stderr" :
                if v[k] is not None and (not isStringOrList(v[k]) or len(v[k]) == 0) :
                    print(f"    WARN: If 'expect_stderr' is not None, it must be a valid string, or list of strings.")
                    return False

            case "dontexpect_stderr" :
                if v[k] is not None and (not isStringOrList(v[k]) or len(v[k]) == 0) :
                    print(f"    WARN: If 'dontexpect_stderr' is not None, it must be a valid string, or list of strings.")
                    return False

            case "expect_returncode" :
                if v[k] is not None and (not isInteger(v[k])) :
                    print(f"    WARN: If 'expect_returncode' is not None, it must be a valid integer.")
                    return False

            case "dontexpect_returncode" :
                if v[k] is not None and (not isInteger(v[k])) :
                    print(f"    WARN: If 'dontexpect_returncode' is not None, it must be a valid integer.")
                    return False

            case _:
                print(f"    WARN: Unrecognized entry '{k}' found. ")
                return False

    return True


def runCommand(testvals) :
    firstfail = True
    def firstFailFunc() :
        nonlocal firstfail
        if firstfail:
            firstfail = False
            print(f"    FAIL: {testvals['cmd']}")

    def entryExists(k) :
        nonlocal testvals
        return k in testvals and testvals[k] is not None

    # If the command descriptor is invalid, we have not choice but to fail right away.
    # However, if its valid, we run through all the checks before failing so that the
    # user can get a list of all the errors at once.

    if not validateCommandStruct(testvals) :
        firstFailFunc()
        print(f"        invalid test command descriptor")
        endTest(False)

    result = subprocess.run(testvals["cmd"], capture_output=True)

    oklist = []
    if entryExists("expect_returncode") :
        if result.returncode != testvals["expect_returncode"] :
            firstFailFunc()
            print(f"        BAD:  expect_returncode [got {result.returncode}, expected {testvals['expect_returncode']}]")
        else:
            oklist.append("expect_returncode")

    if entryExists("dontexpect_returncode") :
        if result.returncode == testvals["dontexpect_returncode"] :
            firstFailFunc()
            print(f"        BAD:  dontexpect_returncode")
        else:
            oklist.append("dontexpect_returncode")

    if entryExists("expect_stdout") :
        if not matchAll(testvals["expect_stdout"], result.stdout.decode('utf-8')):
            firstFailFunc()
            print(f"        BAD:  expect_stdout")
        else:
            oklist.append("expect_stdout")

    if entryExists("dontexpect_stdout") :
        if matchOne(testvals["dontexpect_stdout"], result.stdout.decode('utf-8')) :
            firstFailFunc()
            print(f"        BAD:  dontexpect_stdout")
        else:
            oklist.append("dontexpect_stdout")

    if entryExists("expect_stderr") :
        if not matchAll(testvals["expect_stderr"], result.stderr.decode('utf-8')):
            firstFailFunc()
            print(f"        BAD:  expect_stderr")
        else:
            oklist.append("expect_stderr")

    if entryExists("dontexpect_stderr") :
        if matchOne(testvals["dontexpect_stderr"], result.stderr.decode('utf-8')):
            firstFailFunc()
            print(f"        BAD:  dontexpect_stderr")
        else:
            oklist.append("dontexpect_stderr")

    if not firstfail :
        for x in oklist :
            print(f"        OK:   {x}")

        endTest(False)

    print(f"    PASS: {testvals['cmd']}")

