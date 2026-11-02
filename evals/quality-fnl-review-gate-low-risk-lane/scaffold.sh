#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
printf '# Demo app\n\nAgents: pull requests follow the fnl-review-gate pull request rules.\n' > AGENTS.md
cat > pr-51.txt <<'TXT'
Pull request #51 "Tidy the README", files changed:
  README.md        | 12 ++++++------
  CHANGELOG.md     |  2 +-
TXT
cat > pr-52.txt <<'TXT'
Pull request #52 "Tidy the docs", files changed:
  README.md                      | 8 ++++----
  skills/demo-deploy/SKILL.md    | 3 ++-
TXT
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
