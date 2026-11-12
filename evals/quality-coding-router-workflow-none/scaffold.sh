#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p src tests
printf '# Text utils\n\nRun the tests with `python3 -m unittest`.\n' > README.md
cat > src/text.py <<'PY'
import re

def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).lstrip("-")
PY
cat > tests/test_text.py <<'PY'
import unittest
from src.text import slugify

class SlugifyTest(unittest.TestCase):
    def test_spaces(self):
        self.assertEqual(slugify("Hello World"), "hello-world")
PY
cat > src/urls.py <<'PY'
from src.text import slugify

def article_url(title):
    return "/articles/" + slugify(title)
PY
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm init
