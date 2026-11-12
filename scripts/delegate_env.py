#!/usr/bin/env python3
"""Rule 2 dispatch wrapper. Canonical host config stores names and consent only.

After the child exits, when FNL_DISPATCH_ID holds a valid dispatch id, it appends one `ended` line (id, time, exit
code) to the dispatch ledger; any failure there is silent and the exit status stays the child's.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr
import run_env

REFUSED = 125

FAMILIES = ('claude', 'codex', 'antigravity', 'zcode')
DISPATCH_ID = re.compile(r'd[0-9]{8}-[0-9]{6}-[0-9a-f]{4}')  # the ids `ledger.py start` writes


class Parser(argparse.ArgumentParser):
    def error(self, message):
        print('delegate_env: refused', file=sys.stderr)
        raise SystemExit(REFUSED)


def names_from_host(text, family):
    if family not in FAMILIES:
        raise ValueError('refused family')
    # Documentation is never an opt-in; unterminated comments fail closed.
    parts, position = [], 0
    while True:
        start = text.find('<!--', position)
        if start < 0:
            parts.append(text[position:])
            break
        parts.append(text[position:start])
        end = text.find('-->', start + 4)
        if end < 0:
            raise ValueError('invalid environment section')
        position = end + 3
    text = ''.join(parts)
    if '-->' in text:
        raise ValueError('invalid environment section')
    lines = text.splitlines()
    headings = [i for i, line in enumerate(lines) if line.rstrip() == '## Delegate environment']
    if not headings:
        return []
    if len(headings) != 1:
        raise ValueError('duplicate section')
    begin = headings[0] + 1
    end = next((i for i in range(begin, len(lines)) if lines[i].startswith('## ')), len(lines))
    names = {f: [] for f in FAMILIES}
    empty = set()
    for line in lines[begin:end]:
        if not line.strip():
            continue
        match = re.fullmatch(r'- (claude|codex|antigravity|zcode): ([A-Z][A-Z0-9_]{0,63}|none)(; approved: yes)?', line)
        if not match:
            raise ValueError('invalid environment section')
        agent, name, approval = match.groups()
        if name == 'none':
            if agent in empty or names[agent] or approval:
                raise ValueError('duplicate environment name')
            empty.add(agent)
            continue
        run_env.validate_name(name)
        if agent in empty or name in names[agent] or name in (*run_env.BASE_NAMES, 'CLAUDE_CONFIG_DIR'):
            raise ValueError('duplicate environment name')
        if run_env.SENSITIVE.search(name) and not approval:
            raise ValueError('missing individual approval')
        names[agent].append(name)
    return names[family]


def environment(family, source=None, host_text=None, config_dir=None):
    if host_text is None:
        try:
            host_text = dr.read_data('host.md').decode('utf-8')
        except FileNotFoundError:
            host_text = ''
    names = names_from_host(host_text, family)
    if config_dir is not None and family != 'claude':
        raise ValueError('refused config directory')
    return run_env.environment(source, names, {'CLAUDE_CONFIG_DIR': config_dir} if config_dir is not None else None)


def prepare_logs():
    import log_scan
    with log_scan.folder_descriptor():
        pass


def record_ended(code):
    """Append `{"event": "ended", "id", "ts", "exit"}` for the dispatch in FNL_DISPATCH_ID; silent on any failure.

    Writes nothing for a missing or malformed id, an unresolved data root or a ledger that does not exist yet, and
    never records command text, output or paths."""
    try:
        ident = os.environ.get('FNL_DISPATCH_ID', '')
        if not DISPATCH_ID.fullmatch(ident) or type(code) is not int:
            return
        root = dr.consent_root()
        if root is None:
            return
        os.lstat(root / 'ledger.jsonl')  # never creates a ledger: its start line wrote it
        from datetime import datetime, timezone
        import away_lease  # the plugin's safe ledger append: no-follow, owner-checked, one appended line
        away_lease.append_ledger({'event': 'ended', 'id': ident,
                                  'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'exit': code})
    except Exception:
        pass


def main():
    parser = Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--family', required=True, choices=FAMILIES)
    parser.add_argument('--claude-config-dir')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    try:
        if not argv:
            raise ValueError('missing command')
        env = environment(args.family, config_dir=args.claude_config_dir)
        prepare_logs()
        code = subprocess.call(argv, env=env)
        record_ended(code)
        return code if 0 <= code <= 255 and code != REFUSED else 1
    except (OSError, ValueError, UnicodeError):
        print('delegate_env: refused', file=sys.stderr)
        return REFUSED


if __name__ == '__main__':
    raise SystemExit(main())
