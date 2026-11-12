#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
printf '# Demo app\n\nAgents: pull requests follow the review-gate pull request rules.\n' > AGENTS.md
cat > pr-42.json <<'JSON'
{
  "author": {"login": "demo-owner"},
  "headRefOid": "2222222222222222222222222222222222222222",
  "comments": [
    {"author": {"login": "demo-reviewer"}, "createdAt": "2026-11-02T01:00:00Z", "includesCreatedEdit": false, "body": "<!-- fnl-review kind=code head=2222222222222222222222222222222222222222 verdict=APPROVE -->\nCode review: no findings."},
    {"author": {"login": "demo-reviewer"}, "createdAt": "2026-11-02T01:05:00Z", "includesCreatedEdit": false, "body": "<!-- fnl-review kind=security head=2222222222222222222222222222222222222222 verdict=REWORK -->\nSecurity review, first pass."},
    {"author": {"login": "demo-reviewer"}, "createdAt": "2026-11-02T01:30:00Z", "includesCreatedEdit": false, "body": "<!-- fnl-review kind=security head=2222222222222222222222222222222222222222 verdict=APPROVE -->\nSecurity review, after the native /security-review pass."}
  ],
  "reviews": []
}
JSON
printf '{"demo-owner": "admin", "demo-reviewer": "write"}\n' > permissions.json
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
