import json
import os
import platform
import re
import shutil
import stat
import subprocess

from colorama import Fore, Back, Style
from typing import Tuple

##############################################################################
# Internal utilities for formatted output
##############################################################################

_g_indentLevel = 1

def _doIndentString() -> str :
    global _g_indentLevel
    ret = ""
    for x in range(_g_indentLevel) :
        ret += "    "
    return ret


##############################################################################
# Useful utilities used internally
##############################################################################

def _isString(v) :
    return isinstance(v, str)


def _isListOfStrings(v) :
    if hasattr(v, '__len__') and (not isinstance(v, str)):
        for x in v :
            if not _isString(x) :
                return False
        return True
    return False

def _isListOfJsonFields(v) :
    if hasattr(v, '__len__') :
        for x in v :
            if not isinstance(x, dict):
                return False
            if not "field" in x.keys() :
                return False
            if not "test_type" in x.keys() :
                return False
            else :
                if x["test_type"] not in ["unorderedArrayMatch", "arraySize", "valueEqual", "valueNotEqual"] :
                    return False
            if not "test_value" in x.keys() :
                return False
        return True
    return False

def _isStringOrList(v) :
    return _isString(v) or _isListOfStrings(v)


def _isInteger(n) :
    if isinstance(n, int):
        return True
    if isinstance(n, float):
        return n.is_integer()
    return False


def _matchBasic(pattern, theString) -> Tuple[bool, str]:
    return re.search(pattern, theString, flags=re.MULTILINE) is not None, pattern


def _matchAll(patternList, theString) -> Tuple[bool, str]:
    if _isListOfStrings(patternList) :
        for x in patternList:
            ret, pat =  _matchBasic(x, theString)
            if not ret :
                return False, pat
        return True, "All"
    else:
        return _matchBasic(patternList, theString)


def _matchOne(patternList, theString) :
    if _isListOfStrings(patternList) :
        for x in patternList:
            ret, pat =  _matchBasic(x, theString)
            if ret :
                return True, pat
        return False, "None"
    else:
        return _matchBasic(patternList, theString)


def _endTest(status : bool):
    quit()


def _validateCommandStruct(v) :
    if not isinstance(v, dict) :
        print(f"WARNING: invalid command descriptor. Must be a dict.")
        return False

    for k in v :
        if k == "cmd" :
            if v[k] is not None and (not _isListOfStrings(v[k]) or len(v[k]) == 0) :
                print(f"    WARN: Must have a valid 'cmd' value which contains a list of strings.")
                return False

        elif k == "expect_stdout" :
            if v[k] is not None and (not _isStringOrList(v[k]) or len(v[k]) == 0) :
                print(f"    WARN: If 'expect_stdout' is not None, it must be a valid string, or list of strings.")
                return False

        elif k == "check_json_stdout" :
            if v[k] is not None and (not _isListOfJsonFields(v[k]) or len(v[k]) == 0) :
                print(f"    WARN: If 'check_json_stdout' is not None, it must be a valid list of json field tests.")
                return False

        elif k == "dontexpect_stdout" :
            if v[k] is not None and (not _isStringOrList(v[k]) or len(v[k]) == 0) :
                print(f"    WARN: If 'dontexpect_stdout' is not None, it must be a valid string, or list of strings.")
                return False

        elif k ==  "expect_stderr" :
            if v[k] is not None and (not _isStringOrList(v[k]) or len(v[k]) == 0) :
                print(f"    WARN: If 'expect_stderr' is not None, it must be a valid string, or list of strings.")
                return False

        elif k ==  "dontexpect_stderr" :
            if v[k] is not None and (not _isStringOrList(v[k]) or len(v[k]) == 0) :
                print(f"    WARN: If 'dontexpect_stderr' is not None, it must be a valid string, or list of strings.")
                return False

        elif k == "expect_returncode" :
            if v[k] is not None and (not _isInteger(v[k])) :
                print(f"    WARN: If 'expect_returncode' is not None, it must be a valid integer.")
                return False

        elif k == "dontexpect_returncode" :
            if v[k] is not None and (not _isInteger(v[k])) :
                print(f"    WARN: If 'dontexpect_returncode' is not None, it must be a valid integer.")
                return False

        else :
            print(f"    WARN: Unrecognized entry '{k}' found. ")
            return False

    return True

def _funcDeleteRw(action, name, exc) :
    global stat
    os.chmod(name, stat.S_IWRITE)
    os.remove(name)

def _findJsonField(jsonString : str, fieldSpec : str):
    data = json.loads(jsonString)

    fieldNames = fieldSpec.split('.')
    currentValue = data
    for field in fieldNames:
        if '[' in field and ']' in field:
            fieldName, arrayIndex = field.split('[')
            arrayIndex = int(arrayIndex.replace(']', ''))
            if fieldName in currentValue and isinstance(currentValue[fieldName], list) and len(currentValue[fieldName]) > arrayIndex:
                currentValue = currentValue[fieldName][arrayIndex]
            else:
                return False, None
        elif field in currentValue:
            currentValue = currentValue[field]
        else:
            return False, None

    return True, currentValue

def _getJsonField(jsonString : str, field : str) -> str :
    exists, value = _findJsonField(jsonString, field)
    if exists :
        return value
    else:
        return ""

def _getJsonFieldExists(jsonString : str, field : str) -> bool :
    exists, value = _findJsonField(jsonString, field)
    return exists



##############################################################################
# Public functions for generating regex
##############################################################################

def xAnywhere(v) :
    return re.escape(v)

def xFullLine(v) :
    return r"^" + re.escape(v) + r"\r?\n"


def xLastFullLine(v) :
    return xFullLine(v) + r"\Z"


def xBeginningOfLine(v) :
    return r"^" + re.escape(v)


##############################################################################
# Core functions for writing/controlling tests
##############################################################################

def operatingSystem() -> str :
    global platform
    return platform.system()

def deleteFolder(name : str) :
    global shutil
    shutil.rmtree(name, onerror=_funcDeleteRw)



def failTest(message : str):
    print(f"{_doIndentString()}    {Fore.RED}FAIL: ({message}){Style.RESET_ALL}")
    quit()


def passTest(message : str) :
    print(f"{_doIndentString()}    {Fore.GREEN}PASS: ({message}){Style.RESET_ALL}")



def checkRunCommand(testvals, useShell = False) :
    firstfail = True
    def firstFailFunc() :
        nonlocal firstfail
        if firstfail:
            firstfail = False
            print(f"{_doIndentString()}    {Fore.RED}FAIL: {testvals['cmd']}{Style.RESET_ALL}")

    def entryExists(k) :
        nonlocal testvals
        return k in testvals and testvals[k] is not None

    # If the command descriptor is invalid, we have not choice but to fail right away.
    # However, if its valid, we run through all the checks before failing so that the
    # user can get a list of all the errors at once.

    if not _validateCommandStruct(testvals) :
        firstFailFunc()
        print(f"        invalid test command descriptor")
        _endTest(False)

    result = subprocess.run(testvals["cmd"], capture_output=True, shell=useShell)

    oklist = []
    if entryExists("expect_returncode") :
        if result.returncode != testvals["expect_returncode"] :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  expect_returncode [got {result.returncode}, expected {testvals['expect_returncode']}]{Style.RESET_ALL}")
        else:
            oklist.append("expect_returncode")

    if entryExists("dontexpect_returncode") :
        if result.returncode == testvals["dontexpect_returncode"] :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  dontexpect_returncode{Style.RESET_ALL}")
        else:
            oklist.append("dontexpect_returncode")

    if entryExists("expect_stdout") :
        ret, pat = _matchAll(testvals["expect_stdout"], result.stdout.decode('utf-8'))
        if not ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  expect_stdout [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else:
            oklist.append("expect_stdout")

    if entryExists("check_json_stdout") :
        allOk = True
        for ftest in testvals["check_json_stdout"] :
            ftestField = ftest['field']
            ftestType = ftest['test_type']
            ftestValue = ftest['test_value']

            resultFieldExists, resultFieldValue = _findJsonField(result.stdout.decode('utf-8'), ftestField)
            if resultFieldExists:
                if ftestType == "unorderedArrayMatch" :
                    if (set(ftestValue) != set(resultFieldValue)) :
                        firstFailFunc()
                        print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [sets do not match for field '{ftestField}'")
                        allOk = False
                elif ftestType == "arraySize" :
                    if (resultFieldValue is None) :
                        if ftestValue != 0:
                            firstFailFunc()
                            print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [array size is 0 for field '{ftestField}'")
                            allOk = False
                    elif (ftestValue != len(resultFieldValue)) :
                        firstFailFunc()
                        print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [array sizes do not match for field '{ftestField}'")
                        allOk = False
                elif ftestType == "valueEqual" :
                    if (ftestValue != resultFieldValue) :
                        firstFailFunc()
                        print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [values do not match for field '{ftestField}'")
                        allOk = False
                elif ftestType == "valueNotEqual" :
                    if (ftestValue == resultFieldValue) :
                        firstFailFunc()
                        print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [values match for field '{ftestField}'")
                        allOk = False
                else:
                    firstFailFunc()
                    print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [invalid test type '{ftestType}'")
                    allOk = False
            else:
                firstFailFunc()
                print(f"{_doIndentString()}        {Fore.RED}BAD:  check_json_stdout [invalid field name '{ftest['field']}'")
                allOk = False
        if allOk :
            oklist.append("check_json_stdout")


    if entryExists("dontexpect_stdout") :
        ret, pat = _matchOne(testvals["dontexpect_stdout"], result.stdout.decode('utf-8'))
        if  ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  dontexpect_stdout [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else:
            oklist.append("dontexpect_stdout")

    if entryExists("expect_stderr") :
        ret, pat = _matchAll(testvals["expect_stderr"], result.stderr.decode('utf-8'))
        if not ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  expect_stderr [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else:
            oklist.append("expect_stderr")

    if entryExists("dontexpect_stderr") :
        ret, pat = _matchOne(testvals["dontexpect_stderr"], result.stderr.decode('utf-8'))
        if ret :
            firstFailFunc()
            print(f"{_doIndentString()}        {Fore.RED}BAD:  dontexpect_stderr [failed regex r\"{pat}\"]{Style.RESET_ALL}")
        else:
            oklist.append("dontexpect_stderr")

    if not firstfail :
        for x in oklist :
            print(f"{_doIndentString()}        {Fore.GREEN}OK:   {x}{Style.RESET_ALL}")

        _endTest(False)

    print(f"{_doIndentString()}    {Fore.GREEN}PASS: {testvals['cmd']}{Style.RESET_ALL}")

    return result.returncode, result.stdout.decode('utf-8'), result.stderr.decode('utf-8')


def checkRunShellCommand(testvals) :
    return checkRunCommand(testvals, True)


def checkPathExists(fn : str) :
    if os.path.exists(fn) :
        print(f"{_doIndentString()}    {Fore.GREEN}PASS: (File exists - '{fn}'){Style.RESET_ALL}")
    else:
        print(f"{_doIndentString()}    {Fore.RED}FAIL: (File missing - '{fn}'){Style.RESET_ALL}")
        _endTest(False)

def checkPathNotExists(fn : str) :
    if not os.path.exists(fn) :
        print(f"{_doIndentString()}    {Fore.GREEN}PASS: (File missing - '{fn}'){Style.RESET_ALL}")
    else:
        print(f"{_doIndentString()}    {Fore.RED}FAIL: (File exists - '{fn}'){Style.RESET_ALL}")
        _endTest(False)


def checkFileWriteable(fn : str) :
    if os.access(fn, os.W_OK) :
        print(f"{_doIndentString()}    {Fore.GREEN}PASS: (File writeable - '{fn}'){Style.RESET_ALL}")
    else:
        print(f"{_doIndentString()}    {Fore.RED}FAIL: (File not writeable - '{fn}'){Style.RESET_ALL}")
        _endTest(False)

def checkFileReadOnly(fn : str) :
    if not os.access(fn, os.W_OK) :
        print(f"{_doIndentString()}    {Fore.GREEN}PASS: (File read only - '{fn}'){Style.RESET_ALL}")
    else:
        print(f"{_doIndentString()}    {Fore.RED}FAIL: (File writeable - '{fn}'){Style.RESET_ALL}")
        _endTest(False)

def variantBegin(msg : str) :
    global _g_indentLevel
    print(f"{_doIndentString()}    {Fore.YELLOW}Executing variant: {msg}{Style.RESET_ALL}")
    _g_indentLevel += 1

def variantEnd() :
    global _g_indentLevel
    _g_indentLevel -= 1

def sectionBegin(msg : str) :
    global _g_indentLevel
    print(f"{Fore.BLUE}{indentAndWrap(msg, _doIndentString() + '    ', 72)}{Style.RESET_ALL}")
    _g_indentLevel += 1

def sectionEnd() :
    global _g_indentLevel
    _g_indentLevel -= 1


def indentAndWrap(inputString, indentPrefix, maxLineLength=72):
    import textwrap

    # Replace both Unix-style and Windows-style line breaks with spaces
    inputString = inputString.replace('\n', ' ').replace('\r', '')

    # Remove leading space if it was originally a line break
    inputString = inputString.lstrip()

    # Wrap the inputString
    wrappedLines = textwrap.wrap(inputString, width=maxLineLength - len(indentPrefix))

    # Add the indentPrefix to each line
    outputLines = [indentPrefix + line for line in wrappedLines]

    # Join the lines into a single string
    outputString = '\n'.join(outputLines)

    return outputString
