#!/usr/bin/env python3
"""List the test modules that read a file changed since a base, grouped two per command.

Usage, from the repository root: select_tests.py [--base <ref>]   (default origin/main)

A module reads a changed file when its text names the file's path, its file name (Python
files) or its module name in an import or a quoted string. A changed file counts as changing
every copy of it: a file of the same name in another `scripts/` or `references/` folder. A
changed test module selects itself. A changed file no module names prints as
`no test names: <path>`. The only command run is `git diff --name-only`, with a fixed argv
and no shell; no test runs. Untracked files are not seen. Advisory: the text match is a
heuristic, so a module that builds a path at run time can be missed.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

COPY_FOLDERS = ('scripts', 'references')
SKIP_FOLDERS = {'node_modules', '__pycache__'}
GROUP_SIZE = 2
REF = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/@{}^~-]{0,199}')


def changed_files(base, root):
    argv = ['git', 'diff', '--name-only', '--merge-base', base, '--']
    done = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=60, check=False)
    if done.returncode:
        raise RuntimeError('git diff failed')
    return [line for line in done.stdout.splitlines() if line]


def test_modules(root):
    folder = Path(root) / 'tests'
    if not folder.is_dir():
        return {}
    return {f'tests.{path.stem}': path.read_text(encoding='utf-8', errors='replace')
            for path in sorted(folder.glob('test_*.py')) if path.is_file()}


def copy_index(root):
    """Map a file name to the relative paths of same-named files in copy folders."""
    index = {}
    for current, folders, files in os.walk(root):
        folders[:] = [f for f in folders if not f.startswith('.') and f not in SKIP_FOLDERS]
        if os.path.basename(current) not in COPY_FOLDERS:
            continue
        for name in files:
            relative = os.path.relpath(os.path.join(current, name), root).replace(os.sep, '/')
            index.setdefault(name, []).append(relative)
    return index


def copies(path, index):
    pure = PurePosixPath(path)
    if pure.parent.name not in COPY_FOLDERS:
        return [path]
    return sorted({path, *index.get(pure.name, [])})


def patterns(path):
    pure = PurePosixPath(path)
    found = [re.compile(r'(?<![\w./-])' + re.escape(path) + r'(?![\w-])')]
    if pure.suffix == '.py':
        stem = re.escape(pure.stem)
        found.append(re.compile(r'(?<![\w-])' + re.escape(pure.name) + r'(?!\w)'))
        found.append(re.compile(r'\b(?:import|from)\s+' + stem + r'\b'))
        found.append(re.compile(r'''['"]''' + stem + r'''['"]'''))
    return found


def select(root, changed):
    """Return (sorted module names, changed paths no module names)."""
    modules = test_modules(root)
    index = copy_index(root)
    chosen, unnamed = set(), []
    for path in changed:
        pure = PurePosixPath(path)
        hits = set()
        if pure.parent.as_posix() == 'tests' and pure.name.startswith('test_') and pure.suffix == '.py':
            hits.add(f'tests.{pure.stem}')
        checks = [p for copy in copies(path, index) for p in patterns(copy)]
        hits.update(name for name, text in modules.items() if any(c.search(text) for c in checks))
        if hits:
            chosen.update(hits)
        else:
            unnamed.append(path)
    return sorted(chosen), unnamed


def groups(modules):
    return [modules[i:i + GROUP_SIZE] for i in range(0, len(modules), GROUP_SIZE)]


def main(argv=None):
    parser = argparse.ArgumentParser(description='List test modules that read files changed since a base.')
    parser.add_argument('--base', default='origin/main')
    args = parser.parse_args(argv)
    if not REF.fullmatch(args.base) or '..' in args.base:
        print('select_tests: refused base', file=sys.stderr)
        return 2
    root = os.getcwd()
    try:
        changed = changed_files(args.base, root)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        print('select_tests: git diff failed; run from the repository root with a known base', file=sys.stderr)
        return 2
    if not changed:
        print('no changed files')
        return 0
    modules, unnamed = select(root, changed)
    for name in modules:
        print(name)
    for path in unnamed:
        print(f'no test names: {path}')
    if modules:
        print()
        for group in groups(modules):
            print('python3 -m unittest ' + ' '.join(group))
    return 0


if __name__ == '__main__':
    sys.exit(main())
