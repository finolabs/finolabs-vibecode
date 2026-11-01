#!/usr/bin/env bash
set -e
git init -q .
printf '# Demo app\n' > CLAUDE.md
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
