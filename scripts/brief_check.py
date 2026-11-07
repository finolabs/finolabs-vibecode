#!/usr/bin/env python3
"""Rule 1 brief lint. Diagnostics contain only rule identifiers and line numbers."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import secret_patterns as sp

HEADINGS = ('Task', 'Checkout', 'Context', 'Relevant files', 'Current state', 'What was tried',
            'Acceptance criteria', 'Tests to run', 'Constraints', 'Budget', 'Report')
ENV_RULE = ('never print, dump, log or assert on the process environment or any credential; '
            'tests build a synthetic environment and compare only variable names')


def lint(text):
    lines = text.splitlines()
    errors = [('rule_1_heading', 1) for name in HEADINGS if '## ' + name not in lines]
    constraints = text.split('## Constraints\n', 1)[-1].split('\n## ', 1)[0] if '## Constraints\n' in text else ''
    if ENV_RULE not in ' '.join(constraints.split()):
        errors.append(('rule_1_environment', next((i for i, line in enumerate(lines, 1)
                                                  if line == '## Constraints'), 1)))
    errors.extend(('rule_4_secret', hit['line']) for hit in sp.findings(text))
    return sorted(set(errors), key=lambda e: (e[1], e[0]))


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError()
        path = Path(sys.argv[1])
        with path.open('rb') as stream:
            raw = stream.read(sp.MAX_BYTES + 1)
        if len(raw) > sp.MAX_BYTES or b'\0' in raw:
            raise ValueError()
        errors = lint(raw.decode('utf-8'))
    except (OSError, ValueError, UnicodeError):
        errors = [('rule_1_unreadable', 1)]
    for rule, line in errors:
        print(f'{rule} line={line}')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
