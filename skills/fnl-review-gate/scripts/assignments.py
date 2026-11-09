#!/usr/bin/env python3
"""Parse, validate and render the `## Assignment matrix` section of the host config.

Pure module: it works on text and plain values, reads no file or environment and runs no command.
Nothing is repaired or guessed, and no problem reason ever repeats the text it rejected.
"""
from datetime import date
import re

HEADING = '## Assignment matrix'
TYPES = ('frontend', 'design', 'video', 'three-d', 'image-generation', 'transcription')
ROLES = ('code-review', 'security-review', 'navigator')
NAME = re.compile(r'claude|codex|antigravity|claude[a-z0-9]{1,24}')
MODEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9.-]{0,63}')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
CONSENT = re.compile(r'yes \((\d{4}-\d{2}-\d{2})\)|no')
LEVELS = re.compile(r'levels ([1-5])-([1-5])')
WORD = re.compile(r'[a-z][a-z0-9-]{0,31}')
MAX_AGENTS = 8
MAX_TYPES = 4
MAX_LINES = 200


def real_date(text):
    if not isinstance(text, str) or not DATE.fullmatch(text):
        return False
    try:
        date(int(text[:4]), int(text[5:7]), int(text[8:]))
    except ValueError:
        return False
    return True


def headings(text):
    """Offsets and titles of level-one and level-two headings outside code fences, and whether a fence stays open."""
    found, fence, offset = [], None, 0
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
        elif fence is None and re.match(r'^#{1,2} ', line):
            found.append((offset, line.strip()))
        offset += len(line)
    return found, fence is not None


def check_values(values):
    if not isinstance(values, dict) or set(values) != {'consent', 'date', 'judge', 'agents'}:
        raise ValueError
    if values['consent'] == 'yes':
        if not real_date(values['date']):
            raise ValueError
    elif values['consent'] != 'no' or values['date'] != '':
        raise ValueError
    if values['judge'] not in ('jev', 'host'):
        raise ValueError
    agents = values['agents']
    if not isinstance(agents, dict) or len(agents) > MAX_AGENTS:
        raise ValueError
    named = set()
    for name, entry in agents.items():
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ValueError
        if not isinstance(entry, dict) or set(entry) != {'levels', 'works', 'model', 'roles'}:
            raise ValueError
        levels = entry['levels']
        if (not isinstance(levels, (list, tuple)) or len(levels) != 2 or any(type(n) is not int for n in levels)
                or not 1 <= levels[0] <= levels[1] <= 5):
            raise ValueError
        works, roles, model = entry['works'], entry['roles'], entry['model']
        if (not isinstance(works, list) or len(works) > MAX_TYPES or len(set(works)) != len(works)
                or any(not isinstance(t, str) or t not in TYPES for t in works)):
            raise ValueError
        if model is not None and (not isinstance(model, str) or not MODEL.fullmatch(model)):
            raise ValueError
        if (not isinstance(roles, list) or len(set(roles)) != len(roles)
                or any(not isinstance(r, str) or r not in ROLES for r in roles) or named & set(roles)):
            raise ValueError
        named |= set(roles)


def validate(values):
    """Raise ValueError('values') for anything outside the rules; never carries the offending text."""
    try:
        check_values(values)
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError('values') from None


def render(values):
    validate(values)
    first = f"- Consent: yes ({values['date']})" if values['consent'] == 'yes' else '- Consent: no'
    lines = [first, f"- Judge: {values['judge']}"]
    for name, entry in values['agents'].items():
        low, high = entry['levels']
        parts = [f'levels {low}-{high}']
        if entry['works']:
            parts.append('works on ' + ', '.join(entry['works']))
        if entry['model'] is not None:
            parts.append('model ' + entry['model'])
        if entry['roles']:
            parts.append('roles ' + ', '.join(entry['roles']))
        lines.append(f'- {name}: ' + '; '.join(parts))
    return f'{HEADING}\n\n' + '\n'.join(lines) + '\n\n'


class Matrix:
    """The reading of one host text: state is `absent`, `valid` or `invalid`."""

    def __init__(self):
        self.state = 'absent'
        self.consent = None
        self.date = ''
        self.judge = None
        self.agents = {}
        self.roles = {}
        self.problems = []

    def to_values(self):
        return {'consent': self.consent, 'date': self.date, 'judge': self.judge,
                'agents': {name: {'levels': tuple(entry['levels']), 'works': list(entry['works']),
                                  'model': entry['model'], 'roles': list(entry['roles'])}
                           for name, entry in self.agents.items()}}


def agent_fields(rest, problem):
    entry = {'levels': (1, 5), 'works': [], 'model': None, 'roles': []}
    parts = rest.split('; ')
    match = LEVELS.fullmatch(parts[0])
    if match and int(match[1]) <= int(match[2]):
        entry['levels'] = (int(match[1]), int(match[2]))
    else:
        problem('bad levels')
    stage = 0
    for part in parts[1:]:
        if part.startswith('works on '):
            number = 1
        elif part.startswith('model '):
            number = 2
        elif part.startswith('roles '):
            number = 3
        else:
            problem('unknown key')
            continue
        if number <= stage:
            problem('unknown key')
            continue
        stage = number
        if number == 1:
            items = part[9:].split(', ')
            for item in items:
                if item not in TYPES:
                    problem('unknown type')
            if len(set(items)) != len(items):
                problem('duplicate type')
            if len(items) > MAX_TYPES:
                problem('too many types')
            entry['works'] = [t for t in dict.fromkeys(items) if t in TYPES]
        elif number == 2:
            model = part[6:]
            if MODEL.fullmatch(model):
                entry['model'] = model
            else:
                problem('bad model')
        else:
            items = [] if part[6:] == 'none' else part[6:].split(', ')
            for item in items:
                if item not in ROLES:
                    problem('unknown role')
            if len(set(items)) != len(items):
                problem('duplicate role')
            entry['roles'] = [r for r in dict.fromkeys(items) if r in ROLES]
    return entry


def parse(text):
    """Read the section from host text; never raises and never echoes input."""
    matrix = Matrix()

    def problem(reason):
        if reason not in matrix.problems:
            matrix.problems.append(reason)

    try:
        if not isinstance(text, str):
            raise ValueError
        found, unclosed = headings(text)
        indexes = [i for i, (_, title) in enumerate(found) if title == HEADING]
        if not indexes:
            return matrix
        matrix.state = 'invalid'
        if len(indexes) > 1:
            problem('duplicate section')
            return matrix
        if unclosed:
            problem('ambiguous section')
            return matrix
        index = indexes[0]
        end = found[index + 1][0] if index + 1 < len(found) else len(text)
        body = [line for line in text[found[index][0]:end].splitlines()[1:] if line.strip()]
        if len(body) > MAX_LINES:
            problem('too long')
            return matrix
        consent_seen = judge_seen = False
        for line in body:
            key, sep, rest = line[2:].partition(': ') if line.startswith('- ') else ('', '', '')
            if not sep:
                problem('unknown key')
            elif key == 'Consent':
                if consent_seen:
                    problem('duplicate consent')
                    continue
                consent_seen = True
                match = CONSENT.fullmatch(rest)
                if match and (match[1] is None or real_date(match[1])):
                    matrix.consent, matrix.date = ('yes', match[1]) if match[1] else ('no', '')
                else:
                    problem('bad consent')
            elif key == 'Judge':
                if judge_seen:
                    problem('duplicate judge')
                    continue
                judge_seen = True
                if rest in ('jev', 'host'):
                    matrix.judge = rest
                else:
                    problem('bad judge')
            elif NAME.fullmatch(key):
                if key in matrix.agents:
                    problem('duplicate agent')
                    continue
                if len(matrix.agents) >= MAX_AGENTS:
                    problem('too many agents')
                    continue
                matrix.agents[key] = agent_fields(rest, problem)
            else:
                problem('unknown agent' if WORD.fullmatch(key) else 'unknown key')
        if not consent_seen:
            problem('missing consent')
        if not judge_seen:
            problem('missing judge')
        roles = {}
        for name, entry in matrix.agents.items():
            for role in entry['roles']:
                if role in roles:
                    problem('duplicate role')
                roles[role] = name
        if matrix.problems:
            matrix.judge = None
            return matrix
        matrix.state, matrix.roles = 'valid', roles
        return matrix
    except Exception:
        matrix = Matrix()
        matrix.state, matrix.problems = 'invalid', ['unreadable']
        return matrix
