#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
printf '# Demo app\n\nAgents: pull requests follow the fnl-review-gate pull request rules.\n' > AGENTS.md
cat > pr-42.json <<'JSON'
{
  "headRefOid": "2222222222222222222222222222222222222222",
  "comments": [
    {"author": {"login": "demo-owner"}, "body": "<!-- fnl-review kind=code head=2222222222222222222222222222222222222222 verdict=APPROVE -->\nCode review: no findings."},
    {"author": {"login": "demo-maintainer"}, "body": "<!-- fnl-review kind=security head=2222222222222222222222222222222222222222 verdict=APPROVE -->\nSecurity review: no trigger matched; trust paths checked: none reach auth."}
  ]
}
JSON
cat > permissions.json <<'JSON'
{"demo-owner": "admin", "demo-maintainer": "write"}
JSON
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
