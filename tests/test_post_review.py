"""Posting boundary tests use a fake gh and a synthetic account, never a forge."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import post_review as post
import data_root as dr
from tests.data_root_fixture import account

HEAD = "0123456789abcdef0123456789abcdef01234567"
MARKER = f"<!-- fnl-review kind=code head={HEAD} verdict=APPROVE -->"
BODY = MARKER + "\nNo findings.\n"


AT = chr(64)


class PostingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.home = account(self, self.base / "account")
        self.checkout = self.base / "checkout"
        (self.checkout / ".git").mkdir(parents=True)
        self.remote("https://github.com/sample-owner/sample-repository.git")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.fake = self.bin / "gh"
        self.fake.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
root = Path(os.environ["FAKE_GH_STATE"])
args = sys.argv[1:]
with (root / "argv.jsonl").open("a") as stream:
    stream.write(json.dumps(args) + "\\n")
error = (root / "error").read_text() if (root / "error").exists() else ""
if error:
    print(error, file=sys.stderr)
    sys.exit(1)
head = (root / "head").read_text()
comments_path = root / "comments.json"
comments = json.loads(comments_path.read_text()) if comments_path.exists() else []
if args[:2] == ["pr", "view"]:
    print(json.dumps(dict(headRefOid=head, comments=comments)))
elif args[:2] == ["pr", "comment"]:
    assert args[-2:] == ["--body-file", "-"]
    comments.append(dict(body=sys.stdin.read(), author=dict(login="sample-reviewer"), includesCreatedEdit=False))
    comments_path.write_text(json.dumps(comments))
    if (root / "move-head").exists():
        (root / "head").write_text("f" * 40)
    print("https://github.com/sample-owner/sample-repository/pull/31#issuecomment-1")
else:
    raise AssertionError("forbidden gh argv")
''')
        self.fake.chmod(0o700)
        (self.base / "head").write_text(HEAD)
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin), "FAKE_GH_STATE": str(self.base),
                                           "GH_REPO": "malicious.example/other/repo", "GH_HOST": "malicious.example",
                                           "GH_TOKEN": "synthetic-gh-token", "GITHUB_TOKEN": "synthetic-github-token"})
        patch.start()
        self.addCleanup(patch.stop)
        environment = post.gh_environment
        def fake_environment():
            return {**environment(), "FAKE_GH_STATE": str(self.base)}
        patch = mock.patch.object(post, "gh_environment", side_effect=fake_environment)
        patch.start()
        self.addCleanup(patch.stop)
        def fake_executable():
            if not self.fake.exists():
                raise post.CannotPost("no-cli")
            return str(self.fake)
        self.real_trusted_gh = post.trusted_gh
        patch = mock.patch.object(post, "trusted_gh", side_effect=fake_executable)
        patch.start()
        self.addCleanup(patch.stop)
        self.body = post.create_run_folder()
        self.body.write_text(BODY)

    def remote(self, remote):
        (self.checkout / ".git/config").write_text('[remote "origin"]\n\turl = ' + remote + '\n')

    def calls(self):
        path = self.base / "argv.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def main(self, argv):
        output, error = io.StringIO(), io.StringIO()
        with mock.patch.object(post.Path, "cwd", return_value=self.checkout), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            try:
                code = post.main(argv)
            except SystemExit as raised:
                code = raised.code
        return code, output.getvalue(), error.getvalue()

    def test_prepare_creates_private_run_and_body_under_data_root(self):
        self.assertEqual(self.body.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.body.parent.stat().st_mode & 0o777, 0o700)
        self.assertTrue(self.body.is_relative_to(dr.consent_root()))
        code, output, _ = self.main(["31"])
        self.assertEqual(code, 0)
        self.assertEqual(Path(output.strip()).read_bytes(), b"")
        self.assertEqual(self.calls(), [])

    def test_fixed_argv_post_and_view_with_verified_stdin(self):
        post.post(31, self.body, self.checkout)
        self.assertEqual(self.calls(), [
            ["pr", "view", "31", "--repo", "github.com/sample-owner/sample-repository", "--json", "headRefOid,comments"],
            ["pr", "comment", "31", "--repo", "github.com/sample-owner/sample-repository", "--body-file", "-"],
            ["pr", "view", "31", "--repo", "github.com/sample-owner/sample-repository", "--json", "headRefOid,comments"]])
        comments = json.loads((self.base / "comments.json").read_text())
        self.assertEqual(comments[0]["body"], BODY)
        self.assertTrue(post.posting_verified(comments, "sample-reviewer", MARKER))

    def test_only_supported_option_and_positive_pr_number(self):
        for args in (["31", "--repo", "other/repo"], ["31", "--web"], ["31", "--edit-last"],
                     ["31", "--help"], ["31", "extra"], ["0"], ["-1"], ["https://github.com/sample-owner/sample-repository/pull/31"],
                     ["31", "--body-f", str(self.body)]):
            with self.subTest(args=args):
                self.assertEqual(self.main(args)[0], 2)
        self.assertEqual(self.calls(), [])

    def test_outside_symlink_fifo_directory_and_non_private_body_refused(self):
        outside = self.base / "body.md"
        outside.write_text(BODY)
        with self.assertRaises(ValueError):
            post.read_body(outside)
        self.body.unlink()
        self.body.symlink_to(outside)
        with self.assertRaises((ValueError, OSError)):
            post.read_body(self.body)
        self.body.unlink()
        os.mkfifo(self.body, 0o600)
        with self.assertRaises(ValueError):
            post.read_body(self.body)
        self.body.unlink()
        self.body.mkdir(mode=0o700)
        with self.assertRaises(ValueError):
            post.read_body(self.body)
        self.body.rmdir()
        self.body.write_text(BODY)
        self.body.chmod(0o644)
        with self.assertRaises(ValueError):
            post.read_body(self.body)
        self.assertEqual(self.calls(), [])

    def test_symlinked_or_non_private_run_folder_refused(self):
        folder = self.body.parent
        folder.chmod(0o755)
        with self.assertRaises(ValueError):
            post.read_body(self.body)
        folder.chmod(0o700)
        moved = folder.with_name("moved")
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            post.read_body(self.body)
        self.assertEqual(self.calls(), [])

    def test_size_utf8_and_exact_marker_checks(self):
        malformed = ["", "No findings.", " " + BODY, "\ufeff" + BODY, BODY.replace("kind=code", "kind=other"),
                     BODY.replace("APPROVE", "PASS"), BODY.replace(HEAD, "a" * 39), BODY.replace(HEAD, HEAD.upper()), BODY.replace(" -->", " extra -->"),
                     BODY.replace("\n", "\r\n"), MARKER + " " + "\n", MARKER + "\n" + "x" * post.CAP]
        for body in malformed:
            with self.subTest(body=body[:100]):
                self.body.write_bytes(body.encode())
                self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        self.body.write_bytes(b"\xff")
        self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        self.assertEqual(self.calls(), [])

    def test_size_cap_is_in_bytes_and_inclusive(self):
        self.body.write_bytes((MARKER + "\n").encode() + b"x" * (post.CAP - len(MARKER) - 1))
        self.assertEqual(len(post.read_body(self.body).encode()), post.CAP)
        self.body.write_bytes(self.body.read_bytes() + b"x")
        with self.assertRaises(ValueError):
            post.read_body(self.body)

    def test_marker_variants_and_opaque_content_after_first_line(self):
        for kind in ("code", "security"):
            for verdict in ("APPROVE", "REWORK"):
                for lane in ("", " lane=yes"):
                    marker = f"<!-- fnl-review kind={kind} head={HEAD} verdict={verdict}{lane} -->"
                    body = marker + "\nAttacker-controlled text is not inspected by this wrapper.\n"
                    self.body.write_text(body)
                    self.assertEqual(post.read_body(self.body), body)

    def test_non_github_or_credential_bearing_remotes_refused_before_gh(self):
        for remote in ("https://other.example/sample-owner/sample-repository", "https://github.com.evil.example/sample/repo",
                       "https://user:secret" + AT + "github.com/sample/repo", "file:///sample/repo", "ext::anything",
                       "https://github.com/sample/repo?x=1", "ssh://git" + AT + "github.com:22/sample/repo", "git" + AT + "other.example:sample/repo"):
            with self.subTest(remote=remote):
                self.remote(remote)
                self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        self.assertEqual(self.calls(), [])

    def test_github_remote_forms_and_linked_worktree(self):
        for remote in ("https://github.com/sample/repo", "git" + AT + "github.com:sample/repo.git", "ssh://git" + AT + "github.com/sample/repo.git"):
            self.remote(remote)
            self.assertEqual(post.checkout_remote(self.checkout), "github.com/sample/repo")
        common = self.checkout / ".git"
        git = common / "worktrees/linked"
        git.mkdir(parents=True)
        (git / "commondir").write_text("../..\n")
        linked = self.base / "linked"
        linked.mkdir()
        (linked / ".git").write_text("gitdir: " + str(git) + "\n")
        (git / "gitdir").write_text(str(linked / ".git") + "\n")
        self.assertEqual(post.checkout_remote(linked), "github.com/sample/repo")

    def test_git_entry_redirect_fifo_and_owner_checks(self):
        git = self.checkout / ".git"
        original = self.base / "saved-git"
        git.rename(original)
        for kind in ("symlink", "fifo", "internal", "external"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    git.symlink_to(original, target_is_directory=True)
                elif kind == "fifo":
                    os.mkfifo(git)
                else:
                    target = self.checkout / "fake" if kind == "internal" else original
                    git.write_text("gitdir: " + str(target))
                self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
                git.unlink()
        original.rename(git)
        path = git / "config"
        path.unlink()
        os.mkfifo(path)
        self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        path.unlink()
        self.remote("https://github.com/sample/repo")
        original_fstat = os.fstat
        def wrong_owner(fd):
            info = original_fstat(fd)
            if info.st_ino == path.stat().st_ino:
                values = list(info)
                values[4] = os.getuid() + 1
                return os.stat_result(values)
            return info
        with mock.patch.object(os, "fstat", side_effect=wrong_owner):
            self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        self.assertEqual(self.calls(), [])

    def test_linked_metadata_links_and_back_pointer_refused(self):
        common = self.checkout / ".git"
        git = common / "worktrees/linked"
        git.mkdir(parents=True)
        linked = self.base / "linked"
        linked.mkdir()
        (linked / ".git").write_text("gitdir: " + str(git))
        (git / "commondir").write_text("../..")
        (git / "gitdir").write_text(str(linked / ".git"))
        for name in ("commondir", "gitdir"):
            path = git / name
            moved = git / (name + "-saved")
            path.rename(moved)
            path.symlink_to(moved)
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                post.checkout_remote(linked)
            path.unlink()
            moved.rename(path)
        (git / "gitdir").write_text(str(self.base / "wrong"))
        with self.assertRaises(ValueError):
            post.checkout_remote(linked)

    def test_changed_head_refuses_comment(self):
        (self.base / "head").write_text("f" * 40)
        self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.calls()[0][:2], ["pr", "view"])

    def test_missing_cli_and_fixed_error_reasons(self):
        self.fake.unlink()
        self.assertEqual(self.main(["31", "--body-file", str(self.body)])[:2], (1, "cannot-post: no-cli\n"))
        self.assertEqual(self.calls(), [])

    def test_failed_gh_has_fixed_reason_and_no_provider_text(self):
        for error, reason in (("HTTP 401 Authentication required", "no-auth"), ("HTTP 403 denied", "no-permission"),
                              ("Could not connect", "no-network"), ("arbitrary private error", "other")):
            with self.subTest(reason=reason):
                (self.base / "error").write_text(error)
                code, output, stderr = self.main(["31", "--body-file", str(self.body)])
                self.assertEqual((code, output, stderr), (1, f"cannot-post: {reason}\n", ""))
        self.assertTrue(all(c[:2] == ["pr", "view"] for c in self.calls()))

    def test_timeout_is_not_retried(self):
        with mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("gh", 30)) as run:
            self.assertEqual(self.main(["31", "--body-file", str(self.body)])[:2], (1, "cannot-post: no-network\n"))
            self.assertEqual(run.call_count, 1)

    def test_head_moves_after_post_report_unobserved_without_retry(self):
        (self.base / "move-head").touch()
        self.assertEqual(self.main(["31", "--body-file", str(self.body)])[:2], (1, "cannot-post: other\n"))
        self.assertEqual(sum(c[:2] == ["pr", "comment"] for c in self.calls()), 1)

    def test_same_login_relay_and_missing_edit_evidence_do_not_verify(self):
        for body, edited in ((MARKER + "\nRelayed by coordinator; reviewer: codex; approval: record\n", False), (BODY, None)):
            comment = dict(body=body, author=dict(login="sample-reviewer"), includesCreatedEdit=edited)
            self.assertFalse(post.posting_verified([comment], "sample-reviewer", MARKER))

    def test_untrusted_path_does_not_select_executable(self):
        # Exercise the actual selector, outside setUp's fake-gh seam.
        with mock.patch.dict(os.environ, {"PATH": ".:" + str(self.bin)}), \
             mock.patch.object(Path, "resolve", side_effect=FileNotFoundError):
            with self.assertRaises(post.CannotPost) as raised:
                self.real_trusted_gh()
            self.assertEqual(raised.exception.reason, "no-cli")
        self.assertEqual(self.calls(), [])

    def test_edited_comment_does_not_verify_posting(self):
        comment = dict(body=BODY, author=dict(login="sample-reviewer"), includesCreatedEdit=True)
        self.assertFalse(post.posting_verified([comment], "sample-reviewer", MARKER))

    def test_successful_post_removes_private_draft(self):
        post.post(31, self.body, self.checkout)
        self.assertFalse(self.body.parent.exists())

    def test_symlinked_config_is_refused_before_gh(self):
        config = self.checkout / ".git/config"
        target = self.base / "external-config"
        config.rename(target)
        config.symlink_to(target)
        self.assertEqual(self.main(["31", "--body-file", str(self.body)])[0], 2)
        self.assertEqual(self.calls(), [])

    def test_gh_redirect_environment_is_not_inherited(self):
        hostile = {"GH_HTTP_UNIX_SOCKET": "/tmp/hostile.sock", "HTTPS_PROXY": "https://hostile.invalid",
                   "GH_ENTERPRISE_TOKEN": "synthetic", "GH_CONFIG_DIR": "/tmp/hostile",
                   "GH_HOST": "hostile.invalid", "GH_REPO": "hostile/repo", "HTTP_PROXY": "https://hostile.invalid",
                   "ALL_PROXY": "https://hostile.invalid", "https_proxy": "https://hostile.invalid",
                   "LD_PRELOAD": "/tmp/hostile", "DYLD_INSERT_LIBRARIES": "/tmp/hostile"}
        with mock.patch.dict(os.environ, hostile), mock.patch.object(subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "{}", "")
            post.gh_call(str(self.fake), ["pr", "view", "31"])
        kwargs = run.call_args.kwargs
        self.assertFalse(set(hostile) & set(kwargs.get("env", os.environ)))
        self.assertEqual(kwargs["env"]["GH_PROMPT_DISABLED"], "1")
        self.assertEqual(kwargs["env"]["GH_TOKEN"], "synthetic-gh-token")
        self.assertEqual(kwargs["env"]["GITHUB_TOKEN"], "synthetic-github-token")
        self.assertEqual(kwargs["env"]["HOME"], str(self.home))
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)

    def test_yes_requires_both_marker_and_expected_identity(self):
        own = dict(body=BODY, author=dict(login="sample-reviewer"), includesCreatedEdit=False)
        relay = dict(body=BODY, author=dict(login="sample-coordinator"))
        self.assertTrue(post.posting_verified([own], "sample-reviewer", MARKER))
        for comments, expected, marker in (([relay], "sample-reviewer", MARKER), ([own], "other", MARKER),
                    ([dict(body="No marker", author=dict(login="sample-reviewer"))], "sample-reviewer", MARKER),
                    ([own], "sample-reviewer", MARKER.replace(HEAD, "f" * 40)),
                    ([own], "", MARKER), ([own], "sample-reviewer", "invalid"),
                    (None, "sample-reviewer", MARKER), ([{}, None], "sample-reviewer", MARKER)):
            with self.subTest(comments=comments):
                self.assertFalse(post.posting_verified(comments, expected, marker))


class TrustedGhSelectionTest(unittest.TestCase):
    def check(self, folder, *, mode=0o755, gid=80, uid=None, repository=False, target=None):
        candidate = Path(folder) / "gh"
        resolved = target or candidate
        def resolve(path, **kwargs):
            if path != candidate:
                raise FileNotFoundError
            return resolved
        info = SimpleNamespace(st_uid=os.getuid() if uid is None else uid,
                               st_gid=gid, st_mode=0o100000 | mode)
        with mock.patch.object(Path, "resolve", resolve), \
             mock.patch.object(Path, "stat", return_value=info), \
             mock.patch.object(Path, "exists", return_value=repository), \
             mock.patch.object(os, "access", return_value=True):
            return post.trusted_gh()

    def test_other_fixed_locations_stay_strict(self):
        for folder in ("/usr" + "/local/bin", "/usr" + "/bin"):
            with self.subTest(folder=folder):
                self.assertEqual(self.check(folder), str(Path(folder) / "gh"))
                for kwargs in ({"mode": 0o775}, {"mode": 0o757},
                               {"uid": os.getuid() + 1000}, {"repository": True}):
                    with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                        self.check(folder, **kwargs)

    def test_fixed_locations_cannot_resolve_to_temporary_or_other_prefix(self):
        for target in (Path("/tmp" + "/gh"), Path("/opt" + "/other/bin/gh")):
            with self.subTest(target=target), self.assertRaises(post.CannotPost):
                self.check("/usr" + "/local/bin", target=target)


class HomebrewGhTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.prefix = self.base / "homebrew"
        self.target = self.prefix / "Cellar" / "gh" / "1.0" / "bin" / "gh"
        self.target.parent.mkdir(parents=True)
        self.target.touch(mode=0o755)
        self.candidate = self.prefix / "bin" / "gh"
        self.candidate.parent.mkdir()
        self.candidate.symlink_to(self.target)
        (self.prefix / ".git").mkdir()
        self.overrides = {}

    def stat_path(self, path):
        info = path.stat()
        # Model Homebrew's admin-writable directories without chown or a
        # dependency on the test machine's groups; all writes stay in tmp.
        mode = info.st_mode | 0o020 if path.is_dir() else info.st_mode
        fields = dict(st_mode=mode, st_uid=os.getuid(), st_gid=80)
        fields.update(self.overrides.get(path, {}))
        return SimpleNamespace(**fields)

    def check(self):
        return post.homebrew_gh(self.candidate, self.prefix, os.getuid(), self.stat_path)

    def test_admin_writable_prefix_repository_and_cellar_symlink_allowed(self):
        self.assertEqual(self.check(), self.target)

    def test_nested_repository_refused_on_both_paths(self):
        for folder in (self.target.parent, self.candidate.parent):
            with self.subTest(folder=folder):
                marker = folder / ".git"
                marker.touch()
                with self.assertRaises(ValueError):
                    self.check()
                marker.unlink()

    def test_repository_above_prefix_refused(self):
        (self.base / ".git").mkdir()
        with self.assertRaises(ValueError):
            self.check()

    def test_world_write_other_group_and_other_owner_refused(self):
        for path in (self.prefix, self.candidate.parent, self.target.parent, self.target):
            for fields in ({"st_mode": path.stat().st_mode | 0o002},
                           {"st_mode": path.stat().st_mode | 0o020, "st_gid": 81},
                           {"st_uid": os.getuid() + 1000}):
                with self.subTest(path=path, fields=fields):
                    self.overrides[path] = fields
                    with self.assertRaises(ValueError):
                        self.check()
                    self.overrides.clear()

    def test_root_owned_components_allowed(self):
        self.overrides[self.prefix] = {"st_uid": 0}
        self.assertEqual(self.check(), self.target)

    def test_symlink_escaping_prefix_refused(self):
        outside = self.base / "outside"
        outside.touch(mode=0o755)
        self.candidate.unlink()
        self.candidate.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.check()

    def test_intermediate_symlink_leaving_then_reentering_prefix_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "back").symlink_to(self.target.parent, target_is_directory=True)
        self.candidate.unlink()
        self.candidate.parent.rmdir()
        self.candidate.parent.symlink_to(outside / "back", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.check()

    def test_symlinked_prefix_refused(self):
        alias = self.base / "alias"
        alias.symlink_to(self.prefix, target_is_directory=True)
        with self.assertRaises(ValueError):
            post.homebrew_gh(alias / "bin" / "gh", alias, os.getuid(), self.stat_path)

    def test_installed_homebrew_gh(self):
        prefix = Path("/opt" + "/homebrew")
        if not (prefix / "bin" / "gh").exists():
            self.skipTest("Homebrew gh is not installed")
        selected = Path(post.trusted_gh())
        self.assertTrue(selected.is_relative_to(prefix))
        self.assertTrue(selected.is_file())
        self.assertTrue(os.access(selected, os.X_OK))


if __name__ == "__main__":
    unittest.main()
