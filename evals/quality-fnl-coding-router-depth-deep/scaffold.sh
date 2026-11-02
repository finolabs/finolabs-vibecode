#!/usr/bin/env bash
set -e
git init -q .
printf '# Invoices\n\nTo recieve invoices by email, set `INVOICE_EMAIL`.\n' > README.md
mkdir -p src tests
cat > src/auth.py <<'PY'
def can_delete_invoice(user, invoice):
    """Only the owning tenant's billing admins may delete an invoice."""
    return user.tenant_id == invoice.tenant_id and "billing-admin" in user.roles
PY
cat > tests/test_auth.py <<'PY'
from types import SimpleNamespace as NS
from src.auth import can_delete_invoice

def test_other_tenant_cannot_delete():
    user = NS(tenant_id="t1", roles=["billing-admin"])
    assert not can_delete_invoice(user, NS(tenant_id="t2"))
PY
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
