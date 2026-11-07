#!/usr/bin/env python3
"""Construct child environments from named allowlists; never diagnose their values."""
import os
from pathlib import Path
import re
import subprocess
import sys

BASE_NAMES = ('PATH', 'HOME', 'LANG', 'TMPDIR', 'FNL_DISPATCH_ID')
NAME = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
SENSITIVE = re.compile(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL')
DENIED = re.compile(r'^(?:LD_|DYLD_|PYTHON|PERL5|RUBY|GIT_)|^(?:BASH_ENV|ENV|NODE_OPTIONS)$|_PROXY$|^SSL_CERT_')


def validate_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or DENIED.search(name):
        raise ValueError('refused environment name')
    return name


def environment(source=None, names=(), explicit=None):
    """Read only selected keys. Callers supply synthetic mappings in tests."""
    source = os.environ if source is None else source
    names = tuple(names)
    if len(set(names)) != len(names):
        raise ValueError('duplicate environment name')
    for name in names:
        validate_name(name)
    result = {name: source[name] for name in (*BASE_NAMES, *names) if name in source}
    for name, value in (explicit or {}).items():
        # Only the Claude command form selects a login directory explicitly.
        if name != 'CLAUDE_CONFIG_DIR' or not Path(value).is_absolute():
            raise ValueError('refused explicit environment setting')
        result[name] = str(value)
    return result


def main():
    argv = sys.argv[1:]
    if argv[:1] == ['--']:
        argv = argv[1:]
    if not argv:
        print('run_env: refused', file=sys.stderr)
        return 2
    try:
        return subprocess.call(argv, env=environment())
    except (OSError, ValueError):
        print('run_env: refused', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
