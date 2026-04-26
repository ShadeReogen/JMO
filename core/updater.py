"""
core/updater.py
---------------
Checks the remote git repo for updates and applies them.
Called from the Settings mode or on a schedule.

Flow:
  1. git fetch origin
  2. Compare HEAD vs origin/main
  3. If behind → run update.sh (git pull + systemctl restart)
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE_SH  = os.path.join(BASE_DIR, "update.sh")


def _run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd, cwd=BASE_DIR,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_for_update() -> bool:
    """
    Returns True if the remote has commits not present locally.
    Runs git fetch first. Returns False on any error.
    """
    code, _, err = _run(["git", "fetch", "origin"])
    if code != 0:
        logger.warning(f"git fetch failed: {err}")
        return False

    code, out, _ = _run(["git", "rev-list", "HEAD..origin/main", "--count"])
    if code != 0:
        return False

    try:
        return int(out) > 0
    except ValueError:
        return False


def apply_update() -> bool:
    """
    Runs update.sh which does git pull and restarts the service.
    Returns True if the script was launched (process won't survive the restart).
    """
    if not os.path.isfile(UPDATE_SH):
        logger.error("update.sh not found")
        return False

    os.chmod(UPDATE_SH, 0o755)
    try:
        # Detach so the restart doesn't kill this call
        subprocess.Popen(
            ["bash", UPDATE_SH],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to launch update.sh: {e}")
        return False
