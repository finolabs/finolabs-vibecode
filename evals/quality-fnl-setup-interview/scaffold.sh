#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
printf '# Demo app\n\nA small demo repository.\n' > CLAUDE.md
mkdir -p src && echo 'print(1)' > src/app.py
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
