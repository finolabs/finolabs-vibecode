"""setup_features.py: the strict `## Setup features` record of declined features."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/setup/scripts/setup_features.py"
spec = importlib.util.spec_from_file_location("setup_features", SCRIPT)
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)


class SetupFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / "home")
        ancestors = {p.stat().st_ino for p in base.parents if p.stat().st_mode & 0o022}
        original = os.fstat

        def fstat(fd):
            info = original(fd)
            if info.st_ino in ancestors and stat.S_ISDIR(info.st_mode):
                fields = list(info)
                fields[0] &= ~0o022
                return os.stat_result(fields)
            return info
        patch = mock.patch.object(os, "fstat", side_effect=fstat)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.dict(os.environ, {"HOME": str(self.home)}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.host = self.home / ".finolabs/vibecode/host.md"

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = sf.main(list(args))
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_decline_needs_a_confirmation_and_records_only_its_section(self):
        self.host.parent.mkdir(parents=True)
        self.host.write_text("## Routing\non\n")
        self.assertEqual(self.run_cli("decline", "quota")[0], 1)
        self.assertEqual(self.host.read_text(), "## Routing\non\n")
        code, out, _ = self.run_cli("decline", "quota", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("- quota: declined", out)
        self.assertEqual(self.run_cli("decline", "quota", "--yes")[0], 0)
        self.assertEqual(self.run_cli("decline", "metrics", "--yes")[0], 0)
        self.assertEqual(self.host.read_text(), "## Routing\non\n\n## Setup features\n\n- quota: declined\n- metrics: declined\n\n")
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: quota, metrics")

    def test_clear_removes_one_feature_then_the_section(self):
        self.run_cli("decline", "roles", "--yes")
        self.run_cli("decline", "project", "--yes")
        self.assertEqual(self.run_cli("clear", "roles", "--yes")[0], 0)
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: project")
        self.run_cli("clear", "project", "--yes")
        self.assertNotIn("Setup features", self.host.read_text())
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: none")

    def test_companions_decline_is_distinct_and_closed(self):
        self.assertEqual(set(sf.FEATURES),
                         {"delegation", "roles", "quota", "autopilot", "metrics", "compaction", "companions", "project",
                          "checks"})
        self.assertEqual(self.run_cli("decline", "companions", "--yes")[0], 0)
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: companions")
        self.assertEqual(self.host.read_text(), "## Setup features\n\n- companions: declined\n\n")
        self.assertFalse((self.home / ".finolabs/vibecode/state/consent.json").exists())
        self.assertEqual(self.run_cli("clear", "companions", "--yes")[0], 0)
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: none")

    def test_unknown_feature_is_refused(self):
        for name in ("everything", "markmap", "vietnamizer"):
            with self.subTest(feature=name):
                self.assertEqual(self.run_cli("decline", name, "--yes")[0], 2)
                self.assertIsNone(sf.parse("## Setup features\n- " + name + ": declined\n"))
        self.assertFalse(self.host.exists())

    def test_legacy_review_tools_is_read_as_companions_and_rewritten_canonically(self):
        self.host.parent.mkdir(parents=True)
        self.host.write_text("## Routing\non\n\n## Setup features\n- review-tools: declined\n- quota: declined\n\n## Other\nkeep\n")
        self.assertEqual(sf.declined(), ["companions", "quota"])
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: companions, quota")
        self.assertEqual(self.run_cli("decline", "metrics", "--yes")[0], 0)
        saved = self.host.read_text()
        self.assertIn("- companions: declined", saved)
        self.assertIn("- quota: declined", saved)
        self.assertIn("- metrics: declined", saved)
        self.assertNotIn("review-tools", saved)
        self.assertTrue(saved.startswith("## Routing\non\n\n"))
        self.assertTrue(saved.endswith("## Other\nkeep\n"))
        self.assertEqual(self.run_cli("clear", "companions", "--yes")[0], 0)
        self.assertNotIn("companions", self.host.read_text())
        self.assertEqual(self.run_cli("decline", "review-tools", "--yes")[0], 2)

    def test_legacy_alias_keeps_duplicate_and_malformed_records_strict(self):
        for names in (("review-tools", "companions"), ("companions", "review-tools"),
                      ("review-tools", "review-tools")):
            section = "## Setup features\n" + "".join("- " + name + ": declined\n" for name in names)
            self.assertIsNone(sf.parse(section))
        for line in ("- review-tools: yes", "- review-tools: declined extra", "review-tools: declined"):
            self.assertIsNone(sf.parse("## Setup features\n" + line + "\n"))

    def test_strict_parser_rejects_every_malformed_shape(self):
        good = "## Setup features\n\n- quota: declined\n"
        self.assertEqual(sf.parse(good), ["quota"])
        for bad in ("## Setup features\n- quota: yes\n", "## Setup features\n- quota: declined\n- quota: declined\n",
                    "## Setup features\n- bogus: declined\n", "## Setup features\nquota declined\n",
                    "## Setup features\n- quota: declined extra\n", good + "\n" + good,
                    "## Setup features\n" + "".join("- quota: declined\n" for _ in range(11)),
                    "```\n## Setup features\n- quota: declined\n```\n"):
            self.assertIsNone(sf.parse(bad), bad)

    def test_unreadable_section_means_nothing_is_declined(self):
        self.host.parent.mkdir(parents=True)
        self.host.write_text("## Setup features\n- quota: yes\n")
        self.assertEqual(sf.declined(), [])
        self.assertEqual(self.run_cli("show")[1].strip(), "declined: none")

    def test_malformed_records_refuse_writes_and_previews_without_losing_foreign_text(self):
        self.host.parent.mkdir(parents=True)
        for body in ("- quota: yes\nkeep this foreign line\n", "- quota: declined\n- quota: declined\n",
                     "- review-tools: declined\n- companions: declined\n"):
            original = "## Routing\non\n\n## Setup features\n" + body + "\n## Other\nkeep\n"
            self.host.write_text(original)
            for action in ("decline", "clear"):
                for flag in ("--yes", "--dry-run"):
                    code, out, err = self.run_cli(action, "metrics", flag)
                    self.assertEqual(code, 1)
                    self.assertIn("malformed Setup features", err)
                    self.assertNotIn("nothing else was changed", out)
                    self.assertEqual(self.host.read_text(), original)

    def test_declined_is_not_a_consent_for_anything(self):
        self.run_cli("decline", "metrics", "--yes")
        self.assertFalse((self.home / ".finolabs/vibecode/state/consent.json").exists())


if __name__ == "__main__":
    unittest.main()
