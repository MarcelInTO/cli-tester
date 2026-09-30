# Copyright (c) 2026 Wevr, Inc.
# Licensed under the MIT License. See LICENSE in the project root.

# Runs after t_fails_running and t_errors_running: the ports their servers
# held must be free again. Retried briefly, since on Windows a killed
# process's handles can take a moment to close.
from bg_helpers import portIsFree
from wct import checkTrue, getState, retryUntilPass

for key in ("launcher_port", "server_port") :
    port = getState(key)
    retryUntilPass(lambda : checkTrue(port is not None and portIsFree(port),
                                      f"{key} {port} is free again"),
                   timeout=5, interval=0.1)
