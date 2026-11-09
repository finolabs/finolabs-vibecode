#!/usr/bin/env python3
"""Claude Code hook that records usage metadata (see fnl_metrics.py).

Reads one hook payload from stdin and writes at most one event. `--host claude|codex|antigravity`
says which agent sent it (default claude); Antigravity payloads carry no event name, so `--event
session_start|post_tool_use` says which hook fired. It prints nothing (Antigravity wants `{}`), except one
fixed router reminder on Claude Code at a session's first edit with no router receipt, and always
exits 0, so it can never fail or block the session. It reads command text only to test for a
trigger and discards it, and reads a submitted prompt only for a leading `/fnl-` skill name and
discards it; the only file it opens is a review body named in a `gh pr comment` command, and only
the first line of that file is read.
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
TASK = re.compile(START + r"(?:python3?(?:[ \t]+-(?:I|B|u))*[ \t]+)?[\"']?(?:[^\s\"']*/)?record\.py[\"']?[ \t]+task\b([^;&|)\n]*)")
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
ROUTER_SKILL = "fnl-coding-router"
# A typed skill or slash command: "/name" or "/plugin:name" at the very start of the prompt, then whitespace or the end.
TYPED = re.compile(r"/(?:[A-Za-z0-9_.-]{1,64}:)?(fnl-[a-z][a-z-]{0,39})(?:[ \t\r\n]|\Z)")
REMINDER = ("fnl: this session edited a file before any fnl-coding-router receipt; invoke the fnl-coding-router skill "
            "before further coding work (advisory reminder, shown once per session).")


def router_mark(sid, create):
    """Whether the session has a router receipt, from a marker file beside the first-edit marker; create=True records one."""
    folder = fm.ensure_dir(fm.ensure_dir(fm.state_dir(), follow=True) / "markers")
    path = folder / (sid + ".router")  # a session id never holds a dot, so this never meets a first-edit marker
    if not create:
        return os.path.lexists(path)
    try:
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | fm.NOFOLLOW, 0o600))
    except FileExistsError:
        pass
    return True


def record_skill(sid, cwd, name):
    if fm.record("skill", sid, cwd, name=name) and name == ROUTER_SKILL:
        router_mark(sid, True)


def typed_skill(prompt):
    """The `fnl-` name of a skill typed as a slash command at the start of the prompt, else None. The text is discarded."""
    if not isinstance(prompt, str):
        return None
    found = TYPED.match(prompt[:200])
    return found.group(1) if found else None


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


def refresh_dashboard(seconds=REFRESH_SECONDS, extra=(), cwd=None):
    """Rebuild the dashboard data. A slow or missing refresh is not an error."""
    if not REFRESH.is_file():
        return
    try:
        subprocess.run([sys.executable, "-I", str(REFRESH), "run", *extra, *(["--cwd", cwd] if cwd else [])],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=seconds)
    except subprocess.TimeoutExpired:
        pass


def start_detached_refresh(cwd=None):
    """Antigravity cannot wait for a rebuild. Probe the OS lock before starting one."""
    if not fm.enabled() or not REFRESH.is_file():
        return
    fd = None
    try:
        # The isolated child drops state overrides. Consent guarantees this
        # canonical state folder exists; probe the same lock the child will use.
        root = fm.dr.consent_root()
        if root is None:
            return
        folder = root / "state"
        fd = os.open(folder / "refresh.lock", os.O_RDWR | os.O_CREAT | fm.NOFOLLOW | getattr(os, "O_NONBLOCK", 0), 0o600)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        # No host, project, Python injection or quota variables are inherited.
        env = {k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ}
        for switch in ("FNL_AGENT_SNAPSHOT", "FNL_PROGRESS"):
            if os.environ.get(switch, "").lower() == "off":
                env[switch] = "off"
        subprocess.Popen([sys.executable, "-I", str(REFRESH), "run", "--throttle", "10", *(["--cwd", cwd] if cwd else [])],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=env, cwd=str(REFRESH.parent), close_fds=True, start_new_session=True)
    except (OSError, ValueError):
        pass
    finally:
        if fd is not None:
            os.close(fd)


def refresh_if_stale(cwd=None):
    """Rebuild at most once per REFRESH_EVERY seconds. The stat here spares most tool calls a process; the script
    checks again under its lock, so two hooks that both pass the stat still rebuild once."""
    try:
        if fm.now().timestamp() - (fm.state_dir() / "data.js").stat().st_mtime < REFRESH_EVERY:
            return
    except OSError:
        pass  # no data.js yet
    refresh_dashboard(REFRESH_AFTER_TOOL_SECONDS, ("--throttle", str(REFRESH_EVERY)), cwd=cwd)


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
        import project_progress as pp
        if pp.enabled() and pp.notice('session', pp.installed_version()):
            print(pp.NOTICE, file=sys.stderr if host == 'antigravity' else sys.stdout)
        if host != "antigravity":
            refresh_dashboard(cwd=cwd)
        else:
            start_detached_refresh(cwd=cwd)


def post_tool_use(sid, cwd, tool, data, host="claude"):
    if tool == "Skill":
        name = fnl_name(data.get("skill"))
        if name:
            record_skill(sid, cwd, name)
    elif tool == "Agent":
        name = fnl_name(data.get("subagent_type"))
        if name:
            fm.record("agent", sid, cwd, name=name)
    elif tool in EDIT_TOOLS:
        if fm.first_edit(sid):
            fm.record("first_edit", sid, cwd)
            # Claude Code reads this JSON from an async hook as context for the next turn. Codex's output contract is
            # unverified and Antigravity's hook must print `{}`, so both stay advisory.
            if host == "claude" and not router_mark(sid, False):
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": REMINDER}}))
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
                if fm.record("router", sid, cwd, depth=depth.group(1), trigger=trigger.group(1)):
                    router_mark(sid, True)
        if "record.py" in command and "<<" not in command:  # text inside a heredoc never ran
            for keep in KEEP.finditer(command):  # one receipt per command, each read from its own arguments
                args = keep.group(1)
                tasks, reason, routed = TASKS.search(args), REASON.search(args), ROUTED.search(args)
                fields = {"tasks": int(tasks.group(1)) if tasks else 0, "reason": reason.group(1) if reason else "",
                          "route_by": routed.group(1) if routed else "table"}
                if all(check(fields[key]) for key, check in fm.SCHEMA["kept"].items()):
                    fm.record("kept", sid, cwd, **fields)
        if "record.py" in judge_command and not any(x in judge_command for x in ("<<", "`", "$(")):
            try:
                shlex.split(judge_command)  # include the script token: unmatched quotes never ran
            except ValueError:
                return
            receipts = [(event, receipt) for event, pattern in (("judge", JUDGE), ("task", TASK))
                        for receipt in pattern.finditer(judge_command)]
            for event, judge in receipts:
                if "$" in judge.group():
                    continue  # expanded receipt arguments cannot be validated from command text
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
                        if key not in fm.SCHEMA[event] or key in fields:
                            raise ValueError("invalid judge argument")
                        fields[key] = value if equal else next(words)
                    if (set(fields) == set(fm.SCHEMA[event])
                            and all(check(fields[key]) for key, check in fm.SCHEMA[event].items())
                            and (event != "judge" or fm.valid_judge_pairs(fields))):
                        fm.record(event, sid, cwd, **fields)
                except (ValueError, StopIteration):
                    continue  # malformed commands never record or block the host


def bounded_payload(raw):
    """Keep complete top-level fields from a capped JSON object, never its tail."""
    if len(raw) < 65536:
        return json.loads(raw)
    text = raw.decode("utf-8", "ignore").lstrip()
    if not text.startswith("{"):
        return {}
    decoder, payload, index = json.JSONDecoder(), {}, 1
    whitespace = re.compile(r"\s*")
    try:
        while True:
            index = whitespace.match(text, index).end()
            key, index = decoder.raw_decode(text, index)
            if not isinstance(key, str):
                break
            index = whitespace.match(text, index).end()
            if text[index:index + 1] != ":":
                break
            index += 1
            index = whitespace.match(text, index).end()
            value, index = decoder.raw_decode(text, index)
            payload[key] = value
            index = whitespace.match(text, index).end()
            if text[index:index + 1] != ",":
                break
            index += 1
    except ValueError:
        pass  # The final field may be cut anywhere, including within UTF-8.
    return payload


def main():
    host, hook_event = options(sys.argv[1:])
    try:
        if not fm.enabled():
            return
        raw = sys.stdin.buffer.read(65536)
        payload = bounded_payload(raw)
        if not isinstance(payload, dict):
            return
        event, sid, cwd, source, tool, data = read_payload(payload, host, hook_event)
        if not fm.valid_id(sid) or not isinstance(cwd, str):
            return
        if event == "SessionStart":
            session_start(sid, cwd, source, host)
        elif event == "PostToolUse":
            post_tool_use(sid, cwd, tool, data, host)
            if host != "antigravity":
                refresh_if_stale(cwd=cwd)
            else:
                start_detached_refresh(cwd=cwd)
        elif event == "UserPromptSubmit" and host == "claude":
            name = typed_skill(payload.get("prompt"))
            if name:
                record_skill(sid, cwd, name)
        elif event == "Stop" and host != "antigravity":
            refresh_dashboard(cwd=cwd)
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
