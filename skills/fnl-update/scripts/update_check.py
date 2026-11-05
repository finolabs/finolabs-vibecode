#!/usr/bin/env python3
"""Best-effort release notice. Only the detached --fetch worker uses the network."""

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also works with python -I
import fnl_metrics as fm  # noqa: E402
import data_root as dr

URL = "https://api.github.com/repos/finolabs/finolabs-vibecode/releases/latest"
USER_AGENT = "finolabs-vibecode-update-check"
MAX_AGE = 24 * 60 * 60
MAX_RESPONSE = 65536
TIMEOUT = 3
TAG = re.compile(r"v?[0-9]+\.[0-9]+\.[0-9]+", re.ASCII)
INSTALLED = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)(-dev)?(?:\+[0-9A-Za-z.-]+)?", re.ASCII)


def release_tag(value):
    """Accept only a bounded stable version, never arbitrary response text."""
    return value if isinstance(value, str) and len(value) <= 64 and TAG.fullmatch(value) else None


def version(value):
    """Numeric precedence; a development build precedes its own stable release."""
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("invalid version")
    found = INSTALLED.fullmatch(value.removeprefix("v"))
    if not found:
        raise ValueError("invalid version")
    return (*map(int, found.group(1, 2, 3)), 0 if found.group(4) else 1)


def installed_version():
    # Both shipped locations use the plugin's authoritative manifest. A standalone
    # skill has no plugin manifest and must report the installed version as unknown.
    here = Path(__file__).resolve()
    root = here.parents[3] if here.parent.parent.name == "fnl-update" else here.parents[1]
    path = root / ".claude-plugin/plugin.json"
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        body = handle.read(65537)
    if len(body) > 65536:
        raise ValueError("manifest too large")
    manifest = json.loads(body)
    if manifest.get("name") != "finolabs-vibecode":
        raise ValueError("unexpected manifest")
    value = manifest["version"]
    version(value)
    return value


def read_json(name, default):
    try:
        return json.loads(dr.read_data(Path("state") / name, 4096))
    except FileNotFoundError:
        return default
    except (OSError, ValueError):
        return None


def cache():
    data = read_json("update-check.json", None)
    if data is None:
        return None
    if not isinstance(data, dict) or set(data) != {"checked_at", "tag"}:
        return None
    at = data["checked_at"]
    if (type(at) not in (int, float) or at < 0 or at > fm.now().timestamp()
            or not math.isfinite(at) or not release_tag(data["tag"])):
        return None
    return data


def stored_choices():
    """Keep invalid choices distinct so the hook stays silent until repaired."""
    data = read_json("update-state.json", {"skipped": [], "never_ask": False})
    if (not isinstance(data, dict) or set(data) != {"skipped", "never_ask"}
            or type(data["never_ask"]) is not bool or not isinstance(data["skipped"], list)
            or not all(release_tag(tag) for tag in data["skipped"])):
        return None
    return data


def choices():
    return stored_choices() or {"skipped": [], "never_ask": False}


def write_json(name, data):
    dr.write_data(Path("state") / name, (json.dumps(data, separators=(",", ":")) + "\n").encode())


def fetch():
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None  # one fixed HTTPS GET; never follow response URLs

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT}, method="GET")
    with opener.open(request, timeout=TIMEOUT) as response:
        body = response.read(MAX_RESPONSE + 1)
    if len(body) > MAX_RESPONSE:
        return
    data = json.loads(body)
    tag = release_tag(data.get("tag_name")) if isinstance(data, dict) else None
    if tag:
        write_json("update-check.json", {"checked_at": fm.now().timestamp(), "tag": tag})


def start_fetch():
    detach = ({"creationflags": 0x00000008 | 0x00000200} if sys.platform == "win32"
              else {"start_new_session": True})
    subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--fetch"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, close_fds=True, **detach,
                     cwd=str(Path(__file__).resolve().parent))


def run(argv):
    if os.environ.get("FNL_UPDATE_CHECK", "").lower() == "off" or dr.consent_root() is None:
        return
    if argv == ["--fetch"]:
        fetch()
        return
    if argv == ["never"] or (len(argv) == 2 and argv[0] == "skip"):
        state = choices()
        if argv[0] == "never":
            state["never_ask"] = True
        else:
            tag = release_tag(argv[1])
            if not tag:
                return
            state["skipped"] = sorted({*state["skipped"], tag.removeprefix("v")})
        write_json("update-state.json", state)
        return
    if argv not in ([], ["status"]):
        return
    installed, saved = installed_version(), cache()
    state = choices() if argv == ["status"] else stored_choices()
    stale = saved is None or fm.now().timestamp() - saved["checked_at"] >= MAX_AGE
    available = saved["tag"].removeprefix("v") if saved else None
    newer = bool(installed and available and version(available) > version(installed))
    if argv == ["status"]:
        print(json.dumps({"installed": installed, "available": available, "newer": newer,
                          "stale": stale, **state}, separators=(",", ":")))
        return
    if installed is None:
        return
    if stale:
        start_fetch()  # no wait; this invocation only uses the cache read above
    if (newer and state is not None and not state["never_ask"]
            and available not in [tag.removeprefix("v") for tag in state["skipped"]]):
        print("A newer finolabs-vibecode (%s) is available. Let the user know they can type /fnl-update (on Codex $fnl-update); do not update on your own." % available)


def main(argv=None):
    try:
        from quota_probe import worker_guard
        if worker_guard():
            return 0
        run(sys.argv[1:] if argv is None else argv)
    except Exception:
        pass  # hooks never emit errors, response text or tracebacks
    return 0


if __name__ == "__main__":
    sys.exit(main())
