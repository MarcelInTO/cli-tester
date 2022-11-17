# WCT : Wevr CLI Tester

## Usage:

wct [<test_name> | <wildcard_pattern>] ...

As many tests can be listed on the same command line as desired. Wildcard patterns are similair to rails or golang globbing: '**' matches arbitrary subdirectories

## WCT functions

These check... functions all execute some action, report on failure, and terminate that one test if a failure is encountered. If you use one of these functions, it is not necessary to check a return value. If your script continues, the function succeeded.

    checkFileExists(fn: str)
    checkFileReadOnly(fn: str)
    checkFileWriteable(fn: str)
    checkRunCommand(testvals, useShell=False)
    checkRunShellCommand(testvals)

Test control. These functions are utilities for controlling more complex tests.

    failTest(message: str)
    operatingSystem() -> str
    variantBegin(msg: str)
    variantEnd()

Filesystem management functions

    deleteFolder(name: str)

Regex generation. These functions generate regular expressions for common situations, so that you don't have to.

    xAnywhere(v)
    xBeginningOfLine(v)
    xFullLine(v)
    xLastFullLine(v)

## WvsLib functions

The wvslib module is technically not part of WCT, but rather a set of WVS specific utilities that make testing of WVS projects simpler.

***In order for these functions to work in your tests, you need to make sure that you have an Environment variable called*** **WCT_WVSLIB_AUTHTOKEN** ***set to your PAT.***

    init()

    testForOK()
    testForERR()

    checkForkRepo(name : str) -> str
    checkDeleteRepo(name : str, silent=False)
