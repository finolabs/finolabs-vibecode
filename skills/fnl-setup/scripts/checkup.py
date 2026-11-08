#!/usr/bin/env python3
"""Read-only setup evidence; no host commands, network, or credential files."""

import datetime
import json
import os
import re
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

PLUGIN = "finolabs-vibecode"
PRINCIPLE = "A file that says something is on is not proof that it runs."
# Required sections; Effort preference, Delegation mode and Routing are optional.
HEADINGS = {"Limits", "Briefs folder", "Coordinators and reach", "Route judgment",
            "Dispatch marker", "Claude Code", "Codex", "Antigravity",
            "Agent roles", "Review posting", "Delegate environment"}
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


def folder_install(base, markets):
    """The manifest of a directory marketplace the plugin is installed from, if readable."""
    status, known = read_json(base / "known_marketplaces.json")
    if status != "ok":
        return None
    for market in markets[:8]:
        source = known.get(market)
        location = source.get("installLocation") if isinstance(source, dict) else None
        kind = source.get("source") if isinstance(source, dict) else None
        if not isinstance(location, str) or not os.path.isabs(location) or \
                not isinstance(kind, dict) or kind.get("source") != "directory":
            continue
        root = Path(os.path.abspath(location))
        state, manifest = read_json(root / ".claude-plugin" / "plugin.json")
        if state == "ok" and manifest.get("name") == PLUGIN:
            return root, manifest
    return None


def plugin_evidence(host, home):
    """Only Claude's installation registry proves a recorded install.

    Other hosts' cache manifests supply versions, never activation evidence.
    Unknown layouts remain unverified rather than being guessed absent.
    """
    base = home / "plugins"
    roots = []
    registered = False
    registry_status = "unverified"
    markets = []
    if host == "claude":
        registry_status, registry = read_json(base / "installed_plugins.json")
        plugins = registry.get("plugins", {})
        if registry_status == "ok" and isinstance(plugins, dict):
            for key, entries in plugins.items():
                if key.split("@", 1)[0] != PLUGIN or not isinstance(entries, list):
                    continue
                markets.append(key.split("@", 1)[1] if "@" in key else "")
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
    live = folder_install(base, markets) if registered else None
    if live:
        # A directory marketplace may load the plugin in place while the registry keeps an old snapshot.
        # The files show what the folder declares, not what the running host loaded.
        live_version = version(live[1])
        if live_version == versions:
            return item("plugin", "ok", "install recorded; version " + live_version), [live]
        return item("plugin", "unverified",
                    "folder marketplace declares version " + live_version + "; registry records " + versions +
                    "; the host's own plugin list shows which loads"), [live]
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
        source = "plugin hook file" if root.is_relative_to(home / "plugins") else "folder hook file"
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
    reason = ("from folder hook file; " if source == "folder hook file" else "") + "declared: " + (", ".join(declared) or "none")
    reason += "; missing: " + ", ".join(absent) if absent else "; declarations only"
    if host == "agy":
        reason += "; Stop/PreCompact support unverified"
    if "PreCompact" in declared:
        reason += "; PreCompact declared"
    else:
        reason += "; PreCompact not declared (optional)"
    reason += "; delivery unverified"
    return item("hooks", "missing" if absent else "unverified" if host == "agy" else "ok", reason)


def text_check(name, paths, predicate, present, absent, reader=read):
    evidence = [reader(path) for path in paths]
    if any(status == "ok" and predicate(text) for status, text in evidence):
        return item(name, "ok", present)
    status = "unverified" if any(s == "unverified" for s, _ in evidence) else "missing"
    return item(name, status, "file unreadable or symlink refused" if status == "unverified" else absent)


def agents_evidence(status, text):
    if status == "unverified":
        return item("agents inventory", "unverified", "host config unreadable or symlink refused")
    sections = re.findall(r"^## Agents on this machine[ \t]*\r?$.*?(?=^#{1,2} |\Z)", text, re.M | re.S)
    if not sections:
        return item("agents inventory", "missing", "section absent; run /fnl-setup scan")
    if len(sections) != 1:
        return item("agents inventory", "unverified", "duplicate section; run /fnl-setup scan")
    rows = {}
    for line in sections[0].splitlines():
        cells = [v.strip() for v in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0] in {"Claude Code", "Codex", "Antigravity"}:
            if cells[0] in rows:
                return item("agents inventory", "unverified", "duplicate agent row")
            rows[cells[0]] = cells[-1]
    try:
        if len(rows) != 3:
            raise ValueError("incomplete rows")
        dates = [datetime.date.fromisoformat(value) for value in rows.values()]
        today = datetime.date.today()
        if max(dates) > today:
            raise ValueError("future check")
    except ValueError:
        return item("agents inventory", "unverified", "incomplete rows or invalid Checked dates; run /fnl-setup scan")
    if (today - min(dates)).days > 30:
        return item("agents inventory", "missing", "section stale (older than 30 days); run /fnl-setup scan")
    return item("agents inventory", "ok", "recent file inventory only; live access unverified")


def retired_evidence(paths, reader=read):
    # Construct the historical names so the repository's retired-name rule still applies.
    names = ["fnl-" + suffix for suffix in ("committee", "coordinator-sessions", "knowledge",
                                         "setup-instructions", "scan-agents", "set-mode")]
    evidence = [reader(path) for path in paths]
    found = sorted({name for status, text in evidence if status == "ok"
                    for name in names if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text)})
    unknown = any(status == "unverified" for status, _ in evidence)
    if found:
        return item("retired skill pointers", "missing", "references found: " + ", ".join(found) +
                    ("; some files unverified" if unknown else ""))
    return item("retired skill pointers", "unverified" if unknown else "ok",
                "some context files unreadable or symlink refused" if unknown else
                "none in readable known context files; runtime loading unverified")


# The instruction scan has its own bounded, in-memory evidence set. Reports contain
# locations and fixed pattern names only; only judge_payload may export line text.
INSTRUCTION_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "AGENTS.override.md", "GEMINI.md"}
SECRET_PATTERNS = [(name, re.compile(pattern)) for name, pattern in (
    ("private-key-header", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    ("access-key-id", r"\bAKIA[A-Z0-9]{16}\b"),
    ("github-token", r"\b(?:gh[posur]_|github_pat_)[A-Za-z0-9_]+"),
    ("api-key", r"\bsk-[A-Za-z0-9_-]{20,}"),
    ("npm-token", r"\bnpm_[A-Za-z0-9]{36,}\b"),
    ("gitlab-token", r"\bglpat-[A-Za-z0-9_-]{20,}"),
    ("google-api-key", r"\bAIza[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
    ("stripe-key", r"\b[rs]k_live_[A-Za-z0-9]{20,}"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{7,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("slack-token", r"\bxox[bp]-[A-Za-z0-9-]+"),
    ("secret-assignment", r'''(?i)\b\w*(?:password|passwd|secret|token|api_key|apikey|credential|_pass)\w{0,40}["']?\s*[:=]\s*["']?[^\s"']{8,}'''),
    ("bearer-token", r"(?i)\bAuthorization:\s*Bearer\s+[^\s]{20,}"),
    ("url-credentials", r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s/]+"),
    ("hex-assignment", r"""\b[A-Za-z_]\w*["']?\s*[:="']\s*["']?([A-Fa-f0-9]{32,})\b"""),
    ("encoded-assignment", r"[:=]\s*[\"']?[A-Za-z0-9+/]{40,}={0,2}"),
)]
MACHINE_PATH = re.compile(r"""/Users/|(?<![A-Za-z0-9.-])/home/|(?<![A-Za-z0-9./-])/(?:var/home|usr/home|root)(?=/|\b)|(?<![\w/~])~[A-Za-z_][\w.-]*(?=/|\b)|(?<![A-Za-z])[A-Za-z]:[\\/]""")


def unfenced(text):
    """Keep line numbers; recognize both Markdown fence characters."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence) and not line.strip()[len(mark):].strip():
                fence = None
            continue
        if fence is None:
            yield number, line


def instruction_consent(text):
    sections, active = [], None
    text = re.sub(r"<!--.*?(?:-->|\Z)", "", text, flags=re.S)
    for _, line in unfenced(text):
        if re.match(r"^#{1,2} ", line):
            active = [] if line.strip() == "## Route judgment" else None
            if active is not None:
                sections.append(active)
        elif active is not None:
            active.append(line)
    if len(sections) != 1:
        return False
    values = [line.strip() for line in sections[0] if re.match(r"^- Instruction check:", line)]
    return len(values) == 1 and bool(re.fullmatch(r"- Instruction check: on(?:[ .].*)?", values[0]))


def instruction_scan(home, codex, root, cwd, git, common_git=None, claude=None):
    files, cache, results, visited = {}, {}, [], set()
    limited = directory_limited = backup_limited = False
    result_keys = set()

    def label(path):
        if path is None:
            return "."
        if path.is_relative_to(root):
            value = path.relative_to(root).as_posix()
        elif path.is_relative_to(home):
            value = "~/" + path.relative_to(home).as_posix()
        elif path.is_relative_to(codex):
            value = "$CODEX_HOME/" + path.relative_to(codex).as_posix()
        else:
            value = "<instruction file>"
        # Even a filename can be hostile. Never echo control characters or tokens.
        if len(value) > 2000 or not value.isprintable() or any(rx.search(value) for _, rx in SECRET_PATTERNS):
            return "<instruction file>"
        return value

    def add(ident, status, path, line, pattern, reason):
        row = {"id": ident, "status": status, "file": label(path), "line": line,
               "pattern": pattern, "reason": reason}
        key = tuple(row.values())
        if key not in result_keys:
            result_keys.add(key)
            results.append(row)

    def load(path, boundary, host, rule=False, backup=False):
        nonlocal limited
        if path in files:
            return files[path]
        if path in cache:
            return None
        if len(files) >= 64:
            limited = True
            return None
        status, text = read(path)
        cache[path] = (status, text)
        if status == "missing":
            return None
        entry = {"text": text, "status": status, "boundary": boundary, "host": host,
                 "rule": rule, "backup": backup, "edges": [], "secret": False, "label": label(path)}
        files[path] = entry
        if status != "ok":
            add("I6" if backup else "I4", "unverified", path, 1, "safe-read",
                "not a readable regular file within 256 KiB; symlinks refused")
        return entry

    def entries(folder, backup=False):
        nonlocal directory_limited, backup_limited
        try:
            fd = open_safe(folder, directory=True)
            try:
                with os.scandir(fd) as stream:
                    rows = []
                    for i, entry in enumerate(stream):
                        if i >= 128:
                            directory_limited = True
                            backup_limited |= backup
                            break
                        rows.append((entry.name, entry.is_dir(follow_symlinks=False)))
                    return sorted(rows)
            finally:
                os.close(fd)
        except OSError:
            return []

    for folder, names, host in (
        (claude or home / ".claude", ["CLAUDE.md"], "claude"),
        (codex, ["AGENTS.override.md", "AGENTS.md"], "codex"),
        (home / ".gemini", ["GEMINI.md", "AGENTS.md"], "agy"),
        (root, sorted(INSTRUCTION_NAMES), "project"),
        (root / ".agents", ["AGENTS.md"], "agy"),
    ):
        boundary = root if folder.is_relative_to(root) else folder
        for name in names:
            load(folder / name, boundary, host)
        for name, directory in entries(folder, backup=True):
            if not directory and any(name.startswith(base + ".bak-") for base in names):
                load(folder / name, boundary, host, backup=True)

    # Codex's project chain includes every directory between root and cwd.
    chain_dirs = [root]
    if cwd.is_relative_to(root):
        for part in cwd.relative_to(root).parts:
            chain_dirs.append(chain_dirs[-1] / part)
    for folder in chain_dirs[1:]:
        for name in ("AGENTS.override.md", "AGENTS.md"):
            load(folder / name, root, "codex")

    # Bounded metadata walk finds unsupported nested instructions, not source files.
    queue = [(root, False, root), (home / ".gemini/config/rules", True, home / ".gemini")]
    while queue and len(visited) < 128 and len(files) < 64:
        folder, rule, boundary = queue.pop(0)
        if folder in visited:
            continue
        visited.add(folder)
        for name, directory in entries(folder, backup=rule):
            path = folder / name
            if directory:
                if name in {".git", "node_modules", ".venv", "vendor", "__pycache__"} or (name.startswith(".") and name != ".agents"):
                    continue
                queue.append((path, rule or path == root / ".agents/rules", boundary))
            elif rule and ".md.bak-" in name:
                load(path, boundary, "agy", backup=True)
            elif (rule and name.endswith(".md")) or name in INSTRUCTION_NAMES:
                nested_rule = rule and folder not in {root / ".agents/rules", home / ".gemini/config/rules"}
                nested_doc = not rule and folder not in {root, root / ".agents"}
                if nested_rule or nested_doc:
                    add("I12", "warn", path, 1, "nested-instruction", "Antigravity does not load nested instructions")
                # Nested documents are metadata findings, read only if an include
                # or the root-to-cwd Codex chain actually selects them.
                if not nested_doc:
                    load(path, boundary, "agy" if rule else "project", rule=rule)
    if queue:
        if len(files) >= 64:
            limited = True
        else:
            directory_limited = True

    followed, include_targets, cycles = set(), {}, set()

    def include(path, depth, stack):
        entry = files[path]
        if entry["status"] != "ok" or entry["backup"]:
            return
        for number, line in unfenced(entry["text"]):
            if len(line) > 2000:
                continue
            agy = re.fullmatch(r"\s*@\[[^\]\n]*\]\(([^\n]*)\)\s*", line)
            claude = re.fullmatch(r"\s*@([^\s]+)\s*", line) if not agy else None
            if not agy and not claude:
                continue
            target = (agy or claude)[1]
            boundary = entry["boundary"]
            key = (path.parent, target, boundary)
            if key not in include_targets:
                candidate = path.parent / target
                allowed_rule = False
                try:
                    outside = (target.startswith(("~", "/", "\\")) or bool(re.match(r"^[A-Za-z]:", target))
                               or ".." in target.replace("\\", "/").split("/"))
                    candidate = candidate if outside else candidate.resolve()
                    outside |= not candidate.is_relative_to(boundary)
                    if not outside:
                        allowed_rule = candidate.suffix == ".md" and any(candidate.is_relative_to(p) for p in (
                            root / ".agents/rules", home / ".gemini/config/rules"))
                except (OSError, RuntimeError, ValueError):
                    outside = True
                include_targets[key] = candidate, outside, allowed_rule
            candidate, outside, allowed_rule = include_targets[key]
            if outside:
                add("I4", "fail", path, number, "outside-root", "outside root")
                continue
            codex_only = entry["host"] == "codex" or path.name == "AGENTS.override.md"
            wrong_syntax = codex_only or (entry["host"] == "agy" and not agy) or (path.name.startswith("CLAUDE") and not claude)
            if wrong_syntax:
                add("I4", "warn", path, number, "include-syntax", "include syntax not supported by this host")
                continue
            if candidate.name not in INSTRUCTION_NAMES and not allowed_rule:
                add("I4", "fail", path, number, "include-name", "not an instruction-file name")
                continue
            if depth >= 4:
                add("I4", "fail", path, number, "include-depth", "more than four include hops")
                continue
            if candidate in stack:
                cycle = stack[stack.index(candidate):]
                cycle = min(cycle[i:] + cycle[:i] for i in range(len(cycle)))
                if cycle not in cycles:
                    cycles.add(cycle)
                    add("I4", "fail", path, number, "include-cycle", "include cycle")
                continue
            child = load(candidate, boundary, entry["host"], rule=allowed_rule)
            if not child or child["status"] != "ok":
                add("I4", "unverified" if limited or (child and child["status"] != "ok") else "fail",
                    path, number, "include-target", "instruction target absent or unreadable")
                continue
            edge = (number, candidate)
            if edge not in entry["edges"]:
                entry["edges"].append(edge)
            visit = (candidate, depth + 1)
            if visit not in followed:
                followed.add(visit)
                include(candidate, depth + 1, stack + (candidate,))

    # Roots are snapshotted: included files are followed through their owner only.
    for path in list(files):
        include(path, 0, (path,))

    for path, entry in list(files.items()):
        for name, directory in entries(path.parent, backup=True):
            if not directory and name.startswith(path.name + ".bak-"):
                load(path.parent / name, entry["boundary"], entry["host"], backup=True)
    if limited:
        add("I4", "unverified", None, 1, "discovery-limit", "bounded discovery incomplete (64 files)")

    if directory_limited:
        for ident in ("I4", "I12"):
            add(ident, "unverified", None, 1, "discovery-limit", "directory limit")

    if backup_limited:
        add("I6", "unverified", None, 1, "discovery-limit", "directory limit")

    tracked = tracked_paths(git / "index")
    seen, source_pairs = {}, {}
    for path, entry in files.items():
        if entry["status"] != "ok":
            continue
        lines = entry["text"].splitlines()
        for number, line in enumerate(lines, 1):
            if len(line) > 2000:
                entry["secret"] = True
                for ident in (("I6",) if entry["backup"] else ("I1", "I6")):
                    add(ident, "unverified", path, number, "line-too-long", "line too long")
                continue
            for name, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(line):
                    if (name == "hex-assignment" and len(match[1]) == 40
                            and re.search(r"\b(?:sha|commit|rev|hash)\b", line[:match.start(1)], re.I)):
                        continue
                    entry["secret"] = True
                    add("I6", "fail", path, number, name, "secret-looking content")
                    break
        if entry["backup"]:
            continue
        if len(lines) > 150:
            add("I1", "fail" if len(lines) > 200 else "warn", path, len(lines), "line-limit",
                "above 200 lines" if len(lines) > 200 else "above 150 lines (house rule)")
        if path.name == "AGENTS.override.md":
            add("I12", "warn", path, 1, "codex-override", "override replaces AGENTS.md at this scope")
        front = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", entry["text"], re.S)
        fields = dict(re.findall(r"^([A-Za-z_]+):[ \t]*(.*)$", front[1], re.M)) if front else {}
        trigger = fields.get("trigger", "").strip().strip("\"'")
        entry["always"] = not entry["rule"] or trigger == "always_on"
        if entry["rule"]:
            if trigger not in {"always_on", "model_decision", "glob", "manual"}:
                add("I12", "fail", path, 1, "rule-trigger", "missing or invalid trigger; rule silently discarded")
            elif trigger == "model_decision" and not fields.get("description", "").strip():
                add("I12", "fail", path, 1, "rule-description", "model_decision requires description")
            elif trigger == "glob" and not any(key in fields for key in ("globs", "glob")):
                add("I12", "fail", path, 1, "rule-globs", "glob trigger requires globs or glob")
        emphasis = 0
        in_comment = False
        for number, line in enumerate(lines, 1):
            if len(line) > 2000:
                continue
            normalized = line.strip()
            if len(normalized) >= 40:
                previous = seen.setdefault(normalized, set())
                for other in previous - {path}:
                    pair = (other, path)
                    if pair not in source_pairs:
                        source_pairs[pair] = (records_source(entry["text"], label(other), other.name)
                                              or records_source(files[other]["text"], label(path), path.name))
                    if not source_pairs[pair]:
                        add("I5", "warn", path, number, "duplicate-line", "repeated across files without a source record")
                        break
                previous.add(path)
            if MACHINE_PATH.search(line) and path.is_relative_to(root):
                is_tracked = tracked is not None and path.relative_to(root).as_posix() in tracked
                if is_tracked or tracked is None:
                    add("I7", "warn" if is_tracked else "unverified", path, number, "machine-path",
                        "machine path in tracked file" if is_tracked else "machine path; git index unavailable or unsupported")
            if re.search(r"\b(?:be careful|best practices|properly|clean code)\b", line, re.I):
                add("I10", "warn", path, number, "vague-phrase", "candidate for reason/emphasis review")
            emphasis += len(re.findall(r"\b(?:CRITICAL|MUST|ALWAYS|NEVER|IMPORTANT)\b", line))
            if emphasis > 5 and not any(r["id"] == "I11" and r["file"] == label(path) for r in results):
                add("I11", "warn", path, number, "emphasis-count", "more than five emphasis words; reasons need judgment")
            visible = re.sub(r"<!--.*?-->", "", line)
            if not in_comment and re.search(r"\b(?:maintainer(?: note)?|last updated|review.by)\s*:", visible, re.I):
                add("I13", "warn", path, number, "maintainer-note", "put maintainer notes in HTML comments")
            if "<!--" in visible:
                in_comment = True
            if "-->" in visible:
                in_comment = False
            for suffix in ("committee", "coordinator-sessions", "knowledge",
                           "setup-instructions", "scan-agents", "set-mode"):
                if re.search(r"(?<![\w-])fnl-" + suffix + r"(?![\w-])", line):
                    add("I14", "warn", path, number, "retired-skill", "retired skill pointer")
        try:
            fd = open_safe(path)
            try:
                age = datetime.datetime.now().timestamp() - os.fstat(fd).st_mtime
            finally:
                os.close(fd)
            if age > 90 * 86400:
                add("I13", "warn", path, 1, "file-age", "older than 90 days using file mtime, not git history")
        except OSError:
            add("I13", "unverified", path, 1, "file-age", "file mtime unavailable")
        if path.is_relative_to(root) and path.name in INSTRUCTION_NAMES - {"CLAUDE.local.md"}:
            # A root Claude wrapper delegates shared commands to its imported source.
            if (path == root / "CLAUDE.md" and root / "AGENTS.md" in files
                    and any(target == root / "AGENTS.md" for _, target in entry["edges"])
                    and all(not line.strip() or line.strip() == "@AGENTS.md"
                            or re.search(r"\bClaude(?: Code)?\b", line, re.I) for line in lines)):
                continue
            commands = "\n".join(line for _, line in unfenced(entry["text"]))
            has_heading = bool(re.search(r"^#{1,6}\s+.*\bcommands\b", commands, re.M | re.I))
            spans = " ".join(re.findall(r"`([^`\n]+)`", commands))
            content = entry["text"] if has_heading else spans
            if not (all(re.search(r"\b" + word + r"\b", content, re.I) for word in ("build", "test", "lint"))
                    and (re.search(r"\b(?:one|single|individual) test\b", content, re.I)
                         or re.search(r"\b(?:pytest|unittest|test)\s+[^\s`]+", spans, re.I))):
                add("I9", "warn", path, 1, "project-commands", "build, test, lint and one-test instructions not all present")

    total, unknown = 0, False
    for folder in [codex, *chain_dirs]:
        override, normal = folder / "AGENTS.override.md", folder / "AGENTS.md"
        chosen = override if override in files and files[override]["text"].strip() else normal
        if override in files and files[override]["status"] != "ok":
            unknown = True
        if chosen in files:
            total += len(files[chosen]["text"].encode("utf-8"))
            unknown |= files[chosen]["status"] != "ok"
    add("I2", "fail" if total > 32768 else "unverified" if unknown or limited else "ok", root / "AGENTS.md", 1,
        "codex-chain", f"{total} bytes against default 32768-byte chain limit")
    add("I2", "unverified", codex / "AGENTS.md", 1, "custom-byte-limit", "custom project_doc_max_bytes unverified; config.toml not read")

    expansion_cache, in_progress = {}, set()

    def expanded(path, budget=4):
        if path in in_progress:
            return 0, False
        key = (path, budget)
        if key in expansion_cache:
            return expansion_cache[key]
        in_progress.add(path)
        entry = files[path]
        by_line = dict(entry["edges"]) if budget else {}
        total, capped = 0, False
        for number, line in enumerate(entry["text"].splitlines(keepends=True), 1):
            if number in by_line:
                size, child_cap = expanded(by_line[number], budget - 1)
                capped |= child_cap
            else:
                size = len(line.encode("utf-8"))
            total += size
            if total > MAX_BYTES or capped:
                total, capped = MAX_BYTES, True
                break
        in_progress.remove(path)
        result = (total, capped)
        expansion_cache[key] = result
        return result

    always_total, expansion_limited = 0, False
    for path, entry in files.items():
        if entry["backup"] or entry["status"] != "ok":
            continue
        size, capped = expanded(path)
        if capped:
            expansion_limited = True
            for ident in ("I3", "I4"):
                add(ident, "unverified", path, 1, "expansion-limit", "expanded byte limit (256 KiB)")
        if entry["host"] == "agy" or (entry["host"] == "project" and path.name in {"AGENTS.md", "GEMINI.md"}):
            if size > 24000 and not capped:
                add("I3", "fail", path, 1, "antigravity-file-size", "above 24000 bytes after in-root includes")
            if entry.get("always") and path.parent in {
                    root, root / ".agents", home / ".gemini", root / ".agents/rules", home / ".gemini/config/rules"}:
                always_total += size
    add("I3", "unverified" if expansion_limited else "warn" if always_total > 80000 else "ok", None, 1, "antigravity-token-estimate",
        f"{always_total} bytes; 80000 bytes estimates 20000 tokens for global/always_on rules")

    local = root / "CLAUDE.local.md"
    if local in files:
        ignored = local_ignored(root, common_git or git, tracked)
        add("I8", "ok" if ignored is True else "warn" if ignored is False else "unverified", local, 1,
            "local-ignore", "ignored by local git rules" if ignored is True else
            "tracked or not ignored by local git rules" if ignored is False else "git ignore state unverified")
        if root / "AGENTS.md" in files and root / "CLAUDE.md" not in files:
            add("I8", "warn", local, 1, "native-agents-suppressed", "suppresses Claude Code native AGENTS.md read")
    for ident in range(1, 15):
        key = "I" + str(ident)
        if not any(r["id"] == key for r in results):
            complete = files and not limited and all(e["status"] == "ok" for e in files.values())
            add(key, "ok" if complete else "unverified", None, 1, "scan-complete",
                "no finding in readable instruction files" if files else "no instruction files discovered")
    add("I9", "unverified", None, 1, "command-execution", "command presence only; existence/execution unverified")
    if not any(r["id"] == "I13" and r["pattern"] == "file-age" for r in results):
        add("I13", "ok", None, 1, "file-age", "age uses file mtime, not git history")
    rank = {"fail": 0, "warn": 1, "unverified": 2, "ok": 3}
    results.sort(key=lambda r: (rank[r["status"]], int(r["id"][1:]), r["file"], r["line"], r["pattern"]))
    counts = {status: 0 for status in rank}
    for ident in range(1, 15):
        counts[next(r["status"] for r in results if r["id"] == "I" + str(ident))] += 1
    return {"files": len(files), "counts": counts, "results": results}, files, cache


def records_source(text, label, name):
    return any(re.search(r"\b(?:source|generated from|copied from)\b", line, re.I)
               and (label in line or name in line) for line in text.splitlines())


def tracked_paths(path):
    """Read a bounded ordinary git index, never invoke git or read its config.

    Split/sparse indexes and unfamiliar versions are unverified, not guessed.
    """
    import hashlib
    import struct
    try:
        fd = open_safe(path)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
                return None
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or len(data) < 32 or data[:4] != b"DIRC" or hashlib.sha1(data[:-20]).digest() != data[-20:]:
            return None
        version, count = struct.unpack_from(">II", data, 4)
        if version not in {2, 3} or count > 4096:
            return None
        offset, paths = 12, set()
        for _ in range(count):
            start = offset
            flags = struct.unpack_from(">H", data, offset + 60)[0]
            offset += 62 + (2 if flags & 0x4000 else 0)
            end = data.index(b"\0", offset)
            name = data[offset:end].decode("utf-8")
            if not name or name.endswith("/"):
                return None
            paths.add(name)
            offset = start + ((end - start + 8) // 8) * 8
        # Unknown mandatory extensions (lowercase initial) change index semantics.
        while offset < len(data) - 20:
            signature = data[offset:offset + 4]
            size = struct.unpack_from(">I", data, offset + 4)[0]
            if len(signature) != 4 or not 65 <= signature[0] <= 90:
                return None
            offset += 8 + size
        return paths if offset == len(data) - 20 else None
    except (OSError, ValueError, UnicodeError, struct.error):
        return None


def local_ignored(root, git, tracked):
    import fnmatch
    if tracked is None:
        return None
    if "CLAUDE.local.md" in tracked:
        return False
    ignored = False
    for path in (git / "info/exclude", root / ".gitignore"):
        status, text = read(path)
        if status == "unverified":
            return None
        for line in text.splitlines():
            pattern = line.rstrip()
            if not pattern or pattern.startswith("#"):
                continue
            negate = pattern.startswith("!")
            pattern = pattern[1:] if negate else pattern
            if "\\" in pattern:
                return None
            if fnmatch.fnmatchcase("CLAUDE.local.md", pattern.lstrip("/")):
                ignored = not negate
    # A missing local match cannot disprove an unread global excludes file.
    return True if ignored else None


def judge_payload(files):
    """The sole line-text export: consent is checked before scanning/calling this."""
    output, size = [], 0
    marker = "[truncated]\n"
    for path, entry in files.items():
        if entry["status"] != "ok" or entry["backup"] or entry["secret"] or path.name == "CLAUDE.local.md":
            continue
        scan_section = False
        for number, line in enumerate(entry["text"].splitlines(), 1):
            if re.match(r"^#{1,2} ", line):
                scan_section = line.strip() == "## Agents on this machine"
            if scan_section or re.match(r"^\s*@", line):
                continue
            if MACHINE_PATH.search(line) or any(rx.search(line) for _, rx in SECRET_PATTERNS):
                continue
            line = f'{entry["label"]}:{number}: {line}'
            shortened = line[:287] + " [truncated]" if len(line) > 300 else line
            encoded = (shortened + "\n").encode("utf-8")
            if size + len(encoded) > 8192 - len(marker):
                return "".join(output) + marker
            output.append(shortened + "\n")
            size += len(encoded)
    return "".join(output)


def instruction_lines(block):
    counts = " ".join(f"{key}={value}" for key, value in block["counts"].items())
    lines = [f'instructions: {block["files"]} files; {counts}']
    groups = {}
    for row in block["results"]:
        if row["status"] == "ok" or row["pattern"] in {"custom-byte-limit", "command-execution"}:
            continue
        key = (row["id"], row["status"], row["pattern"], row["file"])
        if key not in groups:
            groups[key] = dict(row, count=0)
        groups[key]["count"] += 1
    # Round-robin ids so even many affected files cannot consume the text budget.
    by_id = {}
    for row in groups.values():
        by_id.setdefault(row["id"], []).append(row)
    findings = []
    while any(by_id.values()):
        for rows in by_id.values():
            if rows:
                findings.append(rows.pop(0))
    shown = findings[:11] if len(findings) > 12 else findings
    for row in shown:
        lines.append(f'{row["id"]}: {row["status"]} - {row["file"]}:{row["line"]} {row["pattern"]}; count={row["count"]}; {row["reason"]}')
    if len(findings) > 12:
        lines.append(f'{len(findings) - 11} more; use --json')
    return lines


def host_config_text(home):
    # The override still serves non-consent diagnostics, never payload permission.
    explicit = os.environ.get("ORCHESTRATION_HOST_CONFIG")
    if explicit:
        config = Path(os.path.abspath(os.path.expanduser(explicit)))
        return read(config) if config.suffix.lower() == ".md" else ("unverified", "")
    try:
        return "ok", dr.read_data("host.md").decode("utf-8")
    except FileNotFoundError:
        return "missing", ""
    except (OSError, ValueError, UnicodeError):
        return "unverified", ""


def project_tracking(text, root):
    """Diagnose host-only joins without exporting values or changing configuration."""
    import project_progress as pp
    rows = []
    try:
        entries = pp.project_settings(text)
    except ValueError:
        entries = {}
        rows.append(item('project settings', 'unverified', 'invalid Project settings section; all entries ignored'))
    try:
        _, body, end = pp.host_section(text)
    except ValueError:
        body = end = len(text)
        rows.append(item('project progress', 'unverified', 'invalid Project progress section; global settings ignored'))
    globals_ = {}
    for key, old in (('ledger', 'Ledger project'), ('tasks', 'Task file')):
        matches = re.findall(r'^(?:- )?' + old + r': (.*)$', text[body:end], re.M)
        if matches:
            rows.append(item('deprecated ' + key, 'unverified',
                             key + ': convert for this repository with project_progress.py settings --set ' + key + '=<value>'))
        if len(matches) == 1:
            globals_[key] = matches[0]
    code = pp.repository_code(root)
    try:
        raw = dr.read_data('ledger.jsonl', 16 * 1024 * 1024).decode('utf-8')
        names = set()
        for line in raw.splitlines():
            if len(line) > 4096:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get('event') == 'start' and isinstance(row.get('project'), str):
                names.add(row['project'])
        folder = root.name.lower()
        resembles = any(min(len(folder), len(name)) >= 4 and
                        (folder in name.lower() or name.lower() in folder) for name in names)
        if (code, 'ledger') not in entries and root.name not in names and resembles:
            rows.append(item('ledger-project mismatch', 'unverified',
                             'no ledger runs match the folder name; similar project names exist; set a ledger entry to confirm association'))
    except (OSError, ValueError, UnicodeError):
        pass
    return rows


def claude_home_names(home):
    """Directory names shaped like Claude config homes among up to 4096 entries, no links followed."""
    try:
        fd = open_safe(home, directory=True)
        try:
            with os.scandir(fd) as entries:
                names, seen = [], 0
                for entry in entries:
                    seen += 1
                    if seen > 4096:
                        return sorted(names), True
                    if (entry.name == ".claude" or re.fullmatch(r"\.claude-[\w.-]{1,40}", entry.name)) \
                            and entry.is_dir(follow_symlinks=False):
                        names.append(entry.name)
                return sorted(names), False
        finally:
            os.close(fd)
    except OSError:
        return [], False


def other_claude_homes(home, active):
    """Names only: sibling Claude config folders that hold plugins, and the version each records."""
    names, truncated = claude_home_names(home)
    rows = []
    for name in names:
        folder = home / name
        if os.path.abspath(folder) == os.path.abspath(active) or not folders(folder) or \
                "plugins" not in folders(folder):
            continue
        _, found = plugin_evidence("claude", folder)
        rows.append(name + ": " + ("version " + ",".join(sorted({version(m) for _, m in found}))[:60]
                                   if found else "no install record"))
    if not rows:
        return []
    notes = ("; more than 4096 home entries; list may be incomplete" if truncated else "") + \
        ("; more homes not shown" if len(rows) > 8 else "")
    return [item("other claude homes", "unverified" if truncated or any("no install" in r for r in rows) else "ok",
                 "; ".join(rows[:8]) + notes + "; launch commands are not inspected")]


def claude_plugin_enablement(home, active):
    """Inert settings facts only: home labels and this plugin's boolean state."""
    names, truncated = claude_home_names(home)
    homes = [(".claude", home / ".claude")]
    if active != home / ".claude":
        label = active.name if active.parent == home and active.name in names else "selected home"
        homes.append((label, active))
    homes.extend((name, home / name) for name in names
                 if home / name not in {folder for _, folder in homes}
                 and "plugins" in folders(home / name))
    rows, unverified = [], truncated
    for label, folder in homes:
        status, settings = read_json(folder / "settings.json")
        plugins = settings.get("enabledPlugins", {})
        state = "unverified"
        if status == "ok" and isinstance(plugins, dict):
            values = [value for key, value in plugins.items()
                      if key.startswith(PLUGIN + "@") and key[len(PLUGIN) + 1:]]
            if not values:
                state = "absent"
            elif all(value is True for value in values):
                state = "enabled"
            elif all(value is False for value in values):
                state = "disabled"
        unverified |= state == "unverified"
        rows.append(label + ": " + state)
    if truncated:
        rows.append("more than 4096 home entries; list may be incomplete")
    return [item("claude plugin enablement", "unverified" if unverified else "ok", "; ".join(rows))]


def collect(payload=False):
    # A local copy keeps this skill usable when installed alone, including under -I.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mode import effective
    settings = effective()
    home = dr.account_home()
    configured = os.environ.get("CODEX_HOME", "")
    codex = Path(configured) if os.path.isabs(configured) else home / ".codex"
    selected = os.environ.get("CLAUDE_CONFIG_DIR", "")
    claude_home = Path(os.path.abspath(selected)) if os.path.isabs(selected) else home / ".claude"
    config_status, config_text = host_config_text(home)
    if payload:
        try:
            consent_text = dr.read_data("host.md").decode("utf-8")
        except (OSError, ValueError, UnicodeError):
            return ""
        if not instruction_consent(consent_text):
            return ""
    cwd = Path.cwd()
    root = next((p for p in (cwd, *cwd.parents) if os.path.lexists(p / ".git")), cwd)
    git = root / ".git"
    status, pointer = read(git)
    if status == "ok" and pointer.startswith("gitdir: "):
        git = Path(os.path.abspath(root / pointer[8:].strip()))
    index_git = git
    status, common = read(git / "commondir")
    if status == "ok":
        git = Path(os.path.abspath(git / common.strip()))
    instruction_block, files, cache = instruction_scan(home, codex, root, cwd, index_git, git, claude=claude_home)
    if payload:
        return judge_payload(files)
    def context_read(path):
        return cache.get(path, ("unverified", ""))
    hosts = {}
    user_context = []
    for host, folder, instructions in (
        ("claude", claude_home, [claude_home / "CLAUDE.md"]),
        ("codex", codex, [codex / "AGENTS.override.md", codex / "AGENTS.md"]),
        ("agy", home / ".gemini", [home / ".gemini/GEMINI.md", home / ".gemini/AGENTS.md"]),
    ):
        user_context.extend(instructions)
        plugin, found = plugin_evidence(host, folder)
        hosts[host] = [cli_present(host), plugin, hooks_evidence(host, folder, found),
                       text_check("instructions", instructions, lambda t: "fnl-coding-router" in t,
                                  "user file names fnl-coding-router; pointer only",
                                  "user file or fnl-coding-router pointer absent", reader=context_read),
                       item("runtime", "unverified", "hook trust/execution and approval policy not exercised"),
                       item("compaction", "unverified", "host threshold enforcement not exercised")]
        enforcement = {
            "claude": "agent judgment; Claude Code hooks can add continuation reminders; execution unverified",
            "codex": "agent judgment; Codex hooks require user trust; trust/execution unverified",
            "agy": "agent judgment; no enforcement hook relied on; static always-on rule ignores Routing",
        }[host]
        hosts[host].append(item("mode enforcement", "unverified", enforcement + "; auto is never 100%"))
    status, text = config_status, config_text
    missing = sorted(HEADINGS - set(re.findall(r"^## (.+?)\s*$", text, re.M)))
    host_config = item("host config", status if status != "ok" else ("missing" if missing else "ok"),
                       ("required headings present; values not validated" if not missing else
                        "required headings absent: " + ", ".join(missing)) if status == "ok" else
                       "host config absent or unreadable")
    inventory = agents_evidence(status, text)
    context = [root / "CLAUDE.md", root / "CLAUDE.local.md", root / "AGENTS.override.md",
               root / "AGENTS.md", root / "GEMINI.md"]
    repository = [
        text_check("local exclude", [git / "info/exclude"],
                   lambda t: any(line.strip() in {".finolabs/", "/.finolabs/"} for line in t.splitlines()),
                   ".finolabs/ exclude line present", ".finolabs/ exclude line absent"),
        text_check("agent skills", context, lambda t: bool(re.search(r"^## Agent skills\s*$", t, re.M)),
                   "Agent skills heading present", "Agent skills block absent", reader=context_read),
        text_check("review adoption", context,
                   lambda t: bool(re.search(r"(?:^|[.>]\s+)Pull requests (?:follow `fnl-review-gate`|merge only after a code review and a security review are posted on them, as `fnl-review-gate` says)", t, re.M)),
                   "review-gate adoption line present", "review-gate adoption line absent", reader=context_read),
        item("workflow", "unverified", "files cannot prove agents follow routing or review gates"),
    ]
    repository.extend(project_tracking(config_text, root))
    data_path, data_source = dr.data_root()
    from quota_probe import status_lines
    quota = item("quota", "unverified", "advisory cache; " + " | ".join(status_lines()))
    return {"principle": PRINCIPLE, "hosts": hosts, "instructions": instruction_block, "setup": [
            item("data root", data_source, str(data_path)), host_config, inventory, quota,
            *other_claude_homes(home, claude_home),
            *claude_plugin_enablement(home, claude_home),
            retired_evidence([*user_context, *context], reader=context_read),
            item("effective settings", "ok", "delegation mode=" + settings["delegation_mode"] +
                 "; routing=" + settings["routing"] + "; auto gate=" + settings["auto_gate"] + "; selected values only, not runtime proof"), *repository]}


def main():
    try:
        if any(arg not in {"--json", "--judge-payload"} for arg in sys.argv[1:]) or len(sys.argv[1:]) > 1:
            result = {"principle": PRINCIPLE, "hosts": {},
                      "setup": [item("arguments", "unverified", "usage: checkup.py [--json | --judge-payload]")]}
        else:
            result = collect(payload=True) if "--judge-payload" in sys.argv[1:] else collect()
    except Exception:
        result = {"principle": PRINCIPLE, "hosts": {},
                  "setup": [item("checkup", "unverified", "inspection unavailable; nothing changed")]}
    try:
        if "--judge-payload" in sys.argv[1:]:
            if isinstance(result, str):
                print(result, end="")
        elif "--json" in sys.argv[1:]:
            print(json.dumps(result, ensure_ascii=True))
        else:
            print(result["principle"])
            for host, rows in [*result["hosts"].items(), ("setup", result["setup"])]:
                for row in rows:
                    if host != "setup" and row["check"] in {"runtime", "compaction"}:
                        continue  # Keep the combined report within forty lines.
                    print(f'{host} / {row["check"]}: {row["status"]} - {row["reason"]}')
            for line in instruction_lines(result["instructions"]) if "instructions" in result else []:
                print(line)
    except (OSError, UnicodeError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
