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
import run_env  # noqa: E402

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


def locations():
    """The plugin root and the fnl-update skill folder, from either shipped copy."""
    here = Path(__file__).resolve()
    if here.parent.parent.name == "fnl-update":
        return here.parents[3], here.parents[1]
    return here.parents[1], here.parents[1] / "skills/fnl-update"


def plugin_root():
    root = locations()[0]
    return root if (root / ".claude-plugin/plugin.json").is_file() else None


def notes_path():
    return locations()[1] / "references/upgrades.json"


def installed_version():
    # Both shipped locations use the plugin's authoritative manifest. A standalone
    # skill has no plugin manifest and must report the installed version as unknown.
    root = plugin_root()
    if root is None:
        return None
    path = root / ".claude-plugin/plugin.json"
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
    if (not isinstance(data, dict) or set(data) - {"pinned"} != {"skipped", "never_ask"}
            or type(data["never_ask"]) is not bool or not isinstance(data["skipped"], list)
            or not all(release_tag(tag) for tag in data["skipped"])
            or ("pinned" in data and not stable(data["pinned"]))):
        return None
    return data


def stable(value):
    """A stable version without the tag prefix, or None."""
    tag = release_tag(value)
    return tag.removeprefix("v") if tag else None


# Upgrade notes: a closed schema read from the skill's own references folder.

NOTES_LIMIT = 65536
KINDS = {"rename", "setup", "migration", "hook", "removed"}
ITEM_ID = re.compile(r"([0-9]+\.[0-9]+\.[0-9]+)/([a-z0-9-]{1,40})", re.ASCII)
SETUP = re.compile(r"/fnl-setup add [a-z][a-z0-9-]{0,39}", re.ASCII)
CHECK_SCRIPT = re.compile(r"(?:scripts|skills/fnl-[a-z0-9-]{1,40}/scripts)/[a-z0-9_]{1,64}\.py", re.ASCII)
CHECK_ARG = re.compile(r"[A-Za-z0-9._=-]{1,64}", re.ASCII)
TEXT = re.compile(r"[ -~]{1,200}", re.ASCII)
CHECK_TIMEOUT = 10
CHECK_STATES = {0: "done", 1: "open", 3: "not applicable"}
MAX_SKIPPED = 200
EVIDENCE_LIMIT = 65536
EVIDENCE_URL = "https://github.com/finolabs/finolabs-vibecode/releases/tag/"


def parse_item(release, item):
    if not isinstance(item, dict) or not {"id", "kind", "text"} <= set(item) <= {
            "id", "kind", "text", "setup", "check", "until"}:
        raise ValueError("item keys")
    found = ITEM_ID.fullmatch(item["id"]) if isinstance(item["id"], str) else None
    if not found or found.group(1) != release or item["kind"] not in KINDS:
        raise ValueError("item id or kind")
    if not isinstance(item["text"], str) or not TEXT.fullmatch(item["text"]):
        raise ValueError("item text")
    if "setup" in item and not (isinstance(item["setup"], str) and SETUP.fullmatch(item["setup"])):
        raise ValueError("item setup")
    if "check" in item:
        argv = item["check"]
        if (not isinstance(argv, list) or not 1 <= len(argv) <= 9
                or not all(isinstance(arg, str) for arg in argv)
                or not CHECK_SCRIPT.fullmatch(argv[0])
                or not all(CHECK_ARG.fullmatch(arg) for arg in argv[1:])):
            raise ValueError("item check")
    if "until" in item and item["until"] != stable(item["until"]):
        raise ValueError("item until")
    return item


def parse_notes(data):
    """Validated entries in version order; any unknown key or bad value raises."""
    if not isinstance(data, dict) or set(data) != {"versions"} or not isinstance(data["versions"], list):
        raise ValueError("notes")
    entries, ids = [], set()
    for entry in data["versions"]:
        if not isinstance(entry, dict) or set(entry) != {"version", "items"}:
            raise ValueError("entry keys")
        release = entry["version"]
        if release != stable(release) or not isinstance(entry["items"], list) or not 1 <= len(entry["items"]) <= 30:
            raise ValueError("entry")
        items = [parse_item(release, item) for item in entry["items"]]
        if any(item["id"] in ids for item in items) or len({item["id"] for item in items}) != len(items):
            raise ValueError("duplicate id")
        ids.update(item["id"] for item in items)
        entries.append({"version": release, "items": items})
    if len({entry["version"] for entry in entries}) != len(entries):
        raise ValueError("duplicate version")
    return sorted(entries, key=lambda entry: version(entry["version"]))


def notes():
    with notes_path().open("rb") as handle:
        body = handle.read(NOTES_LIMIT + 1)
    if len(body) > NOTES_LIMIT:
        raise ValueError("notes too large")
    return parse_notes(json.loads(body))


def missing_release_entry(manifest_version, released):
    """True when a released manifest version (no -dev) has no notes entry."""
    return version(manifest_version)[3] == 1 and manifest_version.split("+")[0] not in released


def between(entries, low, high):
    """Entries after low (None means from the start) up to and including high."""
    return [entry for entry in entries
            if (low is None or version(entry["version"]) > version(low))
            and version(entry["version"]) <= version(high)]


def check_state(argv):
    """Run one read-only plugin script: exit 0 done, 1 open, 3 not applicable, else unknown."""
    root = plugin_root()
    if root is None:
        return "unknown"
    script = root / argv[0]
    try:
        if script.is_symlink() or not script.is_file() or root.resolve() not in script.resolve().parents:
            return "unknown"
        result = subprocess.run([sys.executable, "-I", str(script), *argv[1:]],
                                env=run_env.environment(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=CHECK_TIMEOUT, cwd=str(script.parent))
    except (OSError, ValueError, subprocess.SubprocessError):
        return "unknown"
    return CHECK_STATES.get(result.returncode, "unknown")


def onboard_state():
    """{"last_seen", "skipped"} or None when the stored file is invalid."""
    data = read_json("onboard.json", {"last_seen": None, "skipped": []})
    if (not isinstance(data, dict) or set(data) != {"last_seen", "skipped"}
            or not (data["last_seen"] is None or data["last_seen"] == stable(data["last_seen"]))
            or not isinstance(data["skipped"], list) or len(data["skipped"]) > MAX_SKIPPED
            or not all(isinstance(i, str) and ITEM_ID.fullmatch(i) for i in data["skipped"])):
        return None
    return data


def whats_new(installed):
    state = onboard_state() or {"last_seen": None, "skipped": []}
    entries = between(notes(), state["last_seen"], installed)
    if not entries:
        print("No new upgrade notes.")
        return
    lines = []
    for entry in entries:
        lines.append(entry["version"])
        for item in entry["items"]:
            if item["id"] in state["skipped"]:
                lines.append("- [skipped] %s: %s" % (item["id"], item["text"]))
                continue
            status = check_state(item["check"]) if "check" in item else "unknown"
            line = "- [%s] %s: %s" % (status, item["id"], item["text"])
            if "setup" in item and status in ("open", "unknown"):
                line += " (setup: %s)" % item["setup"]
            lines.append(line)
    print("\n".join(lines))


def onboard(argv):
    if len(argv) != 2 or argv[0] not in ("seen", "skip"):
        return
    state = onboard_state() or {"last_seen": None, "skipped": []}
    if argv[0] == "seen":
        seen = stable(argv[1])
        if not seen or seen != argv[1].removeprefix("v"):
            return
        state["last_seen"] = seen
    else:
        known = {item["id"] for entry in notes() for item in entry["items"]}
        if argv[1] not in known:
            return
        if argv[1] not in state["skipped"]:
            if len(state["skipped"]) >= MAX_SKIPPED:
                return
            state["skipped"] = [*state["skipped"], argv[1]]
    write_json("onboard.json", state)


def evidence_refusal(wanted, path):
    """None when the gh release JSON names exactly this published stable tag of the plugin."""
    try:
        with open(path, "rb") as handle:
            body = handle.read(EVIDENCE_LIMIT + 1)
        data = json.loads(body)
    except (OSError, ValueError):
        return "evidence unreadable"
    if len(body) > EVIDENCE_LIMIT:
        return "evidence too large"
    if not isinstance(data, dict) or set(data) != {"tagName", "isDraft", "isPrerelease", "url"}:
        return "evidence fields"
    tag = data["tagName"]
    if not isinstance(tag, str) or stable(tag) != wanted:
        return "evidence names another tag"
    if data["isDraft"] is not False or data["isPrerelease"] is not False:
        return "release is a draft or a prerelease"
    if data["url"] != EVIDENCE_URL + tag:
        return "release is not in the plugin's repository"
    return None


def target(argv, installed):
    if not argv:
        saved = cache()
        if saved is None:
            print("refused: no cached latest release")
            return
        wanted, source = saved["tag"].removeprefix("v"), "latest"
    else:
        wanted = stable(argv[0])
        if len(argv) != 3 or argv[1] != "--evidence":
            print("refused: evidence required")
            return
        if not wanted or wanted != argv[0].removeprefix("v"):
            print("refused: not a stable version")
            return
        refusal = evidence_refusal(wanted, argv[2])
        if refusal:
            print("refused: " + refusal)
            return
        source = "chosen"
    if installed is None:
        print("target %s %s unknown-installed" % (wanted, source))
        return
    order = version(wanted)[:3] + (1,)
    current = version(installed)
    direction = "upgrade" if order > current else "installed" if order == current else "rollback"
    lines = ["target %s %s %s" % (wanted, source, direction)]
    if direction == "rollback":
        for entry in between(notes(), wanted, installed):
            lines += ["lost: %s: %s" % (item["id"], item["text"]) for item in entry["items"]]
    print("\n".join(lines))


def onboard_line(installed):
    """The session-start line; read-only, and None on any doubt."""
    state = onboard_state()
    if state is None:
        return None
    entries = between(notes(), state["last_seen"], installed)
    if any(item["id"] not in state["skipped"] for entry in entries for item in entry["items"]):
        return ("finolabs-vibecode %s has upgrade notes. Let the user know they can type /fnl-update "
                "(on Codex $fnl-update) to see what is new and finish its setup; do not run it on your own."
                % installed.split("+")[0])
    return None


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
    if argv in (["never"], ["unpin"]) or (len(argv) == 2 and argv[0] in ("skip", "pin")):
        state = choices()
        if argv[0] == "never":
            state["never_ask"] = True
        elif argv[0] == "unpin":
            state.pop("pinned", None)
        else:
            tag = release_tag(argv[1])
            if not tag:
                return
            if argv[0] == "pin":
                state["pinned"] = tag.removeprefix("v")
            else:
                state["skipped"] = sorted({*state["skipped"], tag.removeprefix("v")})
        write_json("update-state.json", state)
        return
    if argv[:1] == ["onboard"]:
        onboard(argv[1:])
        return
    if argv == ["whats-new"]:
        whats_new(installed_version())
        return
    if argv[:1] == ["target"]:
        target(argv[1:], installed_version())
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
    if (newer and state is not None and not state["never_ask"] and "pinned" not in state
            and available not in [tag.removeprefix("v") for tag in state["skipped"]]):
        print("A newer finolabs-vibecode (%s) is available. Let the user know they can type /fnl-update (on Codex $fnl-update); do not update on your own." % available)
    try:
        line = onboard_line(installed)
    except Exception:
        line = None  # the onboarding line fails closed without touching the notice
    if line:
        print(line)


def main(argv=None):
    try:
        run(sys.argv[1:] if argv is None else argv)
    except Exception:
        pass  # hooks never emit errors, response text or tracebacks
    return 0


if __name__ == "__main__":
    sys.exit(main())
