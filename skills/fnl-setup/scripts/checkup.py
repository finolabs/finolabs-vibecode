#!/usr/bin/env python3
"""Read-only setup evidence; no host commands, network, or credential files."""

import json
import os
import re
import stat
import sys
from pathlib import Path

PLUGIN = "finolabs-vibecode"
PRINCIPLE = "A file that says something is on is not proof that it runs."
# Required sections of fnl-delegate's host template; Effort preference is optional.
HEADINGS = {"Limits", "Briefs folder", "Coordinators and reach", "Route judgment",
            "Dispatch marker", "Claude Code", "Codex", "Antigravity"}
MAX_BYTES = 262144


def open_safe(path, directory=False):
    """Open every component without following symlinks, including parent folders."""
    path = Path(os.path.abspath(path))
    if any(p.lower().startswith((".env", "credentials", "secrets")) or
           p.lower() in {".aws", ".ssh", ".gnupg"} for p in path.parts):
        raise OSError("excluded path")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:]):
            is_dir = directory or index < len(path.parts) - 2
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if is_dir:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read(path):
    try:
        fd = open_safe(path)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                return "unverified", ""
            data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return "unverified", ""
            return "ok", data.decode("utf-8")
    except FileNotFoundError:
        return "missing", ""
    except (OSError, UnicodeError, ValueError):
        return "unverified", ""


def read_json(path):
    status, text = read(path)
    if status != "ok":
        return status, {}
    try:
        data = json.loads(text)
        return ("ok", data) if isinstance(data, dict) else ("unverified", {})
    except ValueError:
        return "unverified", {}


def folders(path):
    """Bounded metadata discovery only; never traverse directory links."""
    try:
        fd = open_safe(path, directory=True)
        try:
            with os.scandir(fd) as entries:
                names = []
                for index, entry in enumerate(entries):
                    if index >= 128:
                        break
                    if entry.is_dir(follow_symlinks=False):
                        names.append(entry.name)
                return sorted(names)
        finally:
            os.close(fd)
    except OSError:
        return []


def item(check, status, reason):
    return {"check": check, "status": status, "reason": reason}


def cli_present(name):
    # Only PATH metadata: a symlink is evidence of an entry, not its target.
    linked = False
    inaccessible = False
    for folder in os.get_exec_path():
        try:
            fd = open_safe(Path(folder or "."), directory=True)
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            finally:
                os.close(fd)
            if stat.S_ISREG(info.st_mode) and info.st_mode & 0o111:
                return item("cli", "ok", "executable entry on PATH; not run")
            linked |= stat.S_ISLNK(info.st_mode)
        except FileNotFoundError:
            continue
        except OSError:
            inaccessible = True
    return item("cli", "unverified" if linked or inaccessible else "missing",
                "PATH link not followed" if linked else
                "PATH folder unreadable or symlink refused" if inaccessible else "no executable entry on PATH")


def version(manifest):
    value = manifest.get("version")
    return value if isinstance(value, str) and re.fullmatch(r"[\w.+-]{1,64}", value) else "unknown"


def plugin_evidence(host, home):
    """Only Claude's installation registry proves a recorded install.

    Other hosts' cache manifests supply versions, never activation evidence.
    Unknown layouts remain unverified rather than being guessed absent.
    """
    base = home / "plugins"
    roots = []
    registered = False
    registry_status = "unverified"
    if host == "claude":
        registry_status, registry = read_json(base / "installed_plugins.json")
        plugins = registry.get("plugins", {})
        if registry_status == "ok" and isinstance(plugins, dict):
            for key, entries in plugins.items():
                if key.split("@", 1)[0] != PLUGIN or not isinstance(entries, list):
                    continue
                for entry in entries[:16]:
                    location = entry.get("installPath") if isinstance(entry, dict) else None
                    if isinstance(location, str):
                        path = Path(os.path.abspath(location))
                        # Registry paths cannot redirect reads outside this host's plugin folder.
                        if path.is_relative_to(base):
                            roots.append(path)
            registered = bool(roots)
    if not roots:
        cache = base / "cache"
        for vendor in folders(cache):
            package = cache / vendor / PLUGIN
            roots.extend(package / v for v in folders(package)[:16])
        # Some hosts keep a direct plugin folder rather than a version cache.
        roots.append(base / PLUGIN)
    metadata = {"claude": ".claude-plugin", "codex": ".codex-plugin",
                "agy": ".antigravity-plugin"}[host]
    found = []
    for root in roots[:32]:
        status, manifest = read_json(root / metadata / "plugin.json")
        if status == "ok" and manifest.get("name") == PLUGIN:
            found.append((root, manifest))
    if not found:
        if registered:
            return item("plugin", "unverified", "install recorded; manifest unreadable or absent"), []
        if host == "claude" and registry_status == "ok":
            return item("plugin", "missing", "no install record or readable manifest"), []
        return item("plugin", "unverified", "no readable install record or recognized manifest"), []
    versions = ",".join(sorted({version(m) for _, m in found}))[:100]
    status = "ok" if registered and len(found) == len(roots) and "unknown" not in versions else "unverified"
    return item("plugin", status, ("install recorded" if status == "ok" else "files only; activation unknown") +
                "; version " + versions), found


def hooks_evidence(host, home, found):
    if host == "agy":
        status, data = read_json(home / "config/hooks.json")
        hooks = data.get(PLUGIN, {})
        source = "user hook group"
    elif len(found) == 1:
        root, manifest = found[0]
        location = manifest.get("hooks")
        if not isinstance(location, str):
            return item("hooks", "unverified", "no explicit hook file in manifest")
        path = Path(os.path.abspath(root / location))
        if not path.is_relative_to(root) or path.name != "hooks.json":
            return item("hooks", "unverified", "hook path outside inspected metadata")
        status, data = read_json(path)
        hooks = data.get("hooks", {})
        source = "plugin hook file"
    else:
        return item("hooks", "unverified", "no unique readable installed hook source")
    if status != "ok" or not isinstance(hooks, dict):
        return item("hooks", status if status != "ok" else "unverified", source + " absent or unreadable")
    declared = [event for event in ("SessionStart", "Stop", "PreCompact")
                if isinstance(hooks.get(event), list) and hooks[event]]
    absent = [e for e in ("SessionStart", "Stop") if e not in declared]
    if host == "agy":
        # This plugin's user group has SessionStart; Stop/PreCompact support is unverified.
        absent = [e for e in absent if e == "SessionStart"]
    reason = "declared: " + (", ".join(declared) or "none")
    reason += "; missing: " + ", ".join(absent) if absent else "; declarations only"
    if host == "agy":
        reason += "; Stop/PreCompact support unverified"
    elif "PreCompact" not in declared:
        reason += "; PreCompact not declared (optional)"
    return item("hooks", "missing" if absent else "unverified" if host == "agy" else "ok", reason)


def text_check(name, paths, predicate, present, absent):
    evidence = [read(path) for path in paths]
    if any(status == "ok" and predicate(text) for status, text in evidence):
        return item(name, "ok", present)
    status = "unverified" if any(s == "unverified" for s, _ in evidence) else "missing"
    return item(name, status, "file unreadable or symlink refused" if status == "unverified" else absent)


def collect():
    home = Path(os.path.abspath(os.environ.get("HOME", "~")))
    codex = Path(os.path.abspath(os.path.expanduser(os.environ.get("CODEX_HOME", str(home / ".codex")))))
    hosts = {}
    for host, folder, instructions in (
        ("claude", home / ".claude", [home / ".claude/CLAUDE.md"]),
        ("codex", codex, [codex / "AGENTS.md"]),
        ("agy", home / ".gemini", [home / ".gemini/GEMINI.md", home / ".gemini/AGENTS.md"]),
    ):
        plugin, found = plugin_evidence(host, folder)
        hosts[host] = [cli_present(host), plugin, hooks_evidence(host, folder, found),
                       text_check("instructions", instructions, lambda t: "fnl-coding-router" in t,
                                  "user file names fnl-coding-router; pointer only",
                                  "user file or fnl-coding-router pointer absent"),
                       item("runtime", "unverified", "hook trust/execution and approval policy not exercised"),
                       item("compaction", "unverified", "host threshold enforcement not exercised")]
    config = Path(os.path.expanduser(os.environ.get("ORCHESTRATION_HOST_CONFIG", str(home / ".finolabs/vibecode/host.md"))))
    if config.suffix.lower() != ".md":
        host_config = item("host config", "unverified", "only Markdown host config is inspected")
    else:
        status, text = read(config)
        missing = sorted(HEADINGS - set(re.findall(r"^## (.+?)\s*$", text, re.M)))
        host_config = item("host config", status if status != "ok" else ("missing" if missing else "ok"),
                           ("required headings present; values not validated" if not missing else
                            "required headings absent: " + ", ".join(missing)) if status == "ok" else
                           "host config absent or unreadable")
    cwd = Path.cwd()
    # Locate the nearest repository without invoking git or reading its config.
    root = next((p for p in (cwd, *cwd.parents) if os.path.lexists(p / ".git")), cwd)
    git = root / ".git"
    status, pointer = read(git)
    if status == "ok" and pointer.startswith("gitdir: "):
        git = Path(os.path.abspath(root / pointer[8:].strip()))
        # A worktree's exclude lives in the common git directory, named by commondir.
        status, common = read(git / "commondir")
        if status == "ok":
            git = Path(os.path.abspath(git / common.strip()))
    context = [root / "CLAUDE.md", root / "AGENTS.md"]
    repository = [
        text_check("local exclude", [git / "info/exclude"],
                   lambda t: any(line.strip() in {".finolabs/", "/.finolabs/"} for line in t.splitlines()),
                   ".finolabs/ exclude line present", ".finolabs/ exclude line absent"),
        text_check("agent skills", context, lambda t: bool(re.search(r"^## Agent skills\s*$", t, re.M)),
                   "Agent skills heading present", "Agent skills block absent"),
        text_check("review adoption", context,
                   lambda t: bool(re.search(r"^Pull requests (?:follow `fnl-review-gate`|merge only after a code review and a security review are posted on them, as `fnl-review-gate` says)", t, re.M)),
                   "review-gate adoption line present", "review-gate adoption line absent"),
        item("workflow", "unverified", "files cannot prove agents follow routing or review gates"),
    ]
    return {"principle": PRINCIPLE, "hosts": hosts, "setup": [host_config, *repository]}


def main():
    try:
        if any(arg != "--json" for arg in sys.argv[1:]):
            result = {"principle": PRINCIPLE, "hosts": {},
                      "setup": [item("arguments", "unverified", "usage: checkup.py [--json]")]}
        else:
            result = collect()
    except Exception:
        result = {"principle": PRINCIPLE, "hosts": {},
                  "setup": [item("checkup", "unverified", "inspection unavailable; nothing changed")]}
    try:
        if "--json" in sys.argv[1:]:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(result["principle"])
            for host, rows in [*result["hosts"].items(), ("setup", result["setup"])]:
                for row in rows:
                    print(f'{host} / {row["check"]}: {row["status"]} - {row["reason"]}')
    except (OSError, UnicodeError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
