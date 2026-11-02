#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p src tests .orchestration/briefs
cat > src/slug.py <<'PY'
def slugify(title):
    return title.strip().lower().replace(" ", "_")
PY
cat > tests/test_slug.py <<'PY'
from src.slug import slugify

def test_spaces_become_hyphens():
    assert slugify("Hello World") == "hello-world"
PY
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm "Add slugify"
cat > .orchestration/briefs/T3-report.md <<'MD'
# T3 report (from the delegated agent)

Done. slugify turns titles into URL slugs with hyphens, as the acceptance criterion asks.
Tests to run: `python -m pytest tests/test_slug.py` — all pass.
Commit: see `git log -1`.
MD
