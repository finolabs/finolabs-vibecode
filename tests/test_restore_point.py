"""Tests for skills/fnl-restore-point/scripts/restore_point.py on synthetic git repositories."""

import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/fnl-restore-point/scripts/restore_point.py"
spec = importlib.util.spec_from_file_location("restore_point", SCRIPT)
restore_point = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_point)


class RestorePointTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.env = {
            "HOME": str(self.base),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self.git("init", "-q")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "tester@localhost")

    def git(self, *args, cwd=None):
        result = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=str(cwd or self.repo),
            env=self.env,
            shell=False,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout

    def run_cli(self, *args, cwd=None, extra_env=None, expected_rc=0):
        target_cwd = cwd or self.repo
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *args],
            cwd=str(target_cwd),
            env=env,
            shell=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, expected_rc, result.stderr)
        self.assertLessEqual(len(result.stdout.splitlines()), 40)
        return result.stdout

    def parse_created_name(self, output):
        match = re.search(r"refs/finolabs/restore/([0-9]{8}T[0-9]{6}Z(?:-[a-z0-9-]{1,20})?)", output)
        self.assertIsNotNone(match, output)
        return match.group(1)

    def parse_digest(self, output):
        match = re.search(r"^Digest: ([0-9a-f]{64})$", output, re.M)
        self.assertIsNotNone(match, output)
        return match.group(1)

    def test_create_leaves_index_branch_and_working_tree_untouched(self):
        (self.repo / "tracked.txt").write_text("v1\n", encoding="utf-8")
        (self.repo / "staged.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "tracked.txt", "staged.txt")
        self.git("commit", "-q", "-m", "initial")

        # Stage a change in the real index, modify another tracked file, and add an untracked file.
        (self.repo / "staged.txt").write_text("staged-v2\n", encoding="utf-8")
        self.git("add", "staged.txt")
        (self.repo / "staged.txt").write_text("worktree-v3\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("modified-v2\n", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("untracked-v1\n", encoding="utf-8")

        status_before = self.git("status", "--porcelain")
        head_before = self.git("rev-parse", "HEAD")
        branch_before = self.git("symbolic-ref", "HEAD")
        index_path = self.repo / ".git" / "index"
        index_bytes_before = index_path.read_bytes()

        out = self.run_cli("create")
        name = self.parse_created_name(out)
        self.assertIn("(3 files)", out)

        self.assertEqual(self.git("status", "--porcelain"), status_before)
        self.assertEqual(self.git("rev-parse", "HEAD"), head_before)
        self.assertEqual(self.git("symbolic-ref", "HEAD"), branch_before)
        self.assertEqual(index_path.read_bytes(), index_bytes_before)
        self.assertEqual(self.git("tag", "-l").strip(), "")

        ref = f"refs/finolabs/restore/{name}"
        self.assertEqual(self.git("show", f"{ref}:tracked.txt"), "modified-v2\n")
        self.assertEqual(self.git("show", f"{ref}:staged.txt"), "worktree-v3\n")
        self.assertEqual(self.git("show", f"{ref}:untracked.txt"), "untracked-v1\n")
        self.assertEqual(self.git("rev-parse", f"{ref}^1"), head_before)

    def test_create_captures_untracked_and_excludes_ignored_files(self):
        (self.repo / ".gitignore").write_text("*.log\nbuild/\n", encoding="utf-8")
        (self.repo / "keep.txt").write_text("tracked\n", encoding="utf-8")
        self.git("add", ".gitignore", "keep.txt")
        self.git("commit", "-q", "-m", "initial")

        (self.repo / "fresh.txt").write_text("untracked\n", encoding="utf-8")
        (self.repo / "secret.log").write_text("ignored log\n", encoding="utf-8")
        (self.repo / "build").mkdir()
        (self.repo / "build" / "artifact.bin").write_text("ignored dir\n", encoding="utf-8")

        out = self.run_cli("create")
        name = self.parse_created_name(out)
        ref = f"refs/finolabs/restore/{name}"
        files = set(self.git("ls-tree", "-r", "--name-only", ref).splitlines())
        self.assertEqual(files, {".gitignore", "keep.txt", "fresh.txt"})
        self.assertNotIn("secret.log", files)
        self.assertNotIn("build/artifact.bin", files)

    def test_list_orders_newest_first_with_changed_counts(self):
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        self.git("add", "a.txt")
        self.git("commit", "-q", "-m", "initial")

        (self.repo / "a.txt").write_text("two\n", encoding="utf-8")
        first_name = self.parse_created_name(self.run_cli("create"))

        (self.repo / "b.txt").write_text("extra\n", encoding="utf-8")
        (self.repo / "c.txt").write_text("more\n", encoding="utf-8")
        second_name = self.parse_created_name(self.run_cli("create"))

        self.assertNotEqual(first_name, second_name)
        listing = self.run_cli("list").strip().splitlines()
        self.assertEqual(len(listing), 2)
        self.assertTrue(listing[0].startswith(second_name), listing)
        self.assertIn("3 files changed", listing[0])
        self.assertTrue(listing[1].startswith(first_name), listing)
        self.assertIn("1 file changed", listing[1])

    def test_restore_preview_writes_nothing_and_sanitizes_filenames(self):
        (self.repo / "file.txt").write_text("saved\n", encoding="utf-8")
        self.git("add", "file.txt")
        self.git("commit", "-q", "-m", "initial")

        point = self.parse_created_name(self.run_cli("create"))

        (self.repo / "file.txt").write_text("dirty\n", encoding="utf-8")
        (self.repo / "extra.txt").write_text("keep-me\n", encoding="utf-8")
        index_before = (self.repo / ".git" / "index").read_bytes()
        refs_before = self.git("for-each-ref", "refs/finolabs/restore")

        preview = self.run_cli("restore", point)
        self.assertIn("Would overwrite: file.txt", preview)
        self.assertIn("Exist now but not in restore point (kept, NOT deleted): extra.txt", preview)
        self.assertIn("Digest: ", preview)
        self.assertIn("Preview only", preview)

        self.assertEqual((self.repo / "file.txt").read_text(encoding="utf-8"), "dirty\n")
        self.assertEqual((self.repo / "extra.txt").read_text(encoding="utf-8"), "keep-me\n")
        self.assertEqual((self.repo / ".git" / "index").read_bytes(), index_before)
        self.assertEqual(self.git("for-each-ref", "refs/finolabs/restore"), refs_before)
        self.assertEqual(restore_point.clean_text("bad\x07\x1bname.txt"), "badname.txt")

    def test_restore_digest_mismatch_writes_nothing_and_clean_or_dirty_trees_restore_with_pre_restore_point(self):
        (self.repo / "app.txt").write_text("v1\n", encoding="utf-8")
        (self.repo / "notes.txt").write_text("n1\n", encoding="utf-8")
        self.git("add", "app.txt")
        self.git("commit", "-q", "-m", "initial")

        point = self.parse_created_name(self.run_cli("create"))

        # Dirty working tree: modify tracked file, delete untracked file from snapshot, add new untracked file.
        (self.repo / "app.txt").write_text("dirty-v2\n", encoding="utf-8")
        (self.repo / "notes.txt").unlink()
        (self.repo / "later.txt").write_text("stay-here\n", encoding="utf-8")

        preview = self.run_cli("restore", point)
        digest = self.parse_digest(preview)

        # Missing digest or mismatched digest writes nothing.
        no_digest_out = self.run_cli("restore", point, "--yes")
        self.assertIn("Digest missing or mismatched; nothing written.", no_digest_out)
        bad_digest_out = self.run_cli("restore", point, "--yes", "--digest", "00000000")
        self.assertIn("Digest missing or mismatched; nothing written.", bad_digest_out)
        self.assertEqual((self.repo / "app.txt").read_text(encoding="utf-8"), "dirty-v2\n")
        self.assertFalse((self.repo / "notes.txt").exists())
        self.assertEqual(len(self.run_cli("list").splitlines()), 1)

        # Restore on dirty tree with matching digest prefix creates pre-restore point and restores files.
        index_before = (self.repo / ".git" / "index").read_bytes()
        head_before = self.git("rev-parse", "HEAD")
        restore_out = self.run_cli("restore", point, "--yes", "--digest", digest[:10])
        self.assertIn("-pre-restore", restore_out)
        self.assertEqual((self.repo / "app.txt").read_text(encoding="utf-8"), "v1\n")
        self.assertEqual((self.repo / "notes.txt").read_text(encoding="utf-8"), "n1\n")
        # Files that exist now but not in the point are kept (not deleted).
        self.assertEqual((self.repo / "later.txt").read_text(encoding="utf-8"), "stay-here\n")
        self.assertEqual((self.repo / ".git" / "index").read_bytes(), index_before)
        self.assertEqual(self.git("rev-parse", "HEAD"), head_before)

        # Clean working tree at a newer commit also restores and creates a pre-restore point first.
        (self.repo / "later.txt").unlink()
        (self.repo / "app.txt").write_text("committed-v3\n", encoding="utf-8")
        self.git("add", "app.txt", "notes.txt")
        self.git("commit", "-q", "-m", "move forward")
        self.assertEqual(self.git("status", "--porcelain"), "")

        clean_preview = self.run_cli("restore", point)
        clean_digest = self.parse_digest(clean_preview)
        clean_restore = self.run_cli("restore", point, "--yes", "--digest", clean_digest[:12])
        self.assertIn("-pre-restore", clean_restore)
        self.assertEqual((self.repo / "app.txt").read_text(encoding="utf-8"), "v1\n")
        points_after = [line.split()[0] for line in self.run_cli("list").splitlines()]
        pre_points = [p for p in points_after if p.endswith("-pre-restore")]
        self.assertEqual(len(pre_points), 2)

    def test_symlinked_dot_git_root_component_and_ref_path_are_refused(self):
        (self.repo / "file.txt").write_text("safe\n", encoding="utf-8")
        self.git("add", "file.txt")
        self.git("commit", "-q", "-m", "initial")

        # 1. Symlinked .git entry.
        fake_repo = self.base / "fake-repo"
        fake_repo.mkdir()
        (fake_repo / ".git").symlink_to(self.repo / ".git", target_is_directory=True)
        out_dot_git = self.run_cli("create", cwd=fake_repo)
        self.assertIn("Unsafe path", out_dot_git)
        self.assertEqual(self.run_cli("list"), "No restore points.\n")

        # 2. Symlinked repository root component.
        link_root = self.base / "linked-repo"
        link_root.symlink_to(self.repo, target_is_directory=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = restore_point.main(["create"], cwd=link_root)
        self.assertEqual(rc, 0)
        self.assertIn("Unsafe path", buf.getvalue())
        out_pwd = self.run_cli("create", cwd=link_root, extra_env={"PWD": str(link_root)})
        self.assertIn("Unsafe path", out_pwd)
        self.assertEqual(self.run_cli("list"), "No restore points.\n")

        # 3. Ref path resolving through a symlink.
        refs_dir = self.repo / ".git" / "refs" / "finolabs"
        refs_dir.mkdir(parents=True)
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (refs_dir / "restore").symlink_to(elsewhere, target_is_directory=True)
        out_ref = self.run_cli("create")
        self.assertIn("Unsafe path", out_ref)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_outside_git_prints_init_message_and_creates_nothing(self):
        outside = self.base / "outside"
        outside.mkdir()
        expected = (
            "Not a git repository: this cannot help here. "
            "Run `git init` yourself to start one; nothing was created.\n"
        )
        for args in (("create",), ("list",), ("restore", "20261105T120000Z")):
            with self.subTest(args=args):
                out = self.run_cli(*args, cwd=outside)
                self.assertEqual(out, expected)
                self.assertEqual(list(outside.iterdir()), [])

    def test_name_validation_rejects_traversal_spaces_and_outside_refs(self):
        for valid in ("20261105T120000Z", "20261105T120000Z-pre-restore", "20261105T120000Z-step-1"):
            self.assertTrue(restore_point.validate_name(valid), valid)
        for invalid in (
            "../x",
            "20261105T120000Z/../x",
            "20261105T120000Z bad",
            " 20261105T120000Z",
            "refs/heads/main",
            "refs/finolabs/restore/20261105T120000Z",
            "20261105T120000Z-UPPER",
            "20261105T120000Z-" + "a" * 21,
            "",
        ):
            with self.subTest(invalid=invalid):
                self.assertFalse(restore_point.validate_name(invalid))
                out = self.run_cli("restore", invalid)
                self.assertIn("Invalid restore point name; nothing written.", out)

    def test_script_source_uses_no_network_push_or_fetch(self):
        source = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("push", source)
        self.assertNotIn("fetch", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("socket", source)

    def test_skill_frontmatter_and_try_it_now_demo_step(self):
        skill_text = (ROOT / "skills/fnl-restore-point/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: fnl-restore-point", skill_text)
        self.assertIn("disable-model-invocation: true", skill_text)
        self.assertIn('argument-hint: "[list|create|restore <name>]"', skill_text)
        self.assertIn("Run only when the user asks.", skill_text)

        start_text = (ROOT / "skills/fnl-ask/references/start.md").read_text(encoding="utf-8")
        demo_lines = [line for line in start_text.splitlines() if line.startswith("4. **Try it now**")]
        self.assertEqual(len(demo_lines), 1)
        demo = demo_lines[0].lower()
        self.assertIn("new empty folder", demo)
        self.assertIn("never inside an existing repository", demo)
        self.assertIn("one tiny thing", demo)
        for internal in ("router", "gate", "depth", "ledger", "handoff"):
            self.assertNotIn(internal, demo)


if __name__ == "__main__":
    unittest.main()
