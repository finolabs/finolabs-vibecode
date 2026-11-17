#!/usr/bin/env python3
"""Claude Code PreToolUse Bash hook for the away lease (CLAUDE.md, tenth scoped exception; docs/specs/afk-check-hook.md).

While a valid, unexpired away lease exists, it splits the Bash command into words in memory and judges that argv
through the same `afk.py check --coordinator claude --argv-json` code, in the hook's working folder. A Tier 3 answer,
in either mode, denies the call with one fixed message naming the code; a command that cannot be split into words is
denied with another fixed message, and once a lease is live any error denies as `unsafe`. With no live lease, or on a
Tier 1 answer, it prints nothing and returns no decision. The
command text is never stored, logged or sent: only what a `check` call keeps is written.
"""

import os
import re
import signal
import sys

PARSE_MESSAGE = 'afk: the command could not be read; write it as a simpler command'


def parked(code):
    return f'afk: {code}; this action is parked under the away lease (afk.py check)'


UNSAFE = parked('unsafe')


def deny(reason):
    import json
    os.write(1, (json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                    'permissionDecisionReason': reason}},
                            separators=(',', ':')) + '\n').encode())


def unquoted_newlines(command):
    """The command with every newline outside quotes and comments turned into a `;` separator, so each line is judged
    as its own command (shlex alone reads a newline as a space). Quotes are tracked as bash tracks them: a `#` that
    starts a word comments to the end of the line, a backslash-newline outside single quotes joins lines, and a
    `$'...'` string holding a backslash is refused. Raises ValueError on an unbalanced quote or a form it cannot read the way bash does."""
    out, single, double, i, n = [], False, False, 0, len(command)
    while i < n:
        char = command[i]
        if char == '\\' and not single:
            if i + 1 < n and command[i + 1] == '\n':
                i += 2  # line continuation: bash joins the two lines
                continue
            out.append(command[i:i + 2])
            i += 2
            continue
        if not single and not double:
            if char == '$' and i + 1 < n and command[i + 1] == "'":
                end = command.find("'", i + 2)
                if end < 0 or '\\' in command[i + 2:end]:
                    raise ValueError('ansi-c quote')
                out.append(command[i + 1:end + 1])
                i = end + 1
                continue
            if char == '#' and (i == 0 or command[i - 1] in ' \t\n;&|()<>'):
                end = command.find('\n', i)
                i = n if end < 0 else end
                continue
            if char == '\n':
                out.append(' ; ')
                i += 1
                continue
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        out.append(char)
        i += 1
    if single or double:
        raise ValueError('unbalanced quote')
    return ''.join(out)


LEASE_COMMANDS = {'stop', 'log', 'review', 'effective', 'rules', 'check', 'packet-check'}
OPERATORS = {';', '&&', '||', '|', '&', '|&'}
SAFE_ARGUMENT = re.compile(r'[A-Za-z0-9 ._,:=/@+%-]*')


def own_lease_command(argv, script):
    """True for `python3 [-I] <this install's afk.py> <lease command> ...` with no operator after it and no argument
    made of anything but letters, digits, spaces and `._,:=/@+%-`."""
    if not argv or os.path.basename(argv[0]) not in {'python3', 'python'}:
        return False
    rest = argv[1:]
    while rest and rest[0] in {'-I', '-B', '-u'}:
        rest = rest[1:]
    if len(rest) < 2 or rest[1] not in LEASE_COMMANDS or any(t in OPERATORS for t in rest):
        return False
    if not all(SAFE_ARGUMENT.fullmatch(word) for word in rest[1:]):
        return False  # a word bash could expand, redirect or split is judged like any command
    try:
        return os.path.realpath(rest[0]) == os.path.realpath(script)
    except (OSError, ValueError):
        return False


def expanded_paths(argv, limit=200):
    """The paths the shell would read for each word, and each whitespace-separated piece of a word, holding `~`, `$`
    or a glob character, in memory only."""
    import glob
    found = []
    for piece in (p for word in argv for p in word.split()):
        if not any(c in piece for c in '~$*?['):
            continue
        value = os.path.expandvars(os.path.expanduser(piece))
        matches = glob.glob(value) if any(c in value for c in '*?[') else [value]
        found.extend(matches[:limit])
    return found


def main():
    live = False
    try:
        def timed_out(*_):
            if live:
                deny(UNSAFE)
            os._exit(0)
        signal.signal(signal.SIGALRM, timed_out)
        signal.alarm(12)
        if os.environ.get('FNL_AFK_HOOK', '').lower() in {'off', '0', 'false', 'no'}:
            return 0

        import io
        import json
        import shlex
        import time
        from contextlib import redirect_stdout
        from pathlib import Path

        raw = sys.stdin.buffer.read(256 * 1024)
        if len(raw) == 256 * 1024:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get('tool_name') != 'Bash':
            return 0
        command = (event.get('tool_input') or {}).get('command')
        if not isinstance(command, str) or not command.strip():
            return 0

        sys.dont_write_bytecode = True
        here = Path(__file__).resolve().parent
        sys.path.insert(0, str(here))
        import away_lease
        if away_lease.live_lease(time.time()) is None:
            return 0
        live = True  # from here on every failure denies, as `check` answers `unsafe`

        try:
            argv = shlex.split(unquoted_newlines(command), comments=False, posix=True)
        except ValueError:
            deny(PARSE_MESSAGE)
            return 0
        if not argv:
            return 0
        script = here.parent / 'skills' / 'delegate' / 'scripts' / 'afk.py'
        if own_lease_command(argv, script):
            return 0

        cwd = event.get('cwd')
        if not isinstance(cwd, str) or not os.path.isdir(cwd):
            deny(UNSAFE)
            return 0
        os.chdir(cwd)
        sys.path.insert(0, str(script.parent))
        import afk

        paths = expanded_paths(argv)
        if paths and afk.floored(None, paths, cwd):
            deny(parked('floor'))
            return 0
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            afk.main(['check', '--coordinator', 'claude', '--argv-json', json.dumps(argv)])
        answer = json.loads(buffer.getvalue().strip().splitlines()[-1])
        code = answer.get('code')
        if answer.get('tier') == 1:
            return 0  # no decision: the host's own permission rules still apply
        if isinstance(code, str) and code in afk.ENDED:
            return 0
        deny(parked(code if isinstance(code, str) and code.replace('-', '').isalpha() else 'unsafe'))
    except Exception:
        if live:
            try:
                deny(UNSAFE)
            except Exception:
                pass
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
