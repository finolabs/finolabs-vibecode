#!/usr/bin/env bash
set -e
git init -q .
printf '# Demo app\n\nA small demo repository.\n' > CLAUDE.md
mkdir -p src && echo 'print(1)' > src/app.py
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
