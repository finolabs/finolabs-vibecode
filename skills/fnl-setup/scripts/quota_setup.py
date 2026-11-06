#!/usr/bin/env python3
"""Preview resolved quota commands, then apply only that digest-bound plan."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import quota_probe as qp


def excluded(path):
    path = Path(path)
    roots = [Path(p).resolve() for p in ("/tmp", "/var/tmp", "/var/folders")]
    roots += [dr.account_home() / "Downloads", dr.account_home() / "tmp"]
    root = dr.consent_root()
    if root is not None:
        roots.append(root / "tmp")
    if any(path == base or base in path.parents for base in roots) or any(p.lower() == "downloads" for p in path.parts):
        raise ValueError("temporary or downloads path")
    if any(os.path.lexists(p / ".git") for p in [path.parent, *path.parents]):
        raise ValueError("repository path")


def resolve_executable(agent):
    if agent not in qp.SOURCES:
        raise ValueError("agent")
    # Ignore relative and empty PATH entries; resolution happens only in preview.
    search = os.pathsep.join(p for p in os.get_exec_path() if Path(p).is_absolute())
    found = shutil.which(agent, path=search)
    if not found or Path(found).name != agent:
        raise ValueError("executable missing or wrong name")
    excluded(Path(found).absolute())
    path = Path(found).resolve(strict=True)
    excluded(path)
    first = qp.checked_path(path)
    interpreter = None
    if first.startswith(b"#!"):
        words = first[2:].decode().strip().split()
        if not words or not Path(words[0]).is_absolute():
            raise ValueError("shebang")
        if words[0] == "/usr/bin/env":
            if len(words) != 2 or not re.fullmatch(r"[A-Za-z0-9._+-]+", words[1]):
                raise ValueError("env shebang")
            candidate = shutil.which(words[1], path=search)
            if not candidate:
                raise ValueError("interpreter missing")
        elif len(words) == 1:
            candidate = words[0]
        else:
            raise ValueError("interpreter options unsupported")
        excluded(Path(candidate).absolute())
        interpreter = str(Path(candidate).resolve(strict=True))
        excluded(Path(interpreter))
        qp.checked_path(interpreter)
    entry = {"executable": str(Path(found).absolute()), "resolved": str(path), "interpreter": interpreter}
    qp.checked_executable(agent, entry)
    return entry


def read_host():
    try:
        return dr.read_data("host.md").decode()
    except FileNotFoundError:
        return ""


def render(plan, confirmed=False):
    lines = ["## Quota probe", "", "- Quota probe: " + plan["choice"], "- Date: " + plan["date"]]
    if plan["choice"] == "on":
        lines.append("- Agents: " + ", ".join(plan["agents"]))
        for agent, entry in plan["agents"].items():
            lines.append(f"- Executable {agent}: {entry['executable']}")
            lines.append(f"- Resolved {agent}: {entry['resolved']}")
            if confirmed:
                lines.append(f"- Resolved digest {agent}: {hashlib.sha256(entry['resolved'].encode()).hexdigest()}")
            if entry["interpreter"]:
                lines.append(f"- Interpreter {agent}: {entry['interpreter']}")
        for label, path in plan["configs"].items():
            lines.append(f"- Claude config: {label}: {path}")
    return "\n".join(lines) + "\n\n"


def replace_section(text, new):
    # Locate real headings with byte-preserving offsets, ignoring fenced examples.
    headings, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and re.match(r"^#{1,2} ", line):
            headings.append((offset, line.strip()))
        offset += len(line)
    matches = [i for i, (_, heading) in enumerate(headings) if heading == "## Quota probe"]
    if len(matches) > 1:
        raise ValueError("duplicate quota section")
    newline = "\r\n" if "\r\n" in text else "\n"
    new = new.replace("\n", newline)
    if matches:
        i = matches[0]
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        return text[:headings[i][0]] + new + text[end:]
    return text + (newline * (2 if not text.endswith(newline) else 1) if text and not text.endswith(newline * 2) else "") + new


def digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_folders(folders):
    try:
        qp.validate_configs(folders)
    except FileNotFoundError as error:
        raise ValueError("config folder missing") from error


def preview(agents, configs=None, off=False):
    root = dr.consent_root()
    if root is None:
        raise ValueError("invalid data root")
    if len(set(agents)) != len(agents) or set(agents) - qp.SOURCES.keys() or (not off and not agents):
        raise ValueError("agents")
    folders = dict(configs or {})
    if any(qp.has_line_break(value) for pair in folders.items() for value in pair):
        raise ValueError("newline or carriage return in quota label or path")
    if "claude" in agents and not off:
        unique = {}
        for label, path in folders.items():
            try:
                os.path.samefile(path, path)
                if any(os.path.samefile(path, previous) for previous in unique.values()):
                    continue
            except FileNotFoundError as error:
                raise ValueError("config folder missing") from error
            unique[label] = path
        folders = unique
        default = str(dr.account_home() / ".claude")
        if not any(os.path.samefile(path, default) for path in folders.values() if Path(default).exists()):
            if "default" in folders:
                raise ValueError("default label names another folder")
            folders = {"default": default, **folders}
        validate_folders(folders)
    elif folders:
        raise ValueError("Claude not selected")
    text = read_host()
    old = qp.section(text).splitlines()
    for agent in agents:
        if any(line.startswith(f"- Executable {agent}: ") for line in old):
            if not any(line.startswith(f"- Resolved {agent}: ") for line in old):
                print(f"Quota probe {agent} needs re-preview: missing Resolved record.", file=sys.stderr)
            elif not any(line.startswith(f"- Resolved digest {agent}: ") for line in old):
                print(f"Quota probe {agent} needs re-preview: missing Resolved digest.", file=sys.stderr)
    plan = {"choice": "off" if off else "on", "date": qp.now().date().isoformat(),
            "created": qp.stamp(qp.now()), "root": str(root), "host_digest": hashlib.sha256(text.encode()).hexdigest(),
            "agents": {a: resolve_executable(a) for a in agents} if not off else {}, "configs": folders}
    validate_plan(plan)
    replace_section(text, render(plan))
    value = digest(plan)
    with qp.state_folder(create=True) as folder:
        qp.write_json(folder, "preview.json", {"plan": plan, "digest": value})
    return plan, value


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {"choice", "date", "created", "root", "host_digest", "agents", "configs"}:
        raise ValueError("plan")
    if plan["choice"] not in {"on", "off"} or plan["root"] != str(dr.consent_root()):
        raise ValueError("choice or root changed")
    if not re.fullmatch(r"[0-9a-f]{64}", plan["host_digest"]):
        raise ValueError("host digest")
    qp.datetime.strptime(plan["date"], "%Y-%m-%d")
    if not qp.timedelta(0) <= qp.now() - qp.timestamp(plan["created"]) <= qp.timedelta(minutes=60):
        raise ValueError("preview expired; preview again")
    agents, folders = plan["agents"], plan["configs"]
    if isinstance(folders, dict) and any(isinstance(value, str) and qp.has_line_break(value) for pair in folders.items() for value in pair):
        raise ValueError("newline or carriage return in quota label or path")
    if not isinstance(agents, dict) or set(agents) - qp.SOURCES.keys() or not isinstance(folders, dict):
        raise ValueError("agents")
    if plan["choice"] == "off":
        if agents or folders:
            raise ValueError("off plan")
        return
    if not agents:
        raise ValueError("agents")
    for agent, entry in agents.items():
        if not isinstance(entry, dict) or set(entry) != {"executable", "resolved", "interpreter"}:
            raise ValueError("executable")
        if any(qp.has_line_break(value) for value in entry.values() if isinstance(value, str)):
            raise ValueError("newline or carriage return in quota path")
        path = Path(entry["executable"])
        if not path.is_absolute() or ".." in path.parts or path.name != agent:
            raise ValueError("executable missing or wrong name")
        excluded(path)
        resolved = path.resolve(strict=True)
        if str(resolved) != entry["resolved"]:
            raise ValueError("executable target changed; preview again")
        excluded(resolved)
        if entry["interpreter"]:
            excluded(Path(entry["interpreter"]))
        qp.checked_executable(agent, entry)
    if "claude" in agents:
        validate_folders(folders)
        if not any(os.path.samefile(path, dr.account_home() / ".claude") for path in folders.values()):
            raise ValueError("default install missing")
    elif folders:
        raise ValueError("Claude not selected")


def apply(plan, supplied_digest, yes=False):
    if not yes or not isinstance(supplied_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", supplied_digest):
        raise ValueError("clear yes and full preview digest required")
    # The caller's JSON is only an optional consistency check; never authority.
    # No create here: a missing preview must leave even the state tree untouched.
    with qp.state_folder() as state:
        saved = qp.read_json(state, "preview.json")
        if (not isinstance(saved, dict) or set(saved) != {"plan", "digest"}
                or saved["digest"] != supplied_digest or digest(saved["plan"]) != supplied_digest
                or (plan is not None and plan != saved["plan"])):
            raise ValueError("digest mismatch; preview again")
        plan = saved["plan"]
        validate_plan(plan)
        with dr.root_folder(create=True) as folder:
            fcntl.flock(folder, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                text = dr.read_file(folder, "host.md", 262144).decode()
            except FileNotFoundError:
                text = ""
            if hashlib.sha256(text.encode()).hexdigest() != plan["host_digest"]:
                raise ValueError("host changed; preview again")
            result = replace_section(text, render(plan, confirmed=True)).encode()
            if len(result) > 262144:
                raise ValueError("host too large")
            dr.atomic_write(folder, "host.md", result)
        os.unlink("preview.json", dir_fd=state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "apply"))
    parser.add_argument("--agents", nargs="*", choices=tuple(qp.SOURCES), default=[])
    parser.add_argument("--claude-config", action="append", default=[], metavar="LABEL:/ABS/PATH")
    parser.add_argument("--off", action="store_true")
    parser.add_argument("--plan", help="optional consistency check against the stored preview; never applied directly")
    parser.add_argument("--digest")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "preview":
            folders = {}
            for value in args.claude_config:
                label, path = value.split(":", 1)
                if label in folders:
                    raise ValueError("duplicate label")
                folders[label] = path
            plan, value = preview(args.agents, folders, args.off)
            print(render(plan), end="")
            print("Plan: " + json.dumps(plan, separators=(",", ":")))
            print("Digest: " + value)
            print("Preview saved privately; host configuration unchanged.")
        else:
            apply(json.loads(args.plan or "null"), args.digest, args.yes)
            print("Quota probe section saved; no usage command was run.")
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("Quota setup refused: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
