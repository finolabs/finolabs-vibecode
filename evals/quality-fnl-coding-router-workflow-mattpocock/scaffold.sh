#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p src tests
for s in grilling tdd diagnosing-bugs prototype code-review to-spec to-tickets implement; do
  mkdir -p .claude/skills/$s
  printf -- '---\nname: %s\ndescription: The %s step from a workflow skill pack.\n---\n\nRun the %s step.\n' $s $s $s > .claude/skills/$s/SKILL.md
done
printf '# Shop\n\nWe use the skills in .claude/skills (mattpocock/skills). Run the tests with `python3 -m unittest`.\n' > README.md
cat > src/products.py <<'PY'
def list_products(db):
    return db.execute("SELECT id, name, price FROM products").fetchall()
PY
cat > tests/test_products.py <<'PY'
import sqlite3, unittest
from src.products import list_products

class ProductsTest(unittest.TestCase):
    def test_lists_all(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE products (id, name, price)")
        db.execute("INSERT INTO products VALUES (1, 'Mug', 5)")
        self.assertEqual(len(list_products(db)), 1)
PY
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
