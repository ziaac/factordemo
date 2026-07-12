"""Idempotent launcher for the FACTOR keep-alive watchdog.

Run standalone (`python arm_watchdog.py`) or from a Jupyter/IPython startup hook so
the watchdog comes up automatically when the instance boots or a notebook opens.
Starts factor_watchdog.sh only if it is not already running (pid tracked in /tmp).
"""
import os
import subprocess

PIDF = "/tmp/factor_wd.pid"
WATCHDOG = "/workspace/factor_watchdog.sh"


def _running() -> bool:
    try:
        pid = open(PIDF).read().strip()
        return pid.isdigit() and os.path.exists("/proc/" + pid)
    except Exception:
        return False


if not _running():
    proc = subprocess.Popen(
        ["/bin/bash", WATCHDOG],
        stdout=open("/workspace/watchdog.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,  # detach so it survives the launching shell/kernel
    )
    open(PIDF, "w").write(str(proc.pid))
