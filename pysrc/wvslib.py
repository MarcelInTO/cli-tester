#!/usr/bin/env python3

import atexit
import gitlab
import os
import wct

from typing import Any
from typing import Tuple

##############################################################################
# Main test script
##############################################################################

g_gl = None
g_tempRepos = []

def init() :
    global g_gl
    g_gl = None
    try:
        token = os.getenv("WCT_WVSLIB_AUTHTOKEN")
        if token is None or token == "":
            wct.failTest("No WVS token. Env variable 'WCT_WVSLIB_AUTHTOKEN' is not set")   
        g_gl =  gitlab.Gitlab(url='https://wvs.io', private_token=token)
    except Exception:
        wct.failTest("Could not authenticate connection to wvs.io.")

    atexit.register(_doExitCleanup)


def _doExitCleanup() :
    for x in g_tempRepos :
        checkDeleteRepo(x, True)


def _doCheckInit() :
    global os
    if g_gl is None :
        wct.failTest("Use of unititialized wvs interface in test.")


def testForOK() -> str :
    _doCheckInit()
    return wct.xLastFullLine("OK")


def testForERR() -> str :
    _doCheckInit()
    return wct.xLastFullLine("ERR")


def checkForkRepo(name : str) -> str :
    cloneName, err = _doForkRepo(name)
    if err is not None:
        wct.failTest(err)
    else:
        wct.passTest(f"Fork repo '{name}'")
    return cloneName


def checkDeleteRepo(name : str, silent=False) :
    err = _doDeletetRepo(name)
    if not silent:
        if err is not None:
            wct.failTest(err)
        else:
            wct.passTest(f"Delete repo '{name}'")


def _doForkRepo(sourceRepo : str) -> Tuple[Any, str]:
    _doCheckInit()

    try:
        sourceProject = g_gl.projects.get(sourceRepo)
        if sourceProject is None :
            return None, "Could not find the project to fork"
    except Exception:
        return None, "Exception during getting source project"


    try:
        forkProject = sourceProject.forks.create()
        if forkProject is None :
            return None, "Could not fork the project"
    except Exception:
        return None, "Exception during forking project"

    g_tempRepos.append(forkProject.path_with_namespace)
    return forkProject.path_with_namespace, None


def _doDeletetRepo(repo : str) -> str :

    try:
        sourceProject = g_gl.projects.get(repo)
        if sourceProject is None :
            return "Delete failed. Could not find project."
    except Exception:
        return None, "Exception during getting source project"

    try:
        g_gl.projects.delete(sourceProject.id)
    except Exception:
        return None, "Exception during deleting forked project"

    # The repo might not have been created by us, in which case
    # it will not be in the cleanup list
    if repo in g_tempRepos: 
        g_tempRepos.remove(repo)

    return None
