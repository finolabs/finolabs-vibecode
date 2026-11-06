"""Enforce the spec status vocabulary from work-tracking.md, part C."""

import re
import unittest
from pathlib import Path


SPECS = Path(__file__).resolve().parent.parent / "docs" / "specs"
STATUS = re.compile(r"(?:draft|accepted|in progress|implemented|released|deferred)(?:; .+)?")
# Unresolved spec filenames belong here, each commented as awaiting the owner.
UNRESOLVED = set()


def tables(path):
    """Yield the header and data rows of each pipe-delimited Markdown table."""
    block = []
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        if line.startswith("|"):
            block.append([cell.strip() for cell in line.strip("|").split("|")])
        else:
            if len(block) >= 2:
                yield block[0], block[2:]
            block = []


class SpecStatusTest(unittest.TestCase):
    def assert_status(self, value):
        self.assertIsNotNone(STATUS.fullmatch(value), repr(value))

    def test_spec_documents(self):
        for path in sorted(SPECS.glob("*.md")):
            if path.name == "index.md" or path.name in UNRESOLVED:
                continue
            with self.subTest(file=path.name):
                lines = path.read_text(encoding="utf-8").splitlines()[:40]
                status = next((line[len("Status:"):].strip()
                               for line in lines if line.startswith("Status:")), None)
                self.assertIsNotNone(status, "Missing Status: in the first 40 lines")
                self.assert_status(status)

    def test_index_rows(self):
        seen = set()
        for header, rows in tables(SPECS / "index.md"):
            self.assertIn("Status", header)
            for row in rows:
                with self.subTest(row=row):
                    self.assertEqual(len(row), len(header))
                    link = re.search(r"\]\(([^)]+\.md)\)", row[0])
                    self.assertIsNotNone(link, "Spec row must link to a document")
                    filename = link.group(1)
                    seen.add(filename)
                    if filename not in UNRESOLVED:
                        self.assert_status(row[header.index("Status")])
        self.assertEqual(seen, {p.name for p in SPECS.glob("*.md") if p.name != "index.md"})

    def test_release_package_tables(self):
        for filename in ("release-0.1.8.md", "release-0.1.10.md"):
            package_tables = [(header, rows) for header, rows in tables(SPECS / filename)
                              if "#" in header and "Package" in header]
            with self.subTest(file=filename):
                self.assertTrue(package_tables, "Missing package table")
                for header, rows in package_tables:
                    self.assertIn("Status", header)
                    self.assertTrue(rows, "Empty package table")
                    for row in rows:
                        with self.subTest(package=row[0]):
                            self.assertEqual(len(row), len(header))
                            self.assert_status(row[header.index("Status")])


if __name__ == "__main__":
    unittest.main()
