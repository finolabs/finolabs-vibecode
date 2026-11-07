#!/usr/bin/env python3
"""Construct child environments from named allowlists; never diagnose their values."""
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

BASE_NAMES = ('PATH', 'HOME', 'LANG', 'TMPDIR', 'FNL_DISPATCH_ID')
NAME = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
SENSITIVE = re.compile(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|(?:^|_)(?:PASS|PASSWD|PASSPHRASE|AUTH|COOKIE|COOKIES|SESSION|SESSIONID|PRIVATE)(?:_|$)')
DENIED = re.compile(r'^(?:LD_|DYLD_|PYTHON|PERL5|RUBY|GIT_)|^(?:BASH_ENV|ENV|NODE_OPTIONS|NODE_EXTRA_CA_CERTS|REQUESTS_CA_BUNDLE|CURL_CA_BUNDLE|NODE_TLS_REJECT_UNAUTHORIZED|NODE_PATH|PERLLIB|SHELLOPTS|PS4|PROMPT_COMMAND|JAVA_TOOL_OPTIONS)$|_PROXY$|^SSL_CERT_')


def validate_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or DENIED.search(name):
        raise ValueError('refused environment name')
    return name


def checked_config_dir(value):
    """No-follow folder walk, matching the quota probe's directory boundary."""
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('refused config directory')
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in (*path.parts[1:], None):
            info = os.fstat(fd)
            last = part is None
            if (info.st_uid not in ({os.getuid()} if last else {0, os.getuid()})
                    or info.st_mode & 0o022 or not stat.S_ISDIR(info.st_mode)):
                raise ValueError('refused config directory')
            try:
                os.stat('.git', dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise ValueError('refused config directory')
            if not last:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
    finally:
        os.close(fd)


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
        if name != 'CLAUDE_CONFIG_DIR':
            raise ValueError('refused explicit environment setting')
        checked_config_dir(value)
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
