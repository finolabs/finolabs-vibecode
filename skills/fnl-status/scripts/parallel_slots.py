#!/usr/bin/env python3
"""Read advisory parallel capacity from canonical local config and ledger only."""

import argparse
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))  # support python -I
import data_root as dr

FAMILIES = ('claude', 'codex', 'antigravity')
AGENTS = {'claude': 'claude', 'claude-session': 'claude', 'subagent': 'claude',
          'codex': 'codex', 'antigravity': 'antigravity'}
HOST_LIMIT = 262144
LEDGER_LIMIT = 4 * 1024 * 1024
DEFAULT_LIMIT = 5


def parse_config(text):
    """Missing/invalid total defaults to five; ambiguous caps refuse capacity."""
    sections, lines, active = 0, [], False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('## '):
            active = line == '## Limits'
            sections += active
        elif active:
            lines.append(line)
    if sections > 1:
        raise ValueError('ambiguous limits')
    totals = [line for line in lines if line.startswith('- Parallel dispatches:')]
    match = re.fullmatch(r'- Parallel dispatches: at most ([0-9]{1,2}) at one time\.', totals[0]) if len(totals) == 1 else None
    valid = match is not None and 1 <= int(match[1]) <= 32
    limit = int(match[1]) if valid else DEFAULT_LIMIT
    caps = {family: None for family in FAMILIES}
    entries = [line for line in lines if line.startswith('- Parallel per family')]
    if len(entries) > 1:
        raise ValueError('ambiguous caps')
    if entries:
        for item in entries[0].removeprefix('- Parallel per family:').split(','):
            match = re.fullmatch(r'(claude|codex|antigravity)=([0-9]{1,2})', item.strip())
            if not match or not 1 <= int(match[2]) <= limit or caps[match[1]] is not None:
                raise ValueError('invalid cap')
            caps[match[1]] = int(match[2])
    return dict(limit=limit, caps=caps, source='host config' if valid else 'default')


def config():
    if dr.consent_root() is None:
        raise ValueError('invalid root')
    try:
        text = dr.read_data('host.md', HOST_LIMIT).decode('utf-8')
    except FileNotFoundError:
        text = ''
    return parse_config(text)


def open_counts(raw):
    starts, finishes = {}, set()
    for line in raw.decode('utf-8').splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if (not isinstance(record, dict) or not isinstance(record.get('id'), str)
                or not record['id'] or record.get('event') not in ('start', 'finish')):
            raise ValueError('invalid ledger')
        identity = record['id']
        if record['event'] == 'finish':
            finishes.add(identity)
        else:
            agent = record.get('agent')
            if not isinstance(agent, str) or agent not in AGENTS:
                raise ValueError('invalid agent')
            family = AGENTS[agent]
            if identity in starts and starts[identity] != family:
                raise ValueError('ambiguous start')
            starts[identity] = family
    counts = {family: 0 for family in FAMILIES}
    for identity in starts.keys() - finishes:
        counts[starts[identity]] += 1
    return counts


def status():
    settings = config()
    try:
        raw = dr.read_data('ledger.jsonl', LEDGER_LIMIT)
    except FileNotFoundError:
        raw = b''
    counts = open_counts(raw)
    opened = sum(counts.values())
    return dict(limit=settings['limit'], open=opened, free=max(0, settings['limit'] - opened),
                families={family: dict(open=counts[family], cap=settings['caps'][family],
                    free=None if settings['caps'][family] is None else max(0, settings['caps'][family] - counts[family]))
                    for family in FAMILIES}, source=settings['source'])


def fits(state, family, count=1):
    available = state['families'][family]['free']
    return count <= state['free'] and (available is None or count <= available)


def summary():
    """Fixed words and integers only, including the default source in hook output."""
    try:
        state = status()
        parts = []
        for family in FAMILIES:
            row = state['families'][family]
            parts.append(f"{family} {row['open']} open" +
                         (f" of cap {row['cap']}" if row['cap'] is not None else ''))
        return f"{state['free']} free of {state['limit']} (" + ', '.join(parts) + f"; {state['source']})"
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return 'unknown'


def positive_count(value):
    if len(value) > 64 or not re.fullmatch(r'[0-9]+', value) or int(value) < 1:
        raise argparse.ArgumentTypeError('count must be a positive integer of at most 64 digits')
    return int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status')
    commands.add_parser('check-config')
    check = commands.add_parser('check')
    check.add_argument('--family', choices=FAMILIES, required=True)
    check.add_argument('--count', type=positive_count, default=1)
    args = parser.parse_args(argv)
    try:
        if args.command == 'check-config':
            settings = config()
            print(json.dumps(settings))
            return 0 if settings['source'] == 'host config' else 3
        state = status()
        if args.command == 'status':
            print(json.dumps(state))
            return 0
        available = fits(state, args.family, args.count)
        print('Parallel slots: available' if available else 'Parallel slots: full')
        return 0 if available else 3
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print('Parallel slots: unknown' if args.command == 'check' else 'unknown')
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
