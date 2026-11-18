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
            lines, _ = ledger.clean_worktrees(str(self.main))
        self.assertTrue(path.exists())
        self.assertEqual(len(lines), 1)
        self.assertIn("away lease", lines[0])

    def load_ledger(self):
        spec = importlib.util.spec_from_file_location("ledger_under_test", LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        spec.loader.exec_module(ledger)
        patch = mock.patch.dict(os.environ, {"ORCHESTRATION_LEDGER": str(self.ledger), "PATH": self.env["PATH"],
                                             "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)
        return ledger

    def finished_off(self, path):
        off = dict(self.env, FNL_WORKTREE_CLEAN="off")
        dispatch_id = self.ledger_run(*START, "--checkout", str(path), env=off).stdout.strip()
        self.ledger_run("finish", dispatch_id, "--outcome", "cancelled", "--checkout", str(path), env=off)

    def test_a_worktree_registered_with_other_case_still_matches(self):
        probe = self.base / "CaseProbe"
        probe.mkdir()
        if not (self.base / "caseprobe").exists():
            self.skipTest("case-sensitive file system")
        path = Path(str(self.main / ".wt").swapcase()) / "feat-j"
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", "feat-j", str(path), "origin/main")
        self.git(path, "commit", "-q", "--allow-empty", "-m", "Empty")
        self.git(path, "push", "-q", "-u", "origin", "feat-j")
        self.git(self.main, "merge", "-q", "--no-ff", "-m", "Merge feat-j", "feat-j")
        self.git(self.main, "push", "-q", "origin", "main")
        self.git(self.main, "fetch", "-q", "origin")
        self.finished_off(path)
        out = self.ledger_run("clean-worktrees")
        self.assertIn("1 removed", out.stderr)
        self.assertFalse(path.exists())

    def gh_stub(self, body):
        stub = self.base / "stub"
        stub.mkdir(exist_ok=True)
        (stub / "gh").write_text("#!/bin/sh\n" + body)
        (stub / "gh").chmod(0o755)
        return dict(self.env, PATH=os.pathsep.join([str(stub), self.env["PATH"]]))

    def test_the_automatic_cleanup_never_calls_the_forge(self):
        path = self.worktree("feat-k", merge=False)
        marker = self.base / "gh-called"
        env = self.gh_stub(f"touch {marker}\necho '[]'\n")
        self.finished_off(path)
        self.ledger_run(*START, "--checkout", str(self.main), env=env)
        self.assertFalse(marker.exists())
        self.assertTrue(path.exists())

    def test_an_inherited_gh_repo_never_proves_a_merge(self):
        path = self.worktree("feat-l", merge=False)
        head = self.git(path, "rev-parse", "HEAD").stdout.strip()
        # The stub answers "merged at this head" only when GH_REPO names another repository.
        env = self.gh_stub('if [ -n "$GH_REPO" ]; then echo \'[{"number": 1, "headRefOid": "' + head +
                           '"}]\'; else echo \'[]\'; fi\n')
        env["GH_REPO"] = "someone/else"
        self.finished_off(path)
        out = self.ledger_run("clean-worktrees", env=env)
        self.assertTrue(path.exists())
        self.assertIn("merged=no", out.stderr)

    def test_a_dispatch_started_during_cleanup_keeps_its_worktree(self):
        path = self.worktree("feat-m")
        self.finished_off(path)
        ledger = self.load_ledger()
        import worktree_sweep
        real = worktree_sweep.describe

        def describe(entry, default, forge=True):
            self.ledger_run(*START, "--checkout", str(path), env=dict(self.env, FNL_WORKTREE_CLEAN="off"))
            return real(entry, default, forge)

        with mock.patch.object(worktree_sweep, "describe", describe):
            lines, failed = ledger.clean_worktrees(str(self.main), "explicit")
        self.assertTrue(path.exists())
        self.assertFalse(failed)
        self.assertTrue(any("a dispatch started on it" in line for line in lines), lines)

    def test_a_lease_started_during_cleanup_keeps_the_worktree(self):
        path = self.worktree("feat-n")
        self.finished_off(path)
        ledger = self.load_ledger()
        with mock.patch.object(ledger, "lease_live", side_effect=[False, True]):
            lines, _ = ledger.clean_worktrees(str(self.main), "explicit")
        self.assertTrue(path.exists())
        self.assertTrue(any("an away lease started" in line for line in lines), lines)

    def test_a_failure_keeps_the_report_of_earlier_removals(self):
        first, second = self.worktree("feat-o"), self.worktree("feat-p")
        self.finished_off(first)
        self.finished_off(second)
        ledger = self.load_ledger()
        import worktree_sweep
        real = worktree_sweep.describe

        def describe(entry, default, forge=True):
            if entry["path"].endswith("feat-p"):
                raise OSError("boom")
            return real(entry, default, forge)

        with mock.patch.object(worktree_sweep, "describe", describe):
            lines, failed = ledger.clean_worktrees(str(self.main), "explicit")
        self.assertTrue(failed)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        self.assertTrue(any("removed worktree" in line and "feat-o" in line for line in lines), lines)
        self.assertTrue(any("failed at" in line for line in lines), lines)

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
