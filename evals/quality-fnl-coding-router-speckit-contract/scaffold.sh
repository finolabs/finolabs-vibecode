#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p .specify/memory specs/007-order-currency .claude/skills/speckit-tasks .claude/skills/speckit-implement src web tests
printf '# Constitution\n\nTests first for behavior changes. Every pull request gets a code review and a security review.\n' > .specify/memory/constitution.md
for s in tasks implement; do printf -- '---\nname: speckit-%s\ndescription: Spec Kit %s step.\n---\n\nRun the Spec Kit %s step.\n' $s $s $s > .claude/skills/speckit-$s/SKILL.md; done
cat > specs/007-order-currency/spec.md <<'MD'
# Spec: show the order currency

User story: as a shopper, I see the currency next to my order total.
FR-001: the order summary response includes the order's currency code.
FR-002: the order page shows the total with its currency code.
SC-001: an order in EUR shows "42.00 EUR".
MD
cat > specs/007-order-currency/plan.md <<'MD'
# Plan: show the order currency

Status: accepted by the owner.

Change: `GET /api/orders/{id}/summary` in `src/orders.py` adds a `currency` field (ISO 4217 code, already stored on each order) to its JSON response; `web/order_summary.js` renders `total currency`.
Contract: one additive response field. The only consumer is `web/order_summary.js` in this repository, updated in the same change; no external clients.
Unchanged: authentication and permissions on the endpoint, the database schema, dependencies.
Acceptance: FR-001, FR-002 and SC-001, each covered by a test.
MD
cat > src/orders.py <<'PY'
def order_summary(order):
    return {"id": order["id"], "total": order["total"]}
PY
cat > web/order_summary.js <<'JS'
export function renderTotal(summary) {
  return summary.total.toFixed(2);
}
JS
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm "Accept plan for 007"
