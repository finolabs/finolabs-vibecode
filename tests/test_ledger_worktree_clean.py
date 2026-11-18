"""ledger.py removes the worktrees of finished dispatches once their branch merged, and nothing else.

Every repository here is a temporary one; the real checkout is never touched, and gh is never reachable
unless a test puts its own stub first. Most tests set FNL_WORKTREE_CLEAN=manual, so no background run races
the assertions; the background start itself is tested with a patched Popen and a synchronous --background run.
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
        root = self.home / ".finolabs/vibecode"
        root.mkdir(parents=True, mode=0o700)
        self.ledger = root / "ledger.jsonl"
        tools = self.base / "tools"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        path = os.pathsep.join([str(tools), "/usr/bin", "/bin"])
        if shutil.which("gh", path=path):
            self.skipTest("a gh on the system path would reach the network")
        self.env = {"PATH": path, "HOME": str(self.home), "ORCHESTRATION_LEDGER": str(self.ledger),
                    "FNL_WORKTREE_CLEAN": "manual", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_AUTHOR_NAME": "Test", "GIT_COMMITTER_NAME": "Test",
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

    def merge(self, name):
        self.git(self.main, "merge", "-q", "--no-ff", "-m", "Merge " + name, name)
        self.git(self.main, "push", "-q", "origin", "main")
        self.git(self.main, "fetch", "-q", "origin")

    def worktree(self, name, *, merge=True, parent=None):
        path = (parent or self.main / ".wt") / name
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", name, str(path), "origin/main")
        (path / f"{name}.txt").write_text(name + "\n")
        self.git(path, "add", f"{name}.txt")
        self.git(path, "commit", "-q", "-m", "Add " + name)
        self.git(path, "push", "-q", "-u", "origin", name)
        if merge:
            self.merge(name)
        return path

    def ledger_run(self, *args, env=None, code=0):
        result = subprocess.run([sys.executable, "-I", str(LEDGER), *args], capture_output=True, text=True,
                                env=env or self.env, cwd=self.main)
        if code is not None:
            self.assertEqual(result.returncode, code, result.stderr)
        return result

    def dispatch(self, checkout, *, finish=True):
        dispatch_id = self.ledger_run(*START, "--checkout", str(checkout)).stdout.strip()
        if finish:
            self.ledger_run("finish", dispatch_id, "--outcome", "cancelled", "--checkout", str(checkout))
        return dispatch_id

    def branches(self):
        return self.git(self.main, "branch", "--format=%(refname:short)").stdout.split()

    def load_ledger(self):
        spec = importlib.util.spec_from_file_location("ledger_under_test", LEDGER)
        ledger = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS))
        self.addCleanup(sys.path.remove, str(SCRIPTS))
        patch = mock.patch.dict(os.environ, {key: value for key, value in self.env.items()})
        patch.start()
        self.addCleanup(patch.stop)
        spec.loader.exec_module(ledger)
        import worktree_sweep
        return ledger, worktree_sweep

    # -- what is removed and what stays

    def test_clean_worktrees_removes_a_finished_merged_worktree_and_its_branch(self):
        path = self.worktree("feat-a")
        self.dispatch(path)
        self.assertTrue(path.exists())  # manual mode: start and finish started nothing
        out = self.ledger_run("clean-worktrees")
        self.assertFalse(path.exists())
        self.assertNotIn("feat-a", self.branches())
        self.assertIn("removed worktree", out.stderr)
        self.assertIn("branch feat-a", out.stderr)
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
        self.assertIn("kept worktree", out.stderr)
        self.assertIn("ledger: worktree cleanup: 0 removed", out.stderr)
        for name in ("feat-c", "feat-d", "feat-e", "feat-f"):
            self.assertIn(name, self.branches())

    def test_a_worktree_registered_with_other_case_still_matches(self):
        probe = self.base / "CaseProbe"
        probe.mkdir()
        if not (self.base / "caseprobe").exists():
            self.skipTest("case-sensitive file system")
        path = self.worktree("feat-j", parent=Path(str(self.main / ".wt").swapcase()))
        self.dispatch(path)
        out = self.ledger_run("clean-worktrees")
        self.assertIn("1 removed", out.stderr)
        self.assertFalse(path.exists())

    def gh_stub(self, body):
        stub = self.base / "stub"
        stub.mkdir(exist_ok=True)
        (stub / "gh").write_text("#!/bin/sh\n" + body)
        (stub / "gh").chmod(0o755)
        return dict(self.env, PATH=os.pathsep.join([str(stub), self.env["PATH"]]))

    def test_an_inherited_gh_repo_never_proves_a_merge(self):
        path = self.worktree("feat-l", merge=False)
        head = self.git(path, "rev-parse", "HEAD").stdout.strip()
        # The stub answers "merged at this head" only when GH_REPO names another repository.
        env = self.gh_stub('if [ -n "$GH_REPO" ]; then echo \'[{"number": 1, "headRefOid": "' + head +
                           '"}]\'; else echo \'[]\'; fi\n')
        env["GH_REPO"] = "someone/else"
        self.dispatch(path)
        out = self.ledger_run("clean-worktrees", env=env)
        self.assertTrue(path.exists())
        self.assertIn("merged=no", out.stderr)

    def test_an_inherited_git_dir_never_proves_a_merge(self):
        path = self.worktree("feat-l2", merge=False)
        head = self.git(path, "rev-parse", "HEAD").stdout.strip()
        # The stub answers "merged at this head" only when a GIT_* override reaches it.
        env = self.gh_stub('if env | grep -q "^GIT_"; then echo \'[{"number": 1, "headRefOid": "' + head +
                           '"}]\'; else echo \'[]\'; fi\n')
        env["GIT_DIR"] = str(self.base / "origin.git")
        self.dispatch(path)
        out = self.ledger_run("clean-worktrees", env=env)
        self.assertTrue(path.exists())
        self.assertIn("merged=no", out.stderr)

    def test_the_forge_proves_a_pruned_squash_merge(self):
        path = self.worktree("feat-p", merge=False)
        head = self.git(path, "rev-parse", "HEAD").stdout.strip()
        self.git(self.main, "push", "-q", "origin", "--delete", "feat-p")
        self.git(self.main, "fetch", "-q", "--prune", "origin")
        env = self.gh_stub("echo '[{\"number\": 8, \"headRefOid\": \"" + head + "\"}]'\n")
        self.dispatch(path)
        out = self.ledger_run("clean-worktrees", env=env)
        self.assertFalse(path.exists(), out.stderr)

    def test_the_forge_proves_a_squash_merge(self):
        path = self.worktree("feat-q", merge=False)
        head = self.git(path, "rev-parse", "HEAD").stdout.strip()
        env = self.gh_stub("echo '[{\"number\": 7, \"headRefOid\": \"" + head + "\"}]'\n")
        self.dispatch(path)
        out = self.ledger_run("clean-worktrees", env=env)
        self.assertFalse(path.exists(), out.stderr)

    # -- triggers

    def test_start_and_finish_start_a_background_run(self):
        path = self.worktree("feat-g")
        ledger, _ = self.load_ledger()
        import contextlib
        import io
        with mock.patch.object(ledger, "spawn_cleanup") as spawn, contextlib.redirect_stderr(io.StringIO()):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                args = ledger.build_parser().parse_args([*START, "--checkout", str(path)])
                args.func(args)
            dispatch_id = out.getvalue().strip()
            args = ledger.build_parser().parse_args(["finish", dispatch_id, "--outcome", "cancelled",
                                                     "--checkout", str(path)])
            args.func(args)
        self.assertEqual([call.args[0] for call in spawn.call_args_list], [str(path), str(path)])

    def test_spawn_cleanup_starts_one_detached_run_only_when_on(self):
        ledger, _ = self.load_ledger()
        for mode, expected in (("", 1), ("manual", 0), ("off", 0)):
            with self.subTest(mode=mode), mock.patch.dict(os.environ, {"FNL_WORKTREE_CLEAN": mode}), \
                    mock.patch.object(ledger.subprocess, "Popen") as popen:
                ledger.spawn_cleanup(str(self.main))
                self.assertEqual(popen.call_count, expected)
                for call in popen.call_args_list:
                    self.assertEqual(call.args[0][3:5], ["clean-worktrees", "--background"])
                    self.assertTrue(call.kwargs["start_new_session"])
                    self.assertIs(call.kwargs["stdout"], subprocess.DEVNULL)

    def test_a_background_run_removes_and_prints_nothing(self):
        path = self.worktree("feat-h")
        self.dispatch(path)
        out = self.ledger_run("clean-worktrees", "--background", env=dict(self.env, FNL_WORKTREE_CLEAN=""))
        self.assertFalse(path.exists())
        self.assertEqual((out.stdout, out.stderr), ("", ""))

    def test_a_background_run_stays_silent_on_a_malformed_ledger(self):
        path = self.worktree("feat-h2")
        self.dispatch(path)
        with self.ledger.open("a") as handle:
            handle.write("not json\n")
        out = self.ledger_run("clean-worktrees", "--background", env=dict(self.env, FNL_WORKTREE_CLEAN=""))
        self.assertEqual((out.stdout, out.stderr), ("", ""))

    def test_the_off_switch_keeps_everything(self):
        path = self.worktree("feat-i")
        self.dispatch(path)
        self.ledger_run("clean-worktrees", env=dict(self.env, FNL_WORKTREE_CLEAN="off"))
        self.assertTrue(path.exists())

    # -- the claim

    def claimable(self, name):
        path = self.worktree(name)
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        entries = sweep.worktrees(str(self.main))
        entry = next(e for e in entries if e["path"].endswith(name))
        default = sweep.default_ref(entries[0]["path"])
        info = ledger.inspect(sweep, entry, default, forge=False)
        return path, ledger, sweep, info, default

    def claim(self, ledger, sweep, info, default):
        return ledger.claim(sweep, info, default, None, sweep.spellings(str(self.base)), str(self.main))

    def retiring(self):
        return sorted((self.main / ".wt").glob(".fnl-retiring-*"))

    def test_a_moved_head_is_not_claimed(self):
        path, ledger, sweep, info, default = self.claimable("feat-s")
        (path / "more.txt").write_text("more\n")
        self.git(path, "add", "more.txt")
        self.git(path, "commit", "-q", "-m", "More")
        self.git(path, "push", "-q", "origin", "feat-s")
        self.assertEqual(self.claim(ledger, sweep, info, default), ("its HEAD moved", None))
        self.assertTrue(path.exists())

    def test_a_dispatch_started_after_inspection_is_not_claimed(self):
        path, ledger, sweep, info, default = self.claimable("feat-m")
        self.ledger_run(*START, "--checkout", str(path))
        self.assertEqual(self.claim(ledger, sweep, info, default), ("a dispatch started on it", None))
        self.assertTrue(path.exists())

    def test_a_lease_started_after_inspection_is_not_claimed(self):
        path, ledger, sweep, info, default = self.claimable("feat-n")
        with mock.patch.object(ledger, "lease_live", return_value=True):
            reason = self.claim(ledger, sweep, info, default)
        self.assertEqual(reason, ("an away lease started", None))
        self.assertTrue(path.exists())
        self.assertEqual(self.retiring(), [])

    def test_a_claim_renames_the_worktree_away_from_its_path(self):
        path, ledger, sweep, info, default = self.claimable("feat-t")
        reason, moved = self.claim(ledger, sweep, info, default)
        self.assertIsNone(reason)
        self.assertFalse(path.exists())
        self.assertEqual([Path(moved)], self.retiring())
        # A start on the old path, in any spelling, finds no checkout to attach to the claimed worktree.
        from record import checkout_identity
        claimed = checkout_identity(moved)
        for spelling in (path, Path(str(path).swapcase())):
            self.ledger_run(*START, "--checkout", str(spelling), code=None)
        self.assertNotIn(claimed, self.ledger.read_text())

    def test_a_worktree_cut_at_a_claimed_path_is_left_alone(self):
        path, ledger, sweep, info, default = self.claimable("feat-u2")
        reason, moved = self.claim(ledger, sweep, info, default)
        self.assertIsNone(reason)
        # A new worktree at the old path, with an open dispatch and an unpushed commit.
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", "feat-u3", str(path), "origin/main")
        (path / "new.txt").write_text("new\n")
        self.git(path, "add", "new.txt")
        self.git(path, "commit", "-q", "-m", "New")
        self.dispatch(path, finish=False)
        out = self.ledger_run("clean-worktrees")
        self.assertFalse(Path(moved).exists(), out.stderr)  # the run that stopped is finished
        self.assertTrue((path / "new.txt").exists())
        self.assertIn("1 removed", out.stderr)

    def test_a_head_moved_after_the_claim_is_put_back(self):
        path = self.worktree("feat-hm")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            done = real(checkout, *args, **kwargs)
            if args[:2] == ("worktree", "move") and done.returncode == 0:
                moved = Path(args[-1])
                (moved / "late.txt").write_text("late\n")
                self.git(moved, "add", "late.txt")
                self.git(moved, "commit", "-q", "-m", "Late")
            return done

        with mock.patch.object(sweep, "git", git):
            lines, _ = ledger.clean_worktrees(str(self.main))
        self.assertTrue((path / "late.txt").exists(), lines)
        self.assertEqual(self.retiring(), [])
        self.assertTrue(any("its HEAD moved" in line for line in lines), lines)

    def test_a_run_that_stopped_after_the_rename_is_finished(self):
        path = self.worktree("feat-rs")
        self.dispatch(path)
        self.git(self.main, "worktree", "move", str(path), str(path.parent / ".fnl-retiring-0123456789ab"))
        out = self.ledger_run("clean-worktrees")
        self.assertEqual(self.retiring(), [], out.stderr)
        self.assertIn("1 removed", out.stderr)

    def test_a_hand_run_waits_for_a_running_cleanup(self):
        ledger, _ = self.load_ledger()
        args = ledger.build_parser().parse_args(["clean-worktrees"])
        with mock.patch.object(ledger, "CLEAN_LOCK_WAIT", 0.2), ledger.cleaner_lock(0) as held:
            self.assertTrue(held)
            import contextlib
            import io
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
                args.func(args)
        self.assertEqual(stop.exception.code, 1)
        self.assertIn("another worktree cleanup is running", err.getvalue())

    # -- failures

    def test_a_busy_ledger_is_a_failure(self):
        path = self.worktree("feat-u")
        self.dispatch(path)
        ledger, _ = self.load_ledger()

        def busy():
            raise SystemExit("ledger: another finish is still writing; nothing recorded, retry")

        with mock.patch.object(ledger, "finish_lock", busy):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertTrue(path.exists())
        self.assertTrue(any("the ledger stayed busy" in line for line in lines), lines)

    def test_a_branch_deletion_error_keeps_the_removal_report(self):
        path = self.worktree("feat-o")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:1] == ("branch",):
                raise subprocess.TimeoutExpired("git", 60)
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertFalse(path.exists())
        self.assertTrue(any(line.startswith("ledger: removed worktree") for line in lines), lines)
        self.assertTrue(any("branch deletion failed" in line for line in lines), lines)

    def test_a_refused_removal_puts_the_worktree_back(self):
        path = self.worktree("feat-v")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(args, 1, "", "")
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, _ = ledger.clean_worktrees(str(self.main))
        self.assertTrue(path.exists())
        self.assertTrue(any("git refused the removal" in line for line in lines), lines)
        self.assertEqual(self.retiring(), [])
        self.ledger_run(*START, "--checkout", str(path))  # the checkout is usable again

    def test_a_removal_error_puts_the_worktree_back(self):
        path = self.worktree("feat-z")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "remove"):
                raise subprocess.TimeoutExpired("git", 60)
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertTrue(path.exists())
        self.assertEqual(self.retiring(), [])

    def test_a_live_lease_skips_the_cleanup(self):
        path = self.worktree("feat-w")
        self.dispatch(path)
        ledger, _ = self.load_ledger()
        with mock.patch("away_lease.live_lease", return_value={"id": "x"}):
            lines, _ = ledger.clean_worktrees(str(self.main))
        self.assertTrue(path.exists())
        self.assertEqual(len(lines), 1)
        self.assertIn("away lease", lines[0])

    # -- source rules

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
