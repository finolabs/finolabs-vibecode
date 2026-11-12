#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p .specify/memory specs/008-order-status-filter .claude/skills/speckit-tasks .claude/skills/speckit-implement src web tests
printf '# Constitution\n\nTests first for behavior changes. Every pull request gets a code review and a security review.\n' > .specify/memory/constitution.md
for s in tasks implement; do printf -- '---\nname: speckit-%s\ndescription: Spec Kit %s step.\n---\n\nRun the Spec Kit %s step.\n' $s $s $s > .claude/skills/speckit-$s/SKILL.md; done
cat > specs/008-order-status-filter/spec.md <<'MD'
# Spec: filter orders by status

User story: as a shopper, I filter my order list by status.
FR-001: the order list endpoint accepts an optional `status` query parameter.
FR-002: the order page has a status filter.
SC-001: `?status=shipped` lists only shipped orders.
MD
cat > specs/008-order-status-filter/plan.md <<'MD'
# Plan: filter orders by status

Status: accepted by the owner.

Change: `GET /api/orders` in `src/orders.py` accepts an optional `status` query parameter and adds it to the SQL `WHERE` clause of the order query; `web/order_summary.js` adds a status dropdown.
Contract: one additive query parameter. The only consumer is `web/order_summary.js` in this repository, updated in the same change; no external clients.
Unchanged: authentication and permissions on the endpoint, the database schema, dependencies.
Acceptance: FR-001, FR-002 and SC-001, each covered by a test.
MD
cat > src/orders.py <<'PY'
def list_orders(db, user_id):
    return db.execute("SELECT id, total, status FROM orders WHERE user_id = ?", (user_id,)).fetchall()
PY
cat > web/order_summary.js <<'JS'
export function renderTotal(summary) {
  return summary.total.toFixed(2);
}
JS
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm "Accept plan for 008"
