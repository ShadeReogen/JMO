"""
wifi.py

Thin wrapper around NetworkManager (nmcli) for switching between saved
Wi-Fi profiles. Passwords live in NetworkManager, never in this repo.
All functions fail soft (empty list / False) when nmcli is unavailable.
"""
import subprocess
import time

_PREFIX = "netplan-wlan0-"   # profiles generated from the Pi imager's netplan


def _nmcli(*args, timeout=10):
    return subprocess.run(["nmcli", *args], capture_output=True, text=True,
                          timeout=timeout)


def _rows(args):
    """Parse `nmcli -t` output into lists of unescaped fields."""
    try:
        out = _nmcli("-t", *args).stdout
    except Exception:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.replace("\\:", "\0").split(":")
        rows.append([p.replace("\0", ":") for p in parts])
    return rows


def list_profiles():
    """Names of saved Wi-Fi connection profiles."""
    return [r[0] for r in _rows(["-f", "NAME,TYPE", "con", "show"])
            if len(r) >= 2 and r[1] == "802-11-wireless"]


def active_profile():
    """Name of the Wi-Fi profile currently connected, or None."""
    for r in _rows(["-f", "NAME,TYPE", "con", "show", "--active"]):
        if len(r) >= 2 and r[1] == "802-11-wireless":
            return r[0]
    return None


def label(profile, limit=14):
    """Short friendly name for the on-screen list."""
    name = profile[len(_PREFIX):] if profile.startswith(_PREFIX) else profile
    return name if len(name) <= limit else name[:limit - 1] + "…"


def apply_saved(wanted, delays=(20, 90)):
    """After boot, make sure the saved choice is the active network.

    NetworkManager may autoconnect to the other saved network first, so check
    after `delays` seconds (second try covers a slow boot / router).
    """
    for delay in delays:
        time.sleep(delay)
        if wanted not in list_profiles():
            return
        if active_profile() == wanted:
            return
        ok, msg = connect(wanted)
        print(f"[Wi-Fi] startup apply {wanted}: {ok} {msg}")
        if ok:
            return


def connect(profile):
    """Bring a saved profile up. Returns (ok, message)."""
    try:
        r = _nmcli("-w", "45", "con", "up", "id", profile, timeout=60)
    except Exception as e:
        return False, str(e) or "nmcli unavailable"
    if r.returncode == 0:
        return True, "Connected"
    msg = (r.stderr or r.stdout).strip().splitlines()
    return False, msg[-1] if msg else "Failed"
