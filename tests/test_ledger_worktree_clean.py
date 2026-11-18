"""ledger.py removes the worktrees of finished dispatches once their branch merged, and nothing else.

Every repository here is a temporary one; the real checkout is never touched, and gh is never reachable.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/delegate/scripts"
LEDGER = SCRIPTS / "ledger.py"
START = ["start", "--project", "demo", "--task", "t1", "--kind", "implement", "--grade", "medium",
         "--agent", "codex", "--model", "m1", "--budget", "40"]


class WorktreeCleanTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.home = account(self, self.base / "home")
        self.ledger = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.ledger.parent.mkdir(parents=True)
        tools = self.base / "tools"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        path = os.pathsep.join([str(tools), "/usr/bin", "/bin"])
        if shutil.which("gh", path=path):
            self.skipTest("a gh on the system path would reach the network")
        self.env = {"PATH": path, "HOME": str(self.home), "ORCHESTRATION_LEDGER": str(self.ledger),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test",
                    "GIT_AUTHOR_EMAIL": "test" "@example.invalid", "GIT_COMMITTER_EMAIL": "test" "@example.invalid"}
        origin = self.base / "origin.git"
        self.git(self.base, "init", "-q", "--bare", "-b", "main", str(origin))
        seed = self.base / "seed"
        self.git(self.base, "init", "-q", "-b", "main", str(seed))
        (seed / "README.md").write_text("seed\n")
        self.git(seed, "add", "README.md")
        self.git(seed, "commit", "-q", "-m", "Seed")
        self.git(seed, "push", "-q", str(origin), "main")
        self.main = self.base / "main"
        self.git(self.base, "clone", "-q", str(origin), str(self.main))

    def git(self, cwd, *args, check=True):
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=check,
                              env=self.env)

    def worktree(self, name, *, merge=True):
        path = self.main / ".wt" / name
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", name, str(path), "origin/main")
        (path / f"{name}.txt").write_text(name + "\n")
        self.git(path, "add", f"{name}.txt")
        self.git(path, "commit", "-q", "-m", "Add " + name)
        self.git(path, "push", "-q", "-u", "origin", name)
        if merge:
            self.git(self.main, "merge", "-q", "--no-ff", "-m", "Merge " + name, name)
            self.git(self.main, "push", "-q", "origin", "main")
            self.git(self.main, "fetch", "-q", "origin")
        return path

    def ledger_run(self, *args, env=None, cwd=None):
        result = subprocess.run([sys.executable, "-I", str(LEDGER), *args], capture_output=True, text=True,
                                env=env or self.env, cwd=cwd or self.main)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def dispatch(self, checkout, *, finish=True):
        dispatch_id = self.ledger_run(*START, "--checkout", str(checkout)).stdout.strip()
        if finish:
            self.ledger_run("finish", dispatch_id, "--outcome", "cancelled", "--checkout", str(checkout))
        return dispatch_id

    def branches(self):
        return self.git(self.main, "branch", "--format=%(refname:short)").stdout.split()

    def test_a_finished_dispatch_worktree_is_removed_once_merged(self):
        path = self.worktree("feat-a")
        self.dispatch(path)
        # finish ran the cleanup already, so an explicit run finds nothing more to do
        self.assertFalse(path.exists())
        self.assertNotIn("feat-a", self.branches())
        out = self.ledger_run("clean-worktrees")
        self.assertIn("ledger: worktree cleanup: 0 removed", out.stderr)

    def test_the_explicit_command_reports_what_it_removed(self):
        path = self.worktree("feat-b")
        off = dict(self.env, FNL_WORKTREE_CLEAN="off")
        dispatch_id = self.ledger_run(*START, "--checkout", str(path), env=off).stdout.strip()
        self.ledger_run("finish", dispatch_id, "--outcome", "cancelled", "--checkout", str(path), env=off)
        self.assertTrue(path.exists())
        out = self.ledger_run("clean-worktrees")
        self.assertFalse(path.exists())
        self.assertIn("removed", out.stderr)
        self.assertIn("feat-b", out.stderr)
        self.assertIn("ledger: worktree cleanup: 1 removed", out.stderr)
        self.assertEqual(out.stdout, "")

    def test_unmerged_dirty_open_and_foreign_worktrees_stay(self):
        unmerged = self.worktree("feat-c", merge=False)
        self.dispatch(unmerged)
        dirty = self.worktree("feat-d")
        (dirty / "scratch.txt").write_text("work\n")
        self.dispatch(dirty)
        running = self.worktree("feat-e")
        self.dispatch(running, finish=False)
        foreign = self.worktree("feat-f")  # merged and clean, but no dispatch ever named it
        out = self.ledger_run("clean-worktrees")
        for path in (unmerged, dirty, running, foreign):
            self.assertTrue(path.exists(), path.name)
        self.assertIn("kept", out.stderr)
        self.assertIn("ledger: worktree cleanup: 0 removed", out.stderr)
        for name in ("feat-c", "feat-d", "feat-e", "feat-f"):
            self.assertIn(name, self.branches())

    def test_a_later_start_removes_a_worktree_merged_after_its_finish(self):
        path = self.worktree("feat-g", merge=False)
        self.dispatch(path)
        self.assertTrue(path.exists())
        self.git(self.main, "merge", "-q", "--no-ff", "-m", "Merge feat-g", "feat-g")
        self.git(self.main, "push", "-q", "origin", "main")
        self.git(self.main, "fetch", "-q", "origin")
        out = self.ledger_run(*START, "--checkout", str(self.main))
        self.assertFalse(path.exists())
        self.assertNotIn("feat-g", self.branches())
        self.assertRegex(out.stdout.strip(), r"^[a-z0-9-]+$")  # stdout stays the dispatch id alone
        self.assertIn("removed", out.stderr)

    def test_the_off_switch_keeps_everything(self):
        path = self.worktree("feat-h")
        env = dict(self.env, FNL_WORKTREE_CLEAN="off")
        dispatch_id = self.ledger_run(*START, "--checkout", str(path), env=env).stdout.strip()
        self.ledger_run("finish", dispatch_id, "--outcome", "cancelled", "--checkout", str(path), env=env)
        self.ledger_run("clean-worktrees", env=env)
        self.assertTrue(path.exists())

    def test_a_live_lease_skips_the_cleanup(self):
        path = self.worktree("feat-i")
        env = dict(self.env, FNL_WORKTREE_CLEAN="off")
        dispatch_id = self.ledger_run(*START, "--checkout", str(path), env=env).stdout.strip()
        self.ledger_run("finish", dispatch_id, "--outcome", "cancelled", "--checkout", str(path), env=env)
        spec = importlib.util.spec_from_file_location("ledger_under_test", LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        spec.loader.exec_module(ledger)
        with mock.patch.dict(os.environ, {"ORCHESTRATION_LEDGER": str(self.ledger), "PATH": self.env["PATH"],
                                          "GIT_CONFIG_NOSYSTEM": "1"}), \
                mock.patch("away_lease.live_lease", return_value={"id": "x"}):
            lines = ledger.clean_worktrees(str(self.main))
        self.assertTrue(path.exists())
        self.assertEqual(len(lines), 1)
        self.assertIn("away lease", lines[0])

    def test_removal_never_forces(self):
        source = LEDGER.read_text()
        self.assertNotIn("--force", source)
        self.assertNotIn("rmtree", source)
        self.assertNotIn('"-D"', source)

    def test_delegate_copy_of_the_sweep_matches(self):
        sweep = ROOT / "skills/commit-messages/scripts/worktree_sweep.py"
        self.assertEqual((SCRIPTS / "worktree_sweep.py").read_bytes(), sweep.read_bytes())


if __name__ == "__main__":
    unittest.main()
