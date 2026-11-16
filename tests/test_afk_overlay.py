"""afk overlay (docs/specs/afk-overlay.md): reader, trust anchor, Git index check, writer target and loading."""
import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import afk_overlay as ov  # noqa: E402
import instructions_write as iw  # noqa: E402

TEXT = b"# afk overlay (owner, 2026-11-16)\n\n## Replaces AGENTS.md > Authority: push and merge\nAgents may push.\n"


def git(cwd, *args):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd), "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


class OverlayTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name).resolve()
        self.home = account(self, base / "home")
        self.data = self.home / ".finolabs/vibecode"
        self.data.mkdir(parents=True, mode=0o700)
        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "AGENTS.md").write_text("# Rules\n")
        git(self.repo, "add", "AGENTS.md")
        git(self.repo, "commit", "-q", "-m", "init")
        env = mock.patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop(ov.OFF, None)
        cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)
        self.ident = ov.repository(self.repo)
        self.assertIsNotNone(self.ident)

    def overlay(self, data=TEXT, anchor=True):
        path = self.repo / ov.NAME
        path.write_bytes(data)
        path.chmod(0o600)
        if anchor:
            ov.write_anchor(self.ident, data)
        return path

    def lease(self, mode=None):
        if mode is not None:
            (self.data / "host.md").write_text("## afk\n- Mode: %s\n" % mode)
            (self.data / "host.md").chmod(0o600)
        folder = self.data / "state/autopilot"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.data / "state").chmod(0o700)
        folder.chmod(0o700)
        now = time.time()
        (folder / "lease.json").write_text(json.dumps({"id": "a" * 32, "start": now - 60, "expiry": now + 3600,
                                                       "settings_hash": "b" * 64, "counters": {}}))
        (folder / "lease.json").chmod(0o600)


class ReaderTest(OverlayTest):
    def test_no_file_prints_nothing(self):
        self.assertEqual(ov.state(self.repo), ("none", None))
        self.assertEqual(ov.lines(self.repo), "")

    def test_matching_untracked_file_is_in_force_and_framed(self):
        self.overlay()
        kind, text = ov.state(self.repo)
        self.assertEqual(kind, "in-force")
        self.assertEqual(text.encode(), TEXT)
        out = ov.lines(self.repo)
        self.assertTrue(out.startswith(ov.HEADER + "\n"))
        self.assertTrue(out.endswith(ov.FOOTER + "\n"))

    def test_every_failed_check_prints_only_the_fixed_line(self):
        cases = {
            "no anchor": lambda: self.overlay(anchor=False),
            "changed bytes": lambda: (self.overlay(), (self.repo / ov.NAME).write_bytes(TEXT + b"Agents may merge.\n")),
            "group writable": lambda: (self.overlay(), (self.repo / ov.NAME).chmod(0o620)),
            "over the cap": lambda: self.overlay(b"x" * (ov.LIMIT + 1)),
            "tracked": lambda: (self.overlay(), git(self.repo, "add", "-f", ov.NAME)),
            "bad anchor": lambda: (self.overlay(), (self.data / ov.STATE / ov.anchor_name(self.ident)).write_text("{}")),
        }
        for name, make in cases.items():
            with self.subTest(case=name):
                make()
                self.assertEqual(ov.state(self.repo), ("not-in-force", None))
                self.assertEqual(ov.lines(self.repo), ov.NOT_IN_FORCE + "\n")
                git(self.repo, "rm", "-q", "--cached", "--ignore-unmatch", ov.NAME)
                (self.repo / ov.NAME).unlink()

    def test_a_symlink_is_not_in_force(self):
        target = self.repo / "elsewhere.md"
        target.write_bytes(TEXT)
        (self.repo / ov.NAME).symlink_to(target)
        ov.write_anchor(self.ident, TEXT)
        self.assertEqual(ov.state(self.repo)[0], "not-in-force")

    def test_off_switch_prints_nothing(self):
        self.overlay()
        os.environ[ov.OFF] = "off"
        self.assertEqual(ov.lines(self.repo), "")

    def test_a_linked_worktree_reads_the_main_checkout_overlay(self):
        self.overlay()
        worktree = self.repo / ".claude/worktrees/task"
        git(self.repo, "worktree", "add", "-q", "-b", "task", str(worktree))
        self.assertEqual(ov.state(worktree)[0], "in-force")
        self.assertFalse((worktree / ov.NAME).exists())

    def test_index_versions_two_three_and_four(self):
        for name in ("a.txt", "b/c.txt", "AGENTS.afk.md.old"):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x")
        git(self.repo, "add", "-A")
        for version in ("2", "3", "4"):
            with self.subTest(version=version):
                git(self.repo, "update-index", "--index-version", version)
                paths = ov.index_paths((self.repo / ".git/index").read_bytes())
                self.assertEqual([p.decode() for p in paths], ["AGENTS.afk.md.old", "AGENTS.md", "a.txt", "b/c.txt"])
                self.assertFalse(ov.tracked(self.ident))

    def test_a_truncated_index_raises(self):
        raw = (self.repo / ".git/index").read_bytes()
        with self.assertRaises((ValueError, IndexError)):
            ov.index_paths(raw[:40] + raw[-20:])

    def test_names_match_in_any_case(self):
        for name in ("AGENTS.afk.md", "agents.afk.md", "AGENTS.AFK.MD.bak", "AGENTS.afk.md.bak-20261116"):
            self.assertTrue(ov.is_name(name), name)
        self.assertFalse(ov.is_name("AGENTS.md"))


class ModeTest(OverlayTest):
    def test_mode_from_the_account_section(self):
        for text, expected in (("## afk\n- Mode: strict\n", "strict"), ("## afk\n- Hosts: Codex\n", "open")):
            with self.subTest(text=text):
                (self.data / "host.md").write_text(text)
                (self.data / "host.md").chmod(0o600)
                self.assertEqual(ov.mode(self.ident), expected)
        for text in ("## afk\n- Mode: loose\n", "# nothing\n"):
            with self.subTest(text=text):
                (self.data / "host.md").write_text(text)
                with self.assertRaises(ValueError):
                    ov.mode(self.ident)

    def test_write_refused_only_under_a_strict_or_unreadable_lease(self):
        self.assertIsNone(ov.write_refused(self.ident))
        self.lease("open")
        self.assertIsNone(ov.write_refused(self.ident))
        self.lease("strict")
        self.assertIn("strict", ov.write_refused(self.ident))
        (self.data / "state/autopilot/lease.json").chmod(0o644)
        self.assertIsNotNone(ov.write_refused(self.ident))


class WriterTest(OverlayTest):
    def preview_apply(self, data):
        draft = self.repo.parent / "draft.md"
        draft.write_bytes(data)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            iw.preview(str(self.repo / ov.NAME), str(draft), None)
        digest = out.getvalue().rsplit("Digest: ", 1)[1].strip()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            iw.apply(digest, True)
        return out.getvalue()

    def test_apply_writes_file_exclude_and_anchor_and_backs_up_privately(self):
        result = self.preview_apply(TEXT)
        self.assertIn("trust anchor recorded", result)
        self.assertEqual((self.repo / ov.NAME).read_bytes(), TEXT)
        self.assertEqual(oct((self.repo / ov.NAME).stat().st_mode & 0o777), "0o600")
        self.assertIn("AGENTS.afk.md*", (self.repo / ".git/info/exclude").read_text())
        self.assertEqual(ov.state(self.repo)[0], "in-force")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True).stdout
        self.assertNotIn(ov.NAME, status)
        self.preview_apply(TEXT + b"More.\n")
        self.assertEqual(ov.state(self.repo)[0], "in-force")
        self.assertEqual(list(self.repo.glob("AGENTS.afk.md.bak*")), [])
        self.assertEqual(len(list((self.data / ov.BACKUPS).iterdir())), 1)
        record = json.loads((self.data / ov.STATE / ov.anchor_name(self.ident)).read_text())
        self.assertEqual(set(record), {"sha256", "time"})
        self.assertEqual(record["sha256"], hashlib.sha256(TEXT + b"More.\n").hexdigest())

    def test_refusals(self):
        draft = self.repo.parent / "draft.md"
        draft.write_bytes(TEXT)
        with self.assertRaises(iw.Refusal):
            iw.preview(str(self.repo / ov.NAME), str(draft), "Agent skills")
        (self.repo / "sub").mkdir()
        with self.assertRaises(iw.Refusal):
            iw.preview(str(self.repo / "sub" / ov.NAME), str(draft), None)
        self.overlay(anchor=False)
        git(self.repo, "add", "-f", ov.NAME)
        with self.assertRaises(iw.Refusal):
            iw.preview(str(self.repo / ov.NAME), str(draft), None)
        git(self.repo, "rm", "-q", "--cached", ov.NAME)
        self.lease("strict")
        with self.assertRaises(iw.Refusal):
            iw.preview(str(self.repo / ov.NAME), str(draft), None)

    def test_oversized_or_control_text_and_a_strict_apply_are_refused(self):
        draft = self.repo.parent / "draft.md"
        for data in (b"x" * (ov.LIMIT + 1), b"Agents may push.\x1b[2J\n", "\u202eevil\n".encode()):
            draft.write_bytes(data)
            with self.assertRaises(iw.Refusal):
                iw.preview(str(self.repo / ov.NAME), str(draft), None)
        draft.write_bytes(TEXT)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            iw.preview(str(self.repo / ov.NAME), str(draft), None)
        self.lease("strict")
        with self.assertRaises(iw.Refusal):
            iw.apply(out.getvalue().rsplit("Digest: ", 1)[1].strip(), True)
        self.assertFalse((self.repo / ov.NAME).exists())

    def test_an_open_lease_allows_the_write(self):
        self.lease("open")
        self.preview_apply(TEXT)
        self.assertEqual(ov.state(self.repo)[0], "in-force")


class LoadingTest(OverlayTest):
    def hook_state(self):
        hook = importlib.import_module("session_start")
        return hook.overlay_lines()

    def test_the_hook_prints_the_overlay_only_while_a_lease_is_live(self):
        self.overlay()
        self.assertEqual(self.hook_state(), "")
        self.lease("open")
        self.assertIn(ov.HEADER, self.hook_state())
        (self.repo / ov.NAME).write_bytes(TEXT + b"changed\n")
        self.assertEqual(self.hook_state(), ov.NOT_IN_FORCE + "\n")


class ProtectedNameTest(unittest.TestCase):
    def test_strict_protects_the_overlay_and_the_constitution(self):
        sys.path.insert(0, str(ROOT / "skills/delegate/scripts"))
        self.addCleanup(sys.path.remove, str(ROOT / "skills/delegate/scripts"))
        afk = importlib.import_module("afk")
        for value in ("AGENTS.afk.md", "agents.afk.md", "AGENTS.afk.md.bak-20261116", ".specify/memory/constitution.md",
                      "./.specify/memory/constitution.md"):
            self.assertTrue(afk.protected(value), value)
            self.assertTrue(afk.protected(value, source=True), value)
        for value in ("docs/constitution.md", "AGENTS.md.notes", "src/agents.ts"):
            self.assertFalse(afk.protected(value, source=True), value)
        for value in ("AGENT\u017f.afk.md", ".\u017fpecify/memory/con\u017ftitution.md"):
            self.assertTrue(afk.protected(value, source=True), value)
        for value in (".specify//memory/constitution.md", ".specify/./memory/constitution.md", "--file=.specify/memory/constitution.md"):
            self.assertTrue(afk.protected(value), value)

    def test_the_constitution_is_protected_from_inside_its_folder(self):
        sys.path.insert(0, str(ROOT / "skills/delegate/scripts"))
        self.addCleanup(sys.path.remove, str(ROOT / "skills/delegate/scripts"))
        afk = importlib.import_module("afk")
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp).resolve() / "repo"
            (repo / ".specify/memory").mkdir(parents=True)
            git(repo, "init", "-q", "-b", "main")
            (repo / ".specify/memory/constitution.md").write_text("# Constitution\n")
            found, ident = afk.store.identity(str(repo))
            self.assertEqual(found, "found")
            inside = str(repo / ".specify/memory")
            context = afk.Context("found", ident, "user", None, inside)
            applied = {afk.CONTEXT: context}
            self.assertTrue(afk.token_protected("constitution.md", applied))
            self.assertEqual(afk.classify_paths(["constitution.md"], context=context), "protected")
            self.assertFalse(afk.token_protected("notes.md", applied))


if __name__ == "__main__":
    unittest.main()
