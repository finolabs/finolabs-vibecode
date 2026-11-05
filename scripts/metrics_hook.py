#!/usr/bin/env python3
"""Claude Code hook that records usage metadata (see fnl_metrics.py).

Reads one hook payload from stdin and writes at most one event. `--host claude|codex|antigravity`
says which agent sent it (default claude); Antigravity payloads carry no event name, so `--event
session_start|post_tool_use` says which hook fired. It prints nothing (Antigravity wants `{}`) and always
exits 0, so it can never fail or change the session. It reads command text only to test for a
trigger and discards it; the only file it opens is a review body named in a `gh pr comment`
command, and only the first line of that file is read.
"""

import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I leaves the script folder off the path
import fnl_metrics as fm  # noqa: E402

# A command starts at the beginning of the text or after ; & | ( or a newline, optionally behind VAR=value words.
START = r"(?:^|[;&|(\n])[ \t]*(?:\w+=\S+[ \t]+)*"
COMMIT = re.compile(START + r"git(?:[ \t]+(?:-[cC][ \t]+(?:\"[^\"]*\"|'[^']*'|[^\s\"']\S*)|--[\w-]+(?:=\S+)?))*[ \t]+commit(?![\w-])")
GH_COMMENT = re.compile(START + r"gh[ \t]+pr[ \t]+comment\b([^;&|\n]*)")
ROUTER = re.compile(START + r"(?:python3?(?:[ \t]+-\S+)*[ \t]+)?[\"']?[^\s\"']*record\.py[\"']?[ \t]+router\b")
KEEP = re.compile(START + r"(?:python3?(?:[ \t]+-\S+)*[ \t]+)?[\"']?(?:[^\s\"']*/)?record\.py[\"']?[ \t]+keep\b([^;&|)\n]*)")
JUDGE = re.compile(START + r"(?:python3?(?:[ \t]+-(?:I|B|u))*[ \t]+)?[\"']?(?:[^\s\"']*/)?record\.py[\"']?[ \t]+judge\b([^;&|)\n]*)")
MARKER_TEXT = r"<!-- fnl-review kind=(code|security) head=[0-9a-f]{7,40} verdict=(APPROVE|REWORK)(?: lane=yes)? -->"
MARKER = re.compile("^" + MARKER_TEXT)
MARKER_LINE = re.compile("^" + MARKER_TEXT, re.M)
DEPTH = re.compile(r"--depth[\s=]+([A-Z]+)\b")
TRIGGER = re.compile(r"--trigger[\s=]+([a-z-]+)\b")
TASKS = re.compile(r"--tasks[\s=]+(\d{1,3})(?!\S)")
REASON = re.compile(r"--reason[\s=]+([a-z-]+)(?!\S)")
ROUTED = re.compile(r"--route-by[\s=]+(\S+)")
VALUE_FLAGS = {"--repo", "-R", "--body", "-b", "--body-file", "-F"}
REFRESH = Path(__file__).resolve().parent.parent / "skills/fnl-status/scripts/refresh.py"
REFRESH_EVERY = 10  # seconds between rebuilds while tools run, so an open dashboard stays current
REFRESH_SECONDS = 8
REFRESH_AFTER_TOOL_SECONDS = 4  # under the PostToolUse hook's own timeout
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "apply_patch"}  # apply_patch is Codex's edit tool
AGY_SHELL = {"run_command"}
AGY_EDIT = {"write_file", "write_to_file", "replace_file_content", "multi_replace_file_content"}
HEAD_BYTES = 4096
MAX_COMMAND = 8192  # longer command text is not tested at all: a trigger is never that long


def fnl_name(value):
    """The `fnl-` name inside "plugin:fnl-name" or "fnl-name", else None."""
    if not isinstance(value, str):
        return None
    name = value.rsplit(":", 1)[-1]
    return name if fm.NAME.match(name) else None


def first_line(path):
    """First line of a regular file, at most HEAD_BYTES bytes, never following a symlink or waiting on a pipe. None when unreadable."""
    try:
        fd = os.open(path, os.O_RDONLY | fm.NOFOLLOW | getattr(os, "O_NONBLOCK", 0))
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        return os.read(fd, HEAD_BYTES).decode("utf-8", "replace").split("\n", 1)[0]
    finally:
        os.close(fd)


def parse_words(words):
    """(pr number, --body value, --body-file value) from the words after `gh pr comment`; None for a part not found."""
    pr = body = body_file = None
    tokens = iter(words)
    for word in tokens:
        name, has_value, value = word.partition("=")
        if name in VALUE_FLAGS:
            value = value if has_value else next(tokens, None)
            if name in ("--body-file", "-F"):
                body_file = value
            elif name in ("--body", "-b"):
                body = value
        elif pr is None and not word.startswith(("-", "<")):
            found = re.fullmatch(r"(\d+)", word) or re.search(r"/pull/(\d+)", word)
            pr = int(found.group(1)) if found else None
    return pr, body, body_file


def comment_args(first_line, whole):
    """The arguments of a `gh pr comment`. The first line is tried first, because a heredoc body below it may hold
    anything, quotes included; the whole text is tried when the first line alone is not a complete command, as
    with a quoted --body that spans lines."""
    for text in (first_line, whole):
        try:
            parsed = parse_words(shlex.split(text))
        except ValueError:
            continue
        if parsed[0] is not None and (parsed[1] is not None or parsed[2] is not None):
            return parsed
    return None, None, None


def reviews_from(command, cwd):
    """[(kind, verdict, pr)] for each `gh pr comment` in the command whose body starts with a review marker.

    The body comes from --body-file (first line of the file), from --body, or from stdin: a
    heredoc, a pipe, or --body "$(cat <<EOF", where the marker line is in the command text
    itself and the k-th stdin comment takes the k-th marker line.
    """
    markers = iter(MARKER_LINE.finditer(command))
    found = []
    for posted in GH_COMMENT.finditer(command):
        pr, body, body_file = comment_args(posted.group(1), command[posted.start(1):])
        if pr is None:
            continue
        if body_file == "-" or (body is not None and body.lstrip().startswith("$(")):
            marker = next(markers, None)
        elif body_file is not None:
            line = first_line(Path(cwd) / os.path.expanduser(body_file))
            marker = MARKER.match(line) if line else None
        elif body is not None:
            marker = MARKER.match(body.split("\n", 1)[0])
        else:
            marker = None
        if marker:
            found.append((marker.group(1), marker.group(2), pr))
    return found


def refresh_dashboard(seconds=REFRESH_SECONDS, extra=()):
    """Rebuild the dashboard data. A slow or missing refresh is not an error."""
    if not REFRESH.is_file():
        return
    try:
        subprocess.run([sys.executable, "-I", str(REFRESH), "run", *extra],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=seconds)
    except subprocess.TimeoutExpired:
        pass


def refresh_if_stale():
    """Rebuild at most once per REFRESH_EVERY seconds. The stat here spares most tool calls a process; the script
    checks again under its lock, so two hooks that both pass the stat still rebuild once."""
    try:
        if fm.now().timestamp() - (fm.state_dir() / "data.js").stat().st_mtime < REFRESH_EVERY:
            return
    except OSError:
        pass  # no data.js yet
    refresh_dashboard(REFRESH_AFTER_TOOL_SECONDS, ("--throttle", str(REFRESH_EVERY)))


def options(argv):
    """(host, event) from the command line. An unknown host is recorded as "other"."""
    host, event, words = "claude", None, iter(argv)
    for word in words:
        if word == "--host":
            host = next(words, "claude")
        elif word == "--event":
            event = next(words, None)
    return (host if host in fm.HOSTS else "other"), event


def read_payload(payload, host, event):
    """Normalize a hook payload to (event, session id, cwd, source, tool, tool input) in Claude Code's vocabulary."""
    if host == "antigravity":
        folders = payload.get("workspacePaths")
        cwd = folders[0] if isinstance(folders, list) and folders and isinstance(folders[0], str) else os.getcwd()
        call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        tool = "Bash" if call.get("name") in AGY_SHELL else "Edit" if call.get("name") in AGY_EDIT else None
        data = {"command": args.get("CommandLine") or args.get("command")} if tool == "Bash" else {}
        name = {"session_start": "SessionStart", "post_tool_use": "PostToolUse"}.get(event)
        return name, payload.get("conversationId"), cwd, None, tool, data
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    return (payload.get("hook_event_name"), payload.get("session_id"), payload.get("cwd") or os.getcwd(),
            payload.get("source"), payload.get("tool_name"), data)


def session_start(sid, cwd, source, host):
    dispatch = os.environ.get("FNL_DISPATCH_ID")
    source = "resume" if source == "fork" else source if source in fm.SOURCES else "startup"
    fm.record("session_start", sid, cwd, host=host, dispatch=dispatch if fm.valid_id(dispatch) else None, source=source)
    consent = fm.read_consent()
    if consent:
        fm.prune(consent["retention_days"])
        if host != "antigravity":  # its hook is not async, and a refresh must not hold up the start of a session
            refresh_dashboard()


def post_tool_use(sid, cwd, tool, data):
    if tool == "Skill":
        name = fnl_name(data.get("skill"))
        if name:
            fm.record("skill", sid, cwd, name=name)
    elif tool == "Agent":
        name = fnl_name(data.get("subagent_type"))
        if name:
            fm.record("agent", sid, cwd, name=name)
    elif tool in EDIT_TOOLS:
        if fm.first_edit(sid):
            fm.record("first_edit", sid, cwd)
    elif tool == "Bash":
        command = data.get("command")
        judge_command = command
        if isinstance(command, list) and all(isinstance(word, str) for word in command):
            judge_command = shlex.join(command)  # keep argv quotes for receipt recognition
            command = " ".join(command)  # an argv array, as some hosts send it
        if not isinstance(command, str) or len(command) > MAX_COMMAND:
            return
        if "commit" in command and COMMIT.search(command):  # the substring test is a cheap gate before each regex
            fm.record("commit", sid, cwd)
        for kind, verdict, pr in reviews_from(command, cwd) if "comment" in command else ():
            fm.record("review", sid, cwd, kind=kind, verdict=verdict, pr=pr)
        if "record.py" in command and ROUTER.search(command):
            depth, trigger = DEPTH.search(command), TRIGGER.search(command)
            if depth and trigger and depth.group(1) in fm.DEPTHS and trigger.group(1) in fm.TRIGGERS:
                fm.record("router", sid, cwd, depth=depth.group(1), trigger=trigger.group(1))
        if "record.py" in command and "<<" not in command:  # text inside a heredoc never ran
            for keep in KEEP.finditer(command):  # one receipt per command, each read from its own arguments
                args = keep.group(1)
                tasks, reason, routed = TASKS.search(args), REASON.search(args), ROUTED.search(args)
                fields = {"tasks": int(tasks.group(1)) if tasks else 0, "reason": reason.group(1) if reason else "",
                          "route_by": routed.group(1) if routed else "table"}
                if all(check(fields[key]) for key, check in fm.SCHEMA["kept"].items()):
                    fm.record("kept", sid, cwd, **fields)
        if "record.py" in judge_command and not any(x in judge_command for x in ("<<", "`", "$")):
            try:
                shlex.split(judge_command)  # include the script token: unmatched quotes never ran
            except ValueError:
                return
            for judge in JUDGE.finditer(judge_command):
                try:
                    prefix = judge_command[:judge.start()]
                    # An open quote or a comment before the match means this is text, not a command.
                    if shlex.split(prefix) != shlex.split(prefix, comments=True):
                        continue
                    words = iter(shlex.split(judge.group(1)))
                    fields = {}
                    for word in words:
                        flag, equal, value = word.partition("=")
                        key = flag[2:] if flag.startswith("--") else ""
                        if key not in fm.SCHEMA["judge"] or key in fields:
                            raise ValueError("invalid judge argument")
                        fields[key] = value if equal else next(words)
                    if (set(fields) == set(fm.SCHEMA["judge"])
                            and all(check(fields[key]) for key, check in fm.SCHEMA["judge"].items())
                            and fm.valid_judge_pairs(fields)):
                        fm.record("judge", sid, cwd, **fields)
                except (ValueError, StopIteration):
                    continue  # malformed commands never record or block the host


def main():
    host, hook_event = options(sys.argv[1:])
    try:
        from quota_probe import worker_guard, trigger
        if worker_guard():
            return
        # Probe consent is independent; inspect only the bounded hook event first.
        raw = sys.stdin.buffer.read(65536)
        if len(raw) == 65536:
            return
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return
        event, sid, cwd, source, tool, data = read_payload(payload, host, hook_event)
        if event in {"SessionStart", "PostToolUse"}:
            trigger()
        if not fm.enabled():
            return
        if not fm.valid_id(sid) or not isinstance(cwd, str):
            return
        if event == "SessionStart":
            session_start(sid, cwd, source, host)
        elif event == "PostToolUse":
            post_tool_use(sid, cwd, tool, data)
            if host != "antigravity":  # its hook is not async: a rebuild would hold up the tool call
                refresh_if_stale()
        elif event == "Stop" and host != "antigravity":
            refresh_dashboard()
    except Exception as error:
        fm.bump_errors(error)
    finally:
        if host == "antigravity":
            try:
                print("{}")  # its hook contract: a JSON object on stdout
            except OSError:
                pass  # the reader went away; there is nothing left to tell it


if __name__ == "__main__":
    main()
    sys.exit(0)
