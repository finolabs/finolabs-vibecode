#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p .specify/memory specs src tests
printf '# Constitution\n\nTests first for behavior changes. Every pull request gets a code review and a security review.\n' > .specify/memory/constitution.md
for s in specify clarify plan tasks implement; do
  mkdir -p .claude/skills/speckit-$s
  printf -- '---\nname: speckit-%s\ndescription: Spec Kit %s step.\n---\n\nRun the Spec Kit %s step.\n' $s $s $s > .claude/skills/speckit-$s/SKILL.md
done
cat > src/orders.py <<'PY'
def list_orders(db, user_id):
    return db.execute("SELECT id, total, status FROM orders WHERE user_id = ?", (user_id,)).fetchall()
PY
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
