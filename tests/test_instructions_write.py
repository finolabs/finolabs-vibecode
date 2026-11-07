"""instructions_write.py acceptance; synthetic account, repository and files only."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/instructions_write.py"
COPY = ROOT / "skills/fnl-setup/scripts/instructions_write.py"
spec = importlib.util.spec_from_file_location("instructions_write", SCRIPT)
iw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iw)


class InstructionsWriteTest(unittest.TestCase):
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
        env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, env=dict(os.environ))
        self.outside = base / "outside"
        self.outside.mkdir()
        self.content = base / "draft.md"
        self.content.write_text("# Contract\n\nUse small steps.\n")
        cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)
        self.plans = self.home / ".finolabs/vibecode/state/instructions"

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", [str(SCRIPT), *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = iw.main()
        return code, out.getvalue(), err.getvalue()

    def preview(self, target, content=None, *extra):
        code, out, err = self.run_cli("preview", "--target", str(target), "--content-file", str(content or self.content), *extra)
        self.assertEqual(code, 0, err)
        return out.split("Digest: ")[1].splitlines()[0], out

    def apply(self, digest, *extra):
        return self.run_cli("apply", "--digest", digest, *extra)

    def refused(self, *args):
        code, _, err = self.run_cli(*args)
        self.assertEqual(code, 1)
        self.assertIn("refused", err)
        return err

    def test_preview_shows_diff_and_full_digest_and_writes_nothing(self):
        target = self.repo / "AGENTS.md"
        digest, out = self.preview(target)
        self.assertEqual(len(digest), 64)
        self.assertIn("+Use small steps.", out)
        self.assertFalse(target.exists())
        plan = self.plans / (digest + ".json")
        self.assertEqual(stat.S_IMODE(plan.stat().st_mode), 0o600)

    def test_apply_writes_new_file_owner_only_without_backup(self):
        target = self.repo / "AGENTS.md"
        digest, _ = self.preview(target)
        code, out, err = self.apply(digest, "--yes")
        self.assertEqual(code, 0, err)
        self.assertEqual(target.read_text(), self.content.read_text())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual([p.name for p in self.repo.iterdir() if ".bak-" in p.name], [])
        self.assertFalse((self.plans / (digest + ".json")).exists())

    def test_apply_requires_yes_and_full_digest(self):
        digest, _ = self.preview(self.repo / "AGENTS.md")
        self.refused("apply", "--digest", digest)
        self.refused("apply", "--digest", digest[:12], "--yes")
        self.refused("apply", "--digest", "0" * 64, "--yes")
        self.assertFalse((self.repo / "AGENTS.md").exists())

    def test_backups_never_overwrite(self):
        target = self.repo / "AGENTS.md"
        for number in range(3):
            target.write_text("old %d\n" % number)
            self.content.write_text("new %d\n" % number)
            digest, _ = self.preview(target)
            self.assertEqual(self.apply(digest, "--yes")[0], 0)
        names = sorted(p.name for p in self.repo.iterdir() if ".bak-" in p.name)
        day = time.strftime("%Y%m%d")
        self.assertEqual(names, ["AGENTS.md.bak-" + day, "AGENTS.md.bak-%s-2" % day, "AGENTS.md.bak-%s-3" % day])
        self.assertEqual([(self.repo / n).read_text() for n in names], ["old 0\n", "old 1\n", "old 2\n"])
        for name in names:
            self.assertEqual(stat.S_IMODE((self.repo / name).stat().st_mode), 0o600)

    def test_existing_mode_is_kept(self):
        target = self.repo / "AGENTS.md"
        target.write_text("old\n")
        target.chmod(0o644)
        digest, _ = self.preview(target)
        self.assertEqual(self.apply(digest, "--yes")[0], 0)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_refuses_symlink_target(self):
        real = self.outside / "real.md"
        real.write_text("keep\n")
        link = self.repo / "AGENTS.md"
        link.symlink_to(real)
        self.refused("preview", "--target", str(link), "--content-file", str(self.content))
        self.assertEqual(real.read_text(), "keep\n")

    def test_refuses_symlink_created_after_preview(self):
        target = self.repo / "AGENTS.md"
        digest, _ = self.preview(target)
        real = self.outside / "real.md"
        real.write_text("keep\n")
        target.symlink_to(real)
        self.refused("apply", "--digest", digest, "--yes")
        self.assertEqual(real.read_text(), "keep\n")

    def test_refuses_symlinked_user_folder(self):
        (self.home / ".claude").symlink_to(self.outside)
        self.refused("preview", "--target", str(self.home / ".claude/CLAUDE.md"), "--content-file", str(self.content))
        digest, _ = self.preview(self.home / ".codex/AGENTS.md")
        (self.home / ".codex").symlink_to(self.outside)
        self.refused("apply", "--digest", digest, "--yes")
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_refuses_targets_outside_the_closed_list(self):
        sub = self.repo / "docs"
        sub.mkdir()
        for target in (self.repo / "README.md", sub / "AGENTS.md", self.outside / "AGENTS.md",
                       self.home / ".claude" / "settings.json", self.home / ".bashrc",
                       self.repo / ".git" / "AGENTS.md", self.home / "CLAUDE.md"):
            err = self.refused("preview", "--target", str(target), "--content-file", str(self.content))
            self.assertIn("allowed list", err, str(target))

    def test_refuses_project_file_outside_a_repository(self):
        os.chdir(self.outside)
        err = self.refused("preview", "--target", str(self.outside / "AGENTS.md"), "--content-file", str(self.content))
        self.assertIn("allowed list", err)

    def test_user_level_targets_are_allowed(self):
        for rel in (".claude/CLAUDE.md", ".codex/AGENTS.md", ".codex/AGENTS.override.md", ".gemini/GEMINI.md",
                    ".gemini/AGENTS.md", ".agents/instructions.md"):
            digest, _ = self.preview(self.home / rel)
            self.assertEqual(self.apply(digest, "--yes")[0], 0, rel)
            self.assertTrue((self.home / rel).is_file())

    def test_refuses_digest_mismatch(self):
        target = self.repo / "AGENTS.md"
        digest, _ = self.preview(target)
        plan = self.plans / (digest + ".json")
        data = json.loads(plan.read_text())
        data["content"] = "tampered\n"
        plan.write_text(json.dumps(data))
        os.chmod(plan, 0o600)
        err = self.refused("apply", "--digest", digest, "--yes")
        self.assertIn("differs", err)
        self.assertFalse(target.exists())

    def test_refuses_when_file_changed_after_preview(self):
        target = self.repo / "AGENTS.md"
        target.write_text("old\n")
        digest, _ = self.preview(target)
        target.write_text("edited meanwhile\n")
        err = self.refused("apply", "--digest", digest, "--yes")
        self.assertIn("changed after", err)
        self.assertEqual(target.read_text(), "edited meanwhile\n")

    def test_plan_expires_after_sixty_minutes(self):
        target = self.repo / "AGENTS.md"
        digest, _ = self.preview(target)
        with mock.patch.object(iw.time, "time", return_value=time.time() + 3601):
            err = self.refused("apply", "--digest", digest, "--yes")
        self.assertIn("60 minutes", err)
        self.assertFalse(target.exists())

    def test_refuses_plan_with_open_mode(self):
        digest, _ = self.preview(self.repo / "AGENTS.md")
        os.chmod(self.plans / (digest + ".json"), 0o644)
        self.refused("apply", "--digest", digest, "--yes")

    def test_content_file_must_be_regular_text(self):
        link = self.outside / "link.md"
        link.symlink_to(self.content)
        self.refused("preview", "--target", str(self.repo / "AGENTS.md"), "--content-file", str(link))
        binary = self.outside / "bin.md"
        binary.write_bytes(b"a\x00b")
        self.refused("preview", "--target", str(self.repo / "AGENTS.md"), "--content-file", str(binary))

    def test_no_difference_stores_no_plan(self):
        target = self.repo / "AGENTS.md"
        target.write_text(self.content.read_text())
        code, out, _ = self.run_cli("preview", "--target", str(target), "--content-file", str(self.content))
        self.assertEqual((code, out.strip()), (0, "No difference."))

    def test_block_replaces_only_that_section(self):
        target = self.repo / "AGENTS.md"
        target.write_text("# Repo\n\nBuild with make.\n\n## Agent skills\n\nold text\n\n## Notes\n\nkeep me\n")
        block = self.outside / "block.md"
        block.write_text("## Agent skills\n\nnew text\n")
        digest, _ = self.preview(target, block, "--block", "Agent skills")
        self.assertEqual(self.apply(digest, "--yes")[0], 0)
        self.assertEqual(target.read_text(),
                         "# Repo\n\nBuild with make.\n\n## Agent skills\n\nnew text\n\n## Notes\n\nkeep me\n")

    def test_block_appends_when_missing_and_rejects_bad_blocks(self):
        target = self.repo / "CLAUDE.md"
        target.write_text("# Repo\n")
        block = self.outside / "block.md"
        block.write_text("## Work tracking\n\nThis repository uses work records.\n")
        digest, _ = self.preview(target, block, "--block", "Work tracking")
        self.assertEqual(self.apply(digest, "--yes")[0], 0)
        self.assertEqual(target.read_text(), "# Repo\n\n## Work tracking\n\nThis repository uses work records.\n")
        for heading, text in (("Other", "## Other\n"), ("Work tracking", "## Agent skills\n"),
                              ("Work tracking", "## Work tracking\n## Extra\n")):
            block.write_text(text)
            self.refused("preview", "--target", str(target), "--content-file", str(block), "--block", heading)

    def test_block_refuses_duplicate_sections(self):
        target = self.repo / "AGENTS.md"
        target.write_text("## Agent skills\na\n## Agent skills\nb\n")
        block = self.outside / "block.md"
        block.write_text("## Agent skills\nc\n")
        self.refused("preview", "--target", str(target), "--content-file", str(block), "--block", "Agent skills")

    def test_skill_copy_matches(self):
        self.assertEqual(SCRIPT.read_bytes(), COPY.read_bytes())


if __name__ == "__main__":
    unittest.main()
