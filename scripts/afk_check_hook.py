#!/usr/bin/env python3
"""Claude Code PreToolUse Bash hook for the away lease (CLAUDE.md, tenth scoped exception; docs/specs/afk-check-hook.md).

While a valid, unexpired away lease exists, it splits the Bash command into words in memory and judges that argv
through the same `afk.py check --coordinator claude --argv-json` code, in the hook's working folder. A Tier 3 answer,
in either mode, denies the call with one fixed message naming the code; a command that cannot be split into words is
denied with another fixed message. Every other path, error included, allows with exit 0 and prints nothing. The
command text is never stored, logged or sent: only what a `check` call keeps is written.
"""

import os
import signal
import sys

PARSE_MESSAGE = 'afk: the command could not be read; write it as a simpler command'


def deny(reason):
    import json
    os.write(1, (json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                    'permissionDecisionReason': reason}},
                            separators=(',', ':')) + '\n').encode())


def unquoted_newlines(command):
    """The command with every newline outside quotes turned into a `;` separator, so each line is judged as its own
    command (shlex alone reads a newline as a space). Raises ValueError on an unbalanced quote."""
    out, single, double, escape = [], False, False, False
    for char in command:
        if escape:
            escape = False
        elif char == '\\' and not single:
            escape = True
        elif char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        elif char == '\n' and not single and not double:
            out.append(' ; ')
            continue
        out.append(char)
    if single or double:
        raise ValueError('unbalanced quote')
    return ''.join(out)


def main():
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(10)
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

        try:
            argv = shlex.split(unquoted_newlines(command), comments=False, posix=True)
        except ValueError:
            deny(PARSE_MESSAGE)
            return 0
        if not argv:
            return 0

        cwd = event.get('cwd')
        if isinstance(cwd, str) and os.path.isdir(cwd):
            os.chdir(cwd)
        sys.path.insert(0, str(here.parent / 'skills' / 'delegate' / 'scripts'))
        import afk

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            afk.main(['check', '--coordinator', 'claude', '--argv-json', json.dumps(argv)])
        answer = json.loads(buffer.getvalue().strip().splitlines()[-1])
        code = answer.get('code')
        if answer.get('tier') == 3 and isinstance(code, str) and code not in afk.ENDED:
            deny(f'afk: {code}; this action is parked under the away lease (afk.py check)')
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
