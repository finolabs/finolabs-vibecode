#!/usr/bin/env python3
"""Claude Code PermissionRequest hook for the away mandate (docs/specs/afk-decider.md B); every failure prints nothing
and exits 0, so the host's own prompt stays.

Only while a valid, unexpired away lease exists and FNL_AFK_PERMIT is not off. It allows this install's own afk.py
lease commands with plain arguments, and a request whose digest an away decision recorded (`afk.py log --kind decision
... --approve-request <digest>`), once. Every other request is denied with one fixed message and the request's digest.
It compares digests only: it never splits, rebuilds or stores a command, and it sends nothing anywhere.
"""

import os
import signal
import sys

INPUT_LIMIT = 1024 * 1024
LEASE_COMMANDS = {'stop', 'log', 'goal', 'review', 'effective', 'rules', 'check', 'packet-check'}
DENY = ('The user is away under an afk lease: settle this request through afk "Decide" with two options (1 run it, '
        '2 park it); to run it, record the deciding attempt with --approve-request and the digest below, then retry '
        'the same request once. Request digest: ')
PARK = ('The user is away under an afk lease and this request was denied before with no approval recorded since: park '
        'it with afk.py log --kind parked and move on to other work. Request digest: ')


def request_digest(tool, tool_input, cwd):
    """SHA-256 of the tool name, the canonical JSON of tool_input as the host sent it, and the real working folder."""
    import hashlib
    import json
    body = json.dumps({'cwd': os.path.realpath(cwd), 'input': tool_input, 'tool': tool},
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def own_interpreter(word):
    """True when `word` runs the interpreter this hook runs under (the same real file)."""
    import shutil
    if '/' in word:
        found = word if os.path.isabs(word) else None
    elif word in {'python3', 'python'}:
        path = os.environ.get('PATH', '')
        if not path or any(not os.path.isabs(entry) for entry in path.split(os.pathsep)):
            return False  # an empty or relative entry would resolve against the command's own folder
        found = shutil.which(word, path=path)
    else:
        return False
    return found is not None and os.path.realpath(found) == os.path.realpath(sys.executable)


def own_lease_command(command, cwd, script):
    """True for `python3 [-I|-B|-u]... <this install's afk.py> <lease command> [args]` where the whole command holds only
    letters, digits, spaces and `._,:=/@+%-`: no quote, operator, expansion, glob or newline, so splitting at spaces
    reads it exactly as a shell would. The interpreter must be the hook's own: an absolute path to it, or a bare python3
    or python that this PATH (absolute entries only) resolves to it, so a wrapper earlier on the PATH is not trusted."""
    import re
    if not isinstance(command, str) or not re.fullmatch(r'[A-Za-z0-9 ._,:=/@+%-]{1,4096}', command):
        return False
    words = command.split()
    if not words:
        return False
    if not own_interpreter(words[0]):
        return False
    rest = words[1:]
    while rest and rest[0] in {'-I', '-B', '-u'}:
        rest = rest[1:]
    if len(rest) < 2 or rest[1] not in LEASE_COMMANDS:
        return False
    return os.path.realpath(os.path.join(cwd, rest[0])) == os.path.realpath(script)


def answer(behavior, message=None):
    import json
    decision = {'behavior': behavior}
    if message is not None:
        decision['message'] = message
    return (json.dumps({'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': decision}},
                       separators=(',', ':')) + '\n').encode()


def main():
    try:
        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(3)
        if os.environ.get('FNL_AFK_PERMIT', '').strip().lower() in {'off', '0', 'false', 'no'}:
            return 0

        import json
        import time
        from pathlib import Path

        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get('hook_event_name', 'PermissionRequest') != 'PermissionRequest':
            return 0
        tool, tool_input, cwd = event.get('tool_name'), event.get('tool_input'), event.get('cwd')
        if (not isinstance(tool, str) or not tool or not isinstance(tool_input, dict)
                or not isinstance(cwd, str) or not os.path.isabs(cwd)):
            return 0

        sys.dont_write_bytecode = True
        here = Path(__file__).resolve().parent
        sys.path.insert(0, str(here))
        import away_lease

        current = time.time()
        if away_lease.live_lease(current) is None:
            return 0
        script = here.parent / 'skills/delegate/scripts/afk.py'
        if tool == 'Bash' and set(tool_input) <= {'command', 'description', 'timeout', 'run_in_background'} and own_lease_command(
                tool_input.get('command'), cwd, script):
            os.write(1, answer('allow'))
            return 0
        value = request_digest(tool, tool_input, cwd)
        verdict = away_lease.answer_permit(value, current)
        if verdict == 'allow':
            os.write(1, answer('allow'))
        elif verdict == 'deny':
            os.write(1, answer('deny', DENY + value))
        elif verdict == 'park':
            os.write(1, answer('deny', PARK + value))
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
