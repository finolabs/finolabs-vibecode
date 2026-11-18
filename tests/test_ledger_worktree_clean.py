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
import time
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

    def stopped_after_rename(self, name):
        """A worktree a cleanup renamed (claim record written) before it stopped."""
        path = self.worktree(name)
        self.dispatch(path)
        moved = path.parent / ".fnl-retiring-0123456789ab"
        ledger, _ = self.load_ledger()
        ledger.write_claim(str(moved), ledger.checkout_instance(str(path)))  # a rename keeps the instance
        self.git(self.main, "worktree", "move", str(path), str(moved))
        return moved

    def test_a_run_that_stopped_after_the_rename_is_finished(self):
        self.stopped_after_rename("feat-rs")
        out = self.ledger_run("clean-worktrees")
        self.assertEqual(self.retiring(), [], out.stderr)
        self.assertIn("1 removed", out.stderr)

    def test_a_retiring_name_without_a_claim_record_stays(self):
        path = self.worktree("feat-nc")
        self.dispatch(path)
        moved = path.parent / ".fnl-retiring-feedfacecafe"
        self.git(self.main, "worktree", "move", str(path), str(moved))
        out = self.ledger_run("clean-worktrees")
        self.assertTrue(moved.exists(), out.stderr)
        self.assertIn("0 removed", out.stderr)

    def test_start_refuses_a_renamed_checkout(self):
        # A process already inside a claimed worktree cannot open a dispatch there after the rename.
        moved = self.stopped_after_rename("feat-od")
        (moved / "sub").mkdir()
        out = self.ledger_run(*START, "--checkout", str(moved / "sub"), code=1)
        self.assertIn("being removed", out.stderr)

    def test_a_stale_claim_never_authorizes_a_replacement(self):
        moved = self.stopped_after_rename("feat-sc")
        self.git(self.main, "worktree", "remove", str(moved))
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", "feat-sc2", str(moved), "origin/main")
        out = self.ledger_run("clean-worktrees")
        self.assertTrue(moved.exists(), out.stderr)
        self.assertIn("0 removed", out.stderr)

    def test_an_immediate_replacement_is_not_owned(self):
        path = self.worktree("feat-ir")
        self.dispatch(path)
        self.git(self.main, "worktree", "remove", str(path))
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", "feat-ir2", str(path), "origin/main")
        out = self.ledger_run("clean-worktrees")
        self.assertTrue(path.exists(), out.stderr)
        self.assertIn("0 removed", out.stderr)

    def test_a_failed_move_that_cannot_go_back_is_a_failure_and_stays_claimed(self):
        path = self.worktree("feat-fo")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-1]:
                os.rename(args[-2], args[-1])
                os.mkdir(args[-2])  # someone took the old path meanwhile
                raise subprocess.TimeoutExpired("git", 60)
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        stranded = self.retiring()
        self.assertEqual(len(stranded), 1, lines)
        self.assertTrue(any("stays at" in line for line in lines), lines)
        self.assertIsNotNone(ledger.has_claim(str(stranded[0])))
        out = self.ledger_run("clean-worktrees")  # a later run finds it at its registered retiring path
        self.assertEqual(self.retiring(), [], out.stderr)
        self.assertIn("1 removed", out.stderr)

    def test_a_replacement_after_the_claim_is_left_alone(self):
        path = self.worktree("feat-ra")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real_claim = ledger.claim

        def claim(*args, **kwargs):
            reason, moved = real_claim(*args, **kwargs)
            if moved:  # the claimed worktree is replaced by another one on the same branch and head
                self.git(self.main, "worktree", "remove", moved)
                self.git(self.main, "worktree", "add", "-q", moved, "feat-ra")
            return reason, moved

        with mock.patch.object(ledger, "claim", claim):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertEqual(len(self.retiring()), 1, lines)
        self.assertTrue(any("not the one claimed" in line for line in lines), lines)

    def test_a_replacement_during_the_size_walk_is_left_alone(self):
        path = self.worktree("feat-sw")
        self.dispatch(path)
        other = self.worktree("feat-sw2", merge=False)
        (other / "extra.txt").write_text("unpushed\n")
        self.git(other, "add", "extra.txt")
        self.git(other, "commit", "-q", "-m", "Unpushed")
        ledger, sweep = self.load_ledger()
        real_size = sweep.size_on_disk
        swapped = []

        def size_on_disk(target):
            if ".fnl-retiring-" in str(target) and not swapped:
                swapped.append(target)  # the claimed worktree leaves and another one takes its retiring path
                self.git(self.main, "worktree", "remove", str(target))
                self.git(self.main, "worktree", "move", str(other), str(target))
            return real_size(target)

        with mock.patch.object(sweep, "size_on_disk", size_on_disk):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertTrue((Path(swapped[0]) / "extra.txt").exists(), lines)
        self.assertTrue(any("not the one claimed" in line for line in lines), lines)

    def test_a_stranded_worktree_keeps_its_claim_and_is_finished_later(self):
        path = self.worktree("feat-st")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "remove"):
                path.mkdir(exist_ok=True)  # the old path is taken meanwhile, so it cannot go back
                return subprocess.CompletedProcess(args, 1, "", "")
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        stranded = self.retiring()
        self.assertEqual(len(stranded), 1, lines)
        self.assertIsNotNone(ledger.has_claim(str(stranded[0])))
        out = self.ledger_run("clean-worktrees")
        self.assertEqual(self.retiring(), [], out.stderr)
        self.assertIn("1 removed", out.stderr)

    def test_a_swap_right_after_the_claim_check_is_left_alone(self):
        moved = self.stopped_after_rename("feat-rc")
        ledger, _ = self.load_ledger()
        real_has_claim = ledger.has_claim
        calls = []

        def has_claim(target):
            found = real_has_claim(target)
            calls.append(target)
            if found and len(calls) == 2:  # in the claim: swapped for another instance, same branch and head
                self.git(self.main, "worktree", "remove", str(moved))
                self.git(self.main, "worktree", "add", "-q", str(moved), "feat-rc")
            return found

        with mock.patch.object(ledger, "has_claim", has_claim):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertTrue(moved.exists(), lines)
        self.assertTrue(any("not the one claimed" in line for line in lines), lines)

    def test_a_swap_during_a_failed_recheck_is_never_moved(self):
        path = self.worktree("feat-fr")
        self.dispatch(path)
        other = self.worktree("feat-fr2", merge=False)
        ledger, _ = self.load_ledger()
        real_unchanged = ledger.unchanged

        def unchanged(sweep, info, target, *args):
            if ".fnl-retiring-" in str(target):  # the claimed worktree leaves; another one is swapped in
                self.git(self.main, "worktree", "remove", str(target))
                self.git(self.main, "worktree", "move", str(other), str(target))
                return "dirty"
            return real_unchanged(sweep, info, target, *args)

        with mock.patch.object(ledger, "unchanged", unchanged):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertFalse(path.exists(), lines)  # the swapped-in worktree was not moved to the old path
        self.assertEqual(len(self.retiring()), 1, lines)

    def test_a_failed_move_never_moves_a_folder_swapped_in(self):
        path = self.worktree("feat-sm")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git
        aside = []

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-1]:
                os.rename(args[-2], args[-1])
                aside.append(args[-1] + "-aside")
                os.rename(args[-1], aside[0])  # the renamed folder leaves; something else takes its place
                os.mkdir(args[-1])
                raise subprocess.TimeoutExpired("git", 60)
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)
        self.assertFalse(path.exists(), lines)  # the folder swapped in was not moved to the old path
        self.assertTrue(Path(aside[0][:-len("-aside")]).is_dir(), lines)
        self.assertTrue(any("stays at" in line for line in lines), lines)

    def test_a_worktree_registered_inside_after_inspection_keeps_both(self):
        path = self.worktree("feat-nw")
        self.dispatch(path)
        common = Path(self.git(self.main, "rev-parse", "--git-common-dir").stdout.strip())
        common = common if common.is_absolute() else self.main / common
        (common / "info").mkdir(exist_ok=True)
        with (common / "info" / "exclude").open("a") as handle:
            handle.write("nested/\n")  # ignored, so the outer worktree stays clean
        ledger, sweep = self.load_ledger()
        real_size = sweep.size_on_disk
        nested = []

        def size_on_disk(target):
            if ".fnl-retiring-" in str(target) and not nested:
                nested.append(Path(target) / "nested")
                self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", "feat-nw2", str(nested[0]),
                         "origin/main")
            return real_size(target)

        with mock.patch.object(sweep, "size_on_disk", size_on_disk):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue((path / "nested" / "README.md").exists(), lines)  # moved back with the outer worktree
        self.assertTrue(any("holds another" in line for line in lines), lines)
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertIn("worktree " + str((path / "nested").resolve()) + "\n", listed)  # recorded where it is
        out = self.ledger_run("clean-worktrees")  # a later run still sees the nesting
        self.assertTrue((path / "nested" / "README.md").exists(), out.stderr)
        self.assertIn("holds another", out.stderr)

    def test_a_commit_during_the_size_walk_is_put_back(self):
        path = self.worktree("feat-cw")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real_size = sweep.size_on_disk

        def size_on_disk(target):
            if ".fnl-retiring-" in str(target):
                (Path(target) / "late.txt").write_text("late\n")
                self.git(target, "add", "late.txt")
                self.git(target, "commit", "-q", "-m", "Late")
            return real_size(target)

        with mock.patch.object(sweep, "size_on_disk", size_on_disk):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue((path / "late.txt").exists(), lines)
        self.assertTrue(any("its HEAD moved" in line for line in lines), lines)

    def test_a_reverse_move_that_fails_half_way_is_repaired(self):
        path = self.worktree("feat-rh")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(args, 1, "", "")
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-2]:
                os.rename(args[-2], args[-1])  # renamed back, then git failed before recording it
                raise subprocess.TimeoutExpired("git", 60)
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(path.exists(), lines)
        self.assertEqual(self.retiring(), [])
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertIn("worktree " + str(path.resolve()) + "\n", listed)  # git records it at its old path again
        self.assertNotIn(".fnl-retiring-", listed)

    def test_a_half_done_move_back_records_a_nested_worktree_too(self):
        path = self.worktree("feat-hn")
        self.dispatch(path)
        common = Path(self.git(self.main, "rev-parse", "--git-common-dir").stdout.strip())
        common = common if common.is_absolute() else self.main / common
        (common / "info").mkdir(exist_ok=True)
        with (common / "info" / "exclude").open("a") as handle:
            handle.write("nested/\n")
        ledger, sweep = self.load_ledger()
        real_size, real_git = sweep.size_on_disk, sweep.git
        added = []

        def size_on_disk(target):
            if ".fnl-retiring-" in str(target) and not added:
                added.append(True)
                real_git(str(self.main), "worktree", "add", "-q", "--no-track", "-b", "feat-hn2",
                         str(Path(target) / "nested"), "origin/main")
            return real_size(target)

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-2]:
                os.rename(args[-2], args[-1])  # renamed back, then git failed before recording it
                raise subprocess.TimeoutExpired("git", 60)
            return real_git(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "size_on_disk", size_on_disk), mock.patch.object(sweep, "git", git):
            lines, _ = ledger.clean_worktrees(str(self.main))
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertIn("worktree " + str((path / "nested").resolve()) + "\n", listed, lines)
        self.assertNotIn(".fnl-retiring-", listed)

    def test_an_undone_first_move_records_a_nested_worktree_too(self):
        path = self.worktree("feat-un")
        self.dispatch(path)
        common = Path(self.git(self.main, "rev-parse", "--git-common-dir").stdout.strip())
        common = common if common.is_absolute() else self.main / common
        (common / "info").mkdir(exist_ok=True)
        with (common / "info" / "exclude").open("a") as handle:
            handle.write("nested/\n")
        ledger, sweep = self.load_ledger()
        real_git = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-1]:
                os.rename(args[-2], args[-1])  # renamed, then stalled; meanwhile a worktree appears inside
                real_git(str(self.main), "worktree", "repair", "--", args[-1])
                real_git(str(self.main), "worktree", "add", "-q", "--no-track", "-b", "feat-un2",
                         str(Path(args[-1]) / "nested"), "origin/main")
                raise subprocess.TimeoutExpired("git", 60)
            return real_git(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, _ = ledger.clean_worktrees(str(self.main))
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertIn("worktree " + str((path / "nested").resolve()) + "\n", listed, lines)
        self.assertNotIn(".fnl-retiring-", listed)

    def test_a_worktree_registered_inside_just_before_the_rename_keeps_both(self):
        path = self.worktree("feat-bm")
        self.dispatch(path)
        common = Path(self.git(self.main, "rev-parse", "--git-common-dir").stdout.strip())
        common = common if common.is_absolute() else self.main / common
        (common / "info").mkdir(exist_ok=True)
        with (common / "info" / "exclude").open("a") as handle:
            handle.write("nested/\n")
        ledger, sweep = self.load_ledger()
        real_git = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-1] and \
                    not (Path(args[-2]) / "nested").exists():
                real_git(str(self.main), "worktree", "add", "-q", "--no-track", "-b", "feat-bm2",
                         str(Path(args[-2]) / "nested"), "origin/main")
                (Path(args[-2]) / "nested" / "unsaved.txt").write_text("work\n")
            return real_git(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue((path / "nested" / "unsaved.txt").exists(), lines)
        self.assertTrue(any("holds another" in line for line in lines), lines)
        listed = self.git(self.main, "worktree", "list", "--porcelain").stdout
        self.assertIn("worktree " + str((path / "nested").resolve()) + "\n", listed)
        self.assertNotIn(".fnl-retiring-", listed)

    def ignore_nested(self):
        common = Path(self.git(self.main, "rev-parse", "--git-common-dir").stdout.strip())
        common = common if common.is_absolute() else self.main / common
        (common / "info").mkdir(exist_ok=True)
        with (common / "info" / "exclude").open("a") as handle:
            handle.write("nested/\n")

    def add_nested(self, real_git, folder, branch):
        real_git(str(self.main), "worktree", "add", "-q", "--no-track", "-b", branch, str(Path(folder) / "nested"),
                 "origin/main")
        (Path(folder) / "nested" / "unsaved.txt").write_text("work\n")

    def test_a_stranded_first_move_keeps_a_nested_worktree_safe(self):
        path = self.worktree("feat-sn")
        self.dispatch(path)
        self.ignore_nested()
        ledger, sweep = self.load_ledger()
        real_git = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-1]:
                self.add_nested(real_git, args[-2], "feat-sn2")
                os.rename(args[-2], args[-1])
                os.mkdir(args[-2])  # the old path is taken, so it stays at its retiring path
                raise subprocess.TimeoutExpired("git", 60)
            return real_git(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            ledger.clean_worktrees(str(self.main))
        stranded = self.retiring()
        out = self.ledger_run("clean-worktrees")  # the next run resumes the claim
        self.assertTrue((stranded[0] / "nested" / "unsaved.txt").exists(), out.stderr)
        self.assertIn("holds another", out.stderr)

    def test_a_worktree_registered_during_the_move_back_stays_visible(self):
        path = self.worktree("feat-mb")
        self.dispatch(path)
        self.ignore_nested()
        ledger, sweep = self.load_ledger()
        real_git = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "remove"):
                return subprocess.CompletedProcess(args, 1, "", "")
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-2]:
                self.add_nested(real_git, args[-2], "feat-mb2")  # registered just before the move back
            return real_git(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            ledger.clean_worktrees(str(self.main))
        out = self.ledger_run("clean-worktrees")
        self.assertTrue((path / "nested" / "unsaved.txt").exists(), out.stderr)
        self.assertIn("holds another", out.stderr)

    def test_a_checkout_inside_that_git_does_not_list_still_stops_the_removal(self):
        path = self.worktree("feat-ul")
        self.dispatch(path)
        self.ignore_nested()
        self.git(path, "init", "-q", str(path / "nested"))  # no worktree record names it
        (path / "nested" / "unsaved.txt").write_text("work\n")
        out = self.ledger_run("clean-worktrees", code=None)
        self.assertTrue((path / "nested" / "unsaved.txt").exists(), out.stderr)
        self.assertIn("holds another checkout", out.stderr)

    def test_a_failed_nested_repair_does_not_expose_the_next_run(self):
        path = self.worktree("feat-fn")
        self.dispatch(path)
        self.ignore_nested()
        ledger, sweep = self.load_ledger()
        real_size, real_git = sweep.size_on_disk, sweep.git
        added = []

        def size_on_disk(target):
            if ".fnl-retiring-" in str(target) and not added:
                added.append(True)
                self.add_nested(real_git, target, "feat-fn2")
            return real_size(target)

        real_follow = ledger.follow

        def follow(sweep_module, main, old, new):
            if ".fnl-retiring-" in str(old):
                return False  # the move back cannot record the nested worktree at its new place
            return real_follow(sweep_module, main, old, new)

        with mock.patch.object(sweep, "size_on_disk", size_on_disk), mock.patch.object(ledger, "follow", follow):
            ledger.clean_worktrees(str(self.main))
        self.assertTrue((path / "nested" / "unsaved.txt").exists())
        out = self.ledger_run("clean-worktrees", code=None)  # git's record of the nested one is stale now
        self.assertTrue((path / "nested" / "unsaved.txt").exists(), out.stderr)
        self.assertIn("holds another checkout", out.stderr)

    def test_a_checkout_spelled_dot_git_in_capitals_stops_the_removal(self):
        probe = self.base / "CaseProbe2"
        probe.mkdir()
        if not (self.base / "caseprobe2").exists():
            self.skipTest("case-sensitive file system")
        path = self.worktree("feat-gc")
        self.dispatch(path)
        self.ignore_nested()
        self.git(path, "init", "-q", str(path / "nested"))
        os.rename(path / "nested" / ".git", path / "nested" / ".GIT")
        (path / "nested" / "unsaved.txt").write_text("work\n")
        out = self.ledger_run("clean-worktrees", code=None)
        self.assertTrue((path / "nested" / "unsaved.txt").exists(), out.stderr)
        self.assertIn("holds another checkout", out.stderr)

    def test_recording_moved_worktrees_holds_no_lock_and_an_error_goes_back(self):
        path = self.worktree("feat-lk")
        self.dispatch(path)
        ledger, _ = self.load_ledger()
        seen = []

        def follow(*args):
            with mock.patch.object(ledger, "LOCK_WAIT", 0):
                try:
                    with ledger.finish_lock():
                        seen.append("free")
                except SystemExit:
                    seen.append("held")
            raise subprocess.TimeoutExpired("git", 60)  # the lookup stalls and fails

        with mock.patch.object(ledger, "follow", follow):
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertEqual(seen[:1], ["free"])
        self.assertTrue(path.exists(), lines)
        self.assertEqual(self.retiring(), [])

    def test_a_failed_move_is_undone(self):
        path = self.worktree("feat-fm")
        self.dispatch(path)
        ledger, sweep = self.load_ledger()
        real = sweep.git

        def git(checkout, *args, **kwargs):
            if args[:2] == ("worktree", "move") and ".fnl-retiring-" in args[-1]:
                os.rename(args[-2], args[-1])  # the folder moved, then git failed
                raise subprocess.TimeoutExpired("git", 60)
            return real(checkout, *args, **kwargs)

        with mock.patch.object(sweep, "git", git):
            lines, _ = ledger.clean_worktrees(str(self.main))
        self.assertTrue(path.exists(), lines)
        self.assertEqual(self.retiring(), [])
        self.assertTrue(any("git refused to move it" in line for line in lines), lines)

    def test_a_replacement_at_a_finished_path_is_not_owned(self):
        path = self.worktree("feat-rp")
        self.dispatch(path)
        self.git(self.main, "worktree", "remove", str(path))
        time.sleep(2.1)  # the replacement is registered well after the finished dispatch started
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", "feat-rp2", str(path), "origin/main")
        out = self.ledger_run("clean-worktrees")
        self.assertTrue(path.exists(), out.stderr)
        self.assertIn("0 removed", out.stderr)

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
            lines, failed = ledger.clean_worktrees(str(self.main))
        self.assertTrue(failed)  # a hand run exits 1
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
