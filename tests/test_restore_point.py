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
from tests.data_root_fixture import account
from unittest import mock

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
        self.home = account(self, self.base / "home")
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self.git("init", "-q")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "tester" + "@" + "localhost")

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

    def test_temporary_index_is_private_under_synthetic_root_and_removed(self):
        self.assertEqual(restore_point.dr.account_home(), self.home)
        self.home.chmod(0o775)
        root = self.home / ".finolabs/vibecode"
        observed = []
        original = restore_point.run_git

        def inspect(root_path, args, **kwargs):
            index = kwargs.get("extra_env", {}).get("GIT_INDEX_FILE")
            if index:
                folder = Path(index).parent
                self.assertEqual(folder.parent, root / "tmp")
                self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
                self.assertEqual(folder.parent.stat().st_mode & 0o777, 0o700)
                observed.append(folder)
            return original(root_path, args, **kwargs)

        with mock.patch.object(restore_point, "run_git", side_effect=inspect), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(restore_point.main(["create"], cwd=self.repo), 0)
        self.parse_created_name(output.getvalue())
        self.assertTrue(observed)
        self.assertTrue(all(not folder.exists() for folder in observed))
        self.assertEqual(list((root / "tmp").iterdir()), [])
        self.parse_created_name(self.run_cli("create"))
        self.assertEqual(list((root / "tmp").iterdir()), [])

    def test_invalid_root_refuses_without_creating_anything(self):
        root = self.home / ".finolabs/vibecode"
        root.mkdir(parents=True)
        (root / "root.json").write_text("invalid")
        before = {p.relative_to(self.base) for p in self.base.rglob("*")}
        output = self.run_cli("create")
        self.assertEqual(output, "invalid data root\n")
        self.assertEqual(before, {p.relative_to(self.base) for p in self.base.rglob("*")})
        self.assertFalse((root / "tmp").exists())

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
        no_digest_out = self.run_cli("restore", point, "--yes", expected_rc=1)
        self.assertIn("Digest missing or mismatched; nothing written.", no_digest_out)
        bad_digest_out = self.run_cli("restore", point, "--yes", "--digest", "00000000", expected_rc=1)
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
                out = self.run_cli(*args, cwd=outside, expected_rc=int(args[0] == "restore"))
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
                out = self.run_cli("restore", invalid, expected_rc=1)
                self.assertIn("Invalid restore point name; nothing written.", out)

    def test_action_errors_are_plain_lines_and_restore_exits_nonzero(self):
        for action in ("create", "list", "restore"):
            args = [action] + (["20261105T120000Z"] if action == "restore" else [])
            for error in (subprocess.TimeoutExpired("git", 15),
                          subprocess.SubprocessError("failed\nsecond line"),
                          OSError("unavailable\nsecond line"), RuntimeError("git failed")):
                with self.subTest(action=action, error=type(error).__name__):
                    buf = io.StringIO()
                    with mock.patch.object(restore_point, "run_git", side_effect=error), redirect_stdout(buf):
                        self.assertEqual(restore_point.main(args, cwd=self.repo), int(action == "restore"))
                    self.assertEqual(len(buf.getvalue().splitlines()), 1)
                    self.assertNotIn("Traceback", buf.getvalue())
        self.run_cli("unknown-action", expected_rc=2)

    def test_low_gitdir_back_pointer_must_match_worktree(self):
        self.git("commit", "--allow-empty", "-q", "-m", "initial")
        worktree = self.base / "linked"
        self.git("worktree", "add", "-q", "--detach", str(worktree))
        gitdir = restore_point.check_git_dir_and_refs(worktree)
        pointer = gitdir / "gitdir"
        self.assertEqual(Path(pointer.read_text().strip()), worktree / ".git")
        original = pointer.read_text()
        for replacement in (str(self.repo / ".git"), ""):
            pointer.write_text(replacement)
            with self.assertRaisesRegex(ValueError, "back-pointer"):
                restore_point.check_git_dir_and_refs(worktree)
        pointer.unlink()
        with self.assertRaisesRegex(ValueError, "back-pointer"):
            restore_point.check_git_dir_and_refs(worktree)
        other = self.base / "pointer"
        other.write_text(original)
        pointer.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "back-pointer"):
            restore_point.check_git_dir_and_refs(worktree)

    def test_low_missing_restore_point_exits_nonzero(self):
        out = self.run_cli("restore", "20261105T120000Z", expected_rc=1)
        self.assertIn("not found; nothing written", out)

    def test_temporary_index_preserves_racy_timestamp(self):
        self.git("config", "core.trustctime", "false")
        file = self.repo / "file.txt"
        file.write_text("first\n")
        stamp = 1700000000
        os.utime(file, (stamp, stamp))
        self.git("add", ".")
        index = self.repo / ".git" / "index"
        os.utime(index, (stamp, stamp))
        index_before = index.read_bytes()
        file.write_text("other\n")
        os.utime(file, (stamp, stamp))
        point = self.parse_created_name(self.run_cli("create"))
        self.assertEqual(self.git("show", restore_point.REF_PREFIX + point + ":file.txt"), "other\n")
        self.assertEqual(index.read_bytes(), index_before)
        self.assertEqual(index.stat().st_mtime, stamp)

    def test_git_call_limits_and_hardening(self):
        result = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        for args, timeout in ((["add", "-A", "--", "."], 120),
                              (["checkout-index", "-a", "-f"], 120),
                              (["write-tree"], 15), (["for-each-ref"], 15)):
            with self.subTest(args=args), mock.patch.object(restore_point.subprocess, "run", return_value=result) as run:
                restore_point.run_git(self.repo, args)
                self.assertEqual(run.call_args.kwargs["timeout"], timeout)
                argv = run.call_args.args[0]
                for setting in ("core.hooksPath=/dev/null", "core.fsmonitor=false"):
                    self.assertIn(setting, argv)
                    self.assertEqual(argv[argv.index(setting) - 1], "-c")
        failed = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"git failed\n")
        with mock.patch.object(restore_point.subprocess, "run", return_value=failed):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertEqual(restore_point.main(["create"], cwd=self.repo), 0)
            self.assertEqual(buf.getvalue(), "git failed\n")

    def test_failures_after_pre_restore_report_recovery_point(self):
        (self.repo / "file.txt").write_text("saved\n")
        added_file = self.repo / "target-only.txt"
        added_file.write_text("added by checkout\n")
        point = self.parse_created_name(self.run_cli("create"))
        real_run_git = restore_point.run_git
        for command in ("read-tree", "checkout-index"):
            for error in (subprocess.TimeoutExpired("git", 120),
                          subprocess.SubprocessError("git failed"), OSError("disk failed"),
                          RuntimeError("git command failed")):
                with self.subTest(command=command, error=type(error).__name__):
                    added_file.unlink(missing_ok=True)
                    (self.repo / "file.txt").write_text("before\n")
                    digest = self.parse_digest(self.run_cli("restore", point))
                    refs_before = self.git("for-each-ref", "--format=%(refname)", "refs/finolabs/restore").splitlines()
                    def fail_after_snapshot(root, args, **kwargs):
                        if args[0] == command and (command != "read-tree" or args[1] != "--empty"):
                            if command == "checkout-index":
                                (self.repo / "file.txt").write_text("partly restored\n")
                                added_file.write_text("added by checkout\n")
                            raise error
                        return real_run_git(root, args, **kwargs)
                    buf = io.StringIO()
                    with mock.patch.object(restore_point, "run_git", side_effect=fail_after_snapshot), redirect_stdout(buf):
                        rc = restore_point.main(["restore", point, "--yes", "--digest", digest], cwd=self.repo)
                    self.assertEqual(rc, 1)
                    refs_after = self.git("for-each-ref", "--format=%(refname)", "refs/finolabs/restore").splitlines()
                    added = set(refs_after) - set(refs_before)
                    self.assertEqual(len(added), 1)
                    pre_ref = added.pop()
                    line = buf.getvalue().splitlines()[-1]
                    self.assertIn(pre_ref, line)
                    self.assertIn("may be partly restored", line)
                    self.assertIn("restoring that point undoes", line)
                    self.assertIn("Extra files are kept; symlinked paths require manual review.", line)
                    self.assertNotIn("Traceback", buf.getvalue())
                    pre_name = pre_ref.removeprefix(restore_point.REF_PREFIX)
                    recovery_digest = self.parse_digest(self.run_cli("restore", pre_name))
                    self.run_cli("restore", pre_name, "--yes", "--digest", recovery_digest)
                    self.assertEqual((self.repo / "file.txt").read_text(), "before\n")
                    self.assertEqual(added_file.exists(), command == "checkout-index")

    def test_linked_worktree_create_list_restore_preserves_index(self):
        (self.repo / "file.txt").write_text("saved\n")
        (self.repo / "tracked.log").write_text("tracked despite ignore\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        linked = self.base / "worktree"
        self.git("worktree", "add", "-qb", "linked", str(linked))
        (linked / ".gitignore").write_text("*.log\n")
        index = Path(self.git("rev-parse", "--git-path", "index", cwd=linked).strip())
        index_before = index.read_bytes()
        head_before = self.git("rev-parse", "HEAD", cwd=linked)
        point = self.parse_created_name(self.run_cli("create", cwd=linked))
        self.assertIn(point, self.run_cli("list", cwd=linked))
        self.assertEqual(self.git("show", restore_point.REF_PREFIX + point + ":tracked.log"), "tracked despite ignore\n")
        (linked / "file.txt").write_text("changed\n")
        digest = self.parse_digest(self.run_cli("restore", point, cwd=linked))
        output = self.run_cli("restore", point, "--yes", "--digest", digest, cwd=linked)
        self.assertIn("-pre-restore", output)
        self.assertEqual((linked / "file.txt").read_text(), "saved\n")
        self.assertEqual(index.read_bytes(), index_before)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=linked), head_before)
        # Shared refs must receive the same symlink checks as an ordinary repository.
        refs = self.repo / ".git" / "refs" / "finolabs" / "restore"
        (refs / "20200101T000000Z").symlink_to(self.base / "missing")
        self.assertIn("Unsafe path", self.run_cli("create", cwd=linked))

    def test_submodule_git_file_works(self):
        (self.repo / "file.txt").write_text("saved\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        parent = self.base / "parent"
        parent.mkdir()
        self.git("init", "-q", cwd=parent)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(self.repo), "child", cwd=parent)
        child = parent / "child"
        self.assertTrue((child / ".git").is_file())
        point = self.parse_created_name(self.run_cli("create", cwd=child))
        self.assertIn(point, self.run_cli("list", cwd=child))
        (child / "file.txt").write_text("changed\n")
        digest = self.parse_digest(self.run_cli("restore", point, cwd=child))
        self.run_cli("restore", point, "--yes", "--digest", digest, cwd=child)
        self.assertEqual((child / "file.txt").read_text(), "saved\n")

    def test_symlinked_parent_allowed_but_descendant_refused(self):
        parent_link = self.base / "parent-link"
        parent_link.symlink_to(self.base, target_is_directory=True)
        alias = parent_link / "repo"
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(restore_point.main(["create"], cwd=alias), 0)
        self.parse_created_name(buf.getvalue())
        self.parse_created_name(self.run_cli("create", cwd=alias, extra_env={"PWD": str(alias)}))
        (self.repo / "real").mkdir()
        (self.repo / "alias").symlink_to(self.repo / "real", target_is_directory=True)
        self.assertIn("Unsafe path", self.run_cli("create", cwd=self.repo / "alias", extra_env={"PWD": str(self.repo / "alias")}))

    def test_invalid_git_files_are_refused(self):
        fake = self.base / "fake"
        fake.mkdir()
        for content in ("invalid\n", "gitdir: missing\n", "gitdir: \n",
                        "gitdir: " + str(self.repo / ".git") + "\nextra\n",
                        "gitdir: " + str(self.repo / ".git" / "HEAD") + "\n"):
            with self.subTest(content=content):
                (fake / ".git").write_text(content)
                self.assertIn("Unsafe path", self.run_cli("create", cwd=fake))
        (fake / ".git").write_text("gitdir: " + str(self.repo / ".git") + "\n")
        with mock.patch.object(restore_point.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaisesRegex(ValueError, "owned"):
                restore_point.check_git_dir_and_refs(fake)

    def test_digest_binds_content_even_when_preview_is_identical(self):
        file = self.repo / "file.txt"
        file.write_text("saved\n")
        point = self.parse_created_name(self.run_cli("create"))
        file.write_text("first\n")
        preview = self.run_cli("restore", point)
        digest = self.parse_digest(preview)
        file.write_text("other\n")
        next_preview = self.run_cli("restore", point)
        self.assertEqual(preview.split("Digest:")[0], next_preview.split("Digest:")[0])
        self.assertNotEqual(digest, self.parse_digest(next_preview))
        refs_before = self.git("for-each-ref")
        output = self.run_cli("restore", point, "--yes", "--digest", digest, expected_rc=1)
        self.assertIn("Digest missing or mismatched; nothing written.", output)
        self.assertEqual(file.read_text(), "other\n")
        self.assertEqual(self.git("for-each-ref"), refs_before)

    def test_digest_binds_restore_commit(self):
        (self.repo / "file.txt").write_text("saved\n")
        point = self.parse_created_name(self.run_cli("create"))
        ref = restore_point.REF_PREFIX + point
        digest = self.parse_digest(self.run_cli("restore", point))
        tree = self.git("rev-parse", ref + "^{tree}").strip()
        replacement = self.git("commit-tree", tree, "-m", "replacement commit").strip()
        self.git("update-ref", ref, replacement)
        output = self.run_cli("restore", point, "--yes", "--digest", digest, expected_rc=1)
        self.assertIn("Digest missing or mismatched; nothing written.", output)
        self.assertEqual(len(self.run_cli("list").splitlines()), 1)

    def test_repository_fsmonitor_and_reference_hook_do_not_run(self):
        (self.repo / "file.txt").write_text("saved\n")
        monitor = self.repo / ".git" / "monitor"
        hook = self.repo / ".git" / "hooks" / "reference-transaction"
        for script, marker in ((monitor, "monitor-ran"), (hook, "hook-ran")):
            script.write_text("#!/bin/sh\ntouch .git/" + marker + "\n")
            script.chmod(0o700)
        self.git("config", "core.fsmonitor", str(monitor))
        point = self.parse_created_name(self.run_cli("create"))
        self.assertIn(point, self.run_cli("list"))
        (self.repo / "file.txt").write_text("changed\n")
        digest = self.parse_digest(self.run_cli("restore", point))
        self.run_cli("restore", point, "--yes", "--digest", digest)
        for marker in ("monitor-ran", "hook-ran"):
            self.assertFalse((self.repo / ".git" / marker).exists(), marker)

    def test_long_filenames_are_bounded_in_preview(self):
        names = [str(i) + "x" * 199 for i in range(3)]
        for name in names:
            (self.repo / name).write_text("saved\n")
        point = self.parse_created_name(self.run_cli("create"))
        for name in names:
            (self.repo / name).write_text("changed\n")
        preview = self.run_cli("restore", point)
        for name in names:
            self.assertNotIn(name, preview)
            self.assertIn(name[:77] + "...", preview)
        status_names = [line.split("\t", 1)[1] for line in preview.splitlines() if "\t" in line]
        self.assertEqual([len(name) for name in status_names], [80] * 3)
        self.assertLessEqual(max(map(len, preview.splitlines())), 300)

    def test_preview_limits_more_than_ten_files(self):
        for i in range(15):
            (self.repo / f"file-{i:02}.txt").write_text("saved\n")
        point = self.parse_created_name(self.run_cli("create"))
        for i in range(15):
            (self.repo / f"file-{i:02}.txt").write_text("changed\n")
        preview = self.run_cli("restore", point)
        self.assertEqual(sum("\t" in line for line in preview.splitlines()), 10)
        self.assertIn("... (5 more files)", preview)
        self.assertIn("... (7 more stat lines)", preview)
        self.assertIn("(+3 more)", preview)

    def test_restore_refuses_working_tree_symlink_without_touching_outside(self):
        file = self.repo / "file.txt"
        file.write_text("saved\n")
        point = self.parse_created_name(self.run_cli("create"))
        outside = self.base / "outside.txt"
        outside.write_text("outside unchanged\n")
        file.unlink()
        file.symlink_to(outside)
        digest = self.parse_digest(self.run_cli("restore", point))
        refs_before = self.git("for-each-ref")
        output = self.run_cli("restore", point, "--yes", "--digest", digest, expected_rc=1)
        self.assertIn("Unsafe path: symlink in working tree refused.", output)
        self.assertTrue(file.is_symlink())
        self.assertEqual(outside.read_text(), "outside unchanged\n")
        self.assertEqual(self.git("for-each-ref"), refs_before)

    def test_skill_documents_config_and_local_secret_capture(self):
        text = (ROOT / "skills/fnl-restore-point/SKILL.md").read_text()
        self.assertIn("makes no network call itself", text)
        self.assertIn("configuration can still make git run its filters", text)
        self.assertIn(".env", text)
        self.assertIn("mirror clone or bundle", text)
        self.assertIn("never push `refs/finolabs/*`", text)
        skill_count = sum(1 for path in (ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(skill_count, 20)
        self.assertIn(f"The {skill_count} skill folders", (ROOT / "skills/fnl-ask/references/map.md").read_text())

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
