"""worktree_sweep.py lists linked worktrees and removes only the safe ones.

Every repository here is a temporary one; the real checkout is never touched.
"""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "skills/commit-messages/scripts/worktree_sweep.py"
# The stub answers `--head <branch>` with the JSON a test wrote to <branch>.json beside it, else no pull request.
GH_STUB = """#!/bin/sh
dir=$(dirname "$0")
while [ $# -gt 0 ]; do
  if [ "$1" = "--head" ]; then
    if [ -f "$dir/$2.json" ]; then cat "$dir/$2.json"; else echo '[]'; fi
    exit 0
  fi
  shift
done
echo '[]'
"""


class SweepTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name).resolve()
        self.home = account(self, self.base / "home")
        self.ledger = self.home / ".finolabs/vibecode/ledger.jsonl"
        self.ledger.parent.mkdir(parents=True)
        # Only git and, when a test asks, a stub gh are reachable: never a real gh, never the network.
        tools = self.base / "tools"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        self.stub = self.base / "stub"
        self.stub.mkdir()
        (self.stub / "gh").write_text(GH_STUB)
        (self.stub / "gh").chmod(0o755)
        self.path_without_gh = os.pathsep.join([str(tools), "/usr/bin", "/bin"])
        if shutil.which("gh", path=self.path_without_gh):
            self.skipTest("a gh on the system path would reach the network")
        self.git_env = {"PATH": self.path_without_gh, "HOME": str(self.home), "GIT_CONFIG_NOSYSTEM": "1",
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
                              env=self.git_env)

    def worktree(self, name, *, push=True, merge=False, gone=False, parent=None):
        path = (parent or self.main / ".wt") / name
        self.git(self.main, "worktree", "add", "-q", "--no-track", "-b", name, str(path), "origin/main")
        (path / f"{name}.txt").write_text(name + "\n")
        self.git(path, "add", f"{name}.txt")
        self.git(path, "commit", "-q", "-m", "Add " + name)
        if push:
            self.git(path, "push", "-q", "-u", "origin", name)
        if merge:
            self.git(self.main, "merge", "-q", "--no-ff", "-m", "Merge " + name, name)
            self.git(self.main, "push", "-q", "origin", "main")
        if gone:
            self.git(self.main, "push", "-q", "origin", "--delete", name)
        self.git(self.main, "fetch", "-q", "--prune", "origin")
        return path

    def head(self, path):
        return self.git(path, "rev-parse", "HEAD").stdout.strip()

    def forge_merged(self, branch, head):
        """The stub gh reports one merged pull request for this branch, whose head was this commit."""
        (self.stub / f"{branch}.json").write_text(json.dumps([{"number": 7, "headRefOid": head}]))

    def ignore(self, pattern):
        exclude = self.main / ".git/info/exclude"
        exclude.parent.mkdir(exist_ok=True)
        with exclude.open("a") as stream:
            stream.write(pattern + "\n")

    def sweep(self, *args, gh=True, cwd=None):
        env = {"PATH": os.pathsep.join([str(self.stub), self.path_without_gh]) if gh else self.path_without_gh,
               "HOME": str(self.home)}
        return subprocess.run([sys.executable, "-I", str(SWEEP), *args], capture_output=True, text=True,
                              cwd=str(cwd or self.main), env=env)

    def line(self, output, name):
        found = [line for line in output.splitlines() if (".wt/" + name) in line]
        self.assertEqual(len(found), 1, output)
        return found[0]

    def at(self, output, rel):
        """The one line about the worktree at this path relative to the main checkout."""
        found = [l for l in output.splitlines() if rel in l.split()[:2]]
        self.assertEqual(len(found), 1, output)
        return found[0]

    def dispatch(self, ident, path, finished):
        checkout = hashlib.sha256(os.fsencode(Path(path).resolve())).hexdigest()
        lines = [{"event": "start", "id": ident, "ts": "2026-11-12T00:00:00+00:00", "project": "demo", "task": "t1",
                  "kind": "implement", "grade": "easy", "agent": "codex", "model": "m", "reason": "routing",
                  "checkout_id": checkout}]
        if finished:
            lines.append({"event": "finish", "id": ident, "ts": "2026-11-12T01:00:00+00:00", "outcome": "accepted",
                          "rework_rounds": 0})
        with self.ledger.open("a") as stream:
            for record in lines:
                stream.write(json.dumps(record) + "\n")

    def test_list_reports_each_linked_worktree_and_never_the_main_checkout(self):
        self.worktree("feat-merged", merge=True)
        dirty = self.worktree("feat-dirty", merge=True)
        (dirty / "scratch.txt").write_text("untracked\n")
        self.worktree("feat-open")
        self.worktree("feat-local", push=False)
        squash = self.worktree("feat-squash")
        self.forge_merged("feat-squash", self.head(squash))
        result = self.sweep("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        merged = self.line(result.stdout, "feat-merged")
        self.assertIn("branch=feat-merged", merged)
        self.assertRegex(merged, r"size=\d")
        for word in ("clean", "unpushed=0", "merged=yes"):
            self.assertIn(word, merged)
        self.assertIn("dirty", self.line(result.stdout, "feat-dirty"))
        self.assertIn("merged=no", self.line(result.stdout, "feat-open"))
        local = self.line(result.stdout, "feat-local")
        self.assertIn("unpushed=1", local)
        self.assertIn("no upstream", local)
        self.assertIn("merged=yes", self.line(result.stdout, "feat-squash"))  # gh reports its pull request merged
        self.assertEqual(len([l for l in result.stdout.splitlines() if "branch=" in l]), 5)

    def test_list_without_gh_reports_unknown_for_a_branch_not_on_the_default_branch(self):
        self.worktree("feat-open")
        self.worktree("feat-merged", merge=True)
        result = self.sweep(gh=False)  # list is the default
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("merged=unknown", self.line(result.stdout, "feat-open"))
        self.assertIn("merged=yes", self.line(result.stdout, "feat-merged"))

    def test_list_outside_a_repository_exits_zero(self):
        outside = self.base / "plain"
        outside.mkdir()
        result = self.sweep("list", cwd=outside)
        self.assertEqual(result.returncode, 0)

    def test_remove_by_path_removes_only_the_safe_worktree_and_its_branch(self):
        merged = self.worktree("feat-merged", merge=True)
        dirty = self.worktree("feat-dirty", merge=True)
        (dirty / "scratch.txt").write_text("untracked\n")
        unmerged = self.worktree("feat-open")
        local = self.worktree("feat-local", push=False)
        result = self.sweep("--remove", "--path", str(merged), "--path", str(dirty), "--path", str(unmerged),
                            "--path", str(local))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(merged.exists())
        self.assertNotIn("feat-merged", self.git(self.main, "branch", "--list").stdout)
        self.assertTrue(self.line(result.stdout, "feat-merged").startswith("removed"))
        for path, reason in ((dirty, "dirty"), (unmerged, "not merged"), (local, "unpushed")):
            self.assertTrue(path.exists())
            kept = self.line(result.stdout, path.name)
            self.assertTrue(kept.startswith("kept"), kept)
            self.assertIn(reason, kept)
        self.assertTrue((dirty / "scratch.txt").exists())

    def test_remove_keeps_unknown_merge_state_without_gh(self):
        unmerged = self.worktree("feat-open")
        result = self.sweep("--remove", "--path", str(unmerged), gh=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(unmerged.exists())
        self.assertIn("unknown", self.line(result.stdout, "feat-open"))

    def test_remove_accepts_a_branch_whose_upstream_was_deleted_after_merge(self):
        gone = self.worktree("feat-gone", merge=True, gone=True)
        result = self.sweep("--remove", "--path", str(gone))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(gone.exists(), result.stdout)

    def test_remove_accepts_a_pull_request_merged_on_the_forge(self):
        squash = self.worktree("feat-squash")
        self.forge_merged("feat-squash", self.head(squash))
        result = self.sweep("--remove", "--path", str(squash))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(squash.exists(), result.stdout)

    def test_a_forge_merge_counts_only_at_the_branch_current_head(self):
        reused = self.worktree("feat-squash")
        self.forge_merged("feat-squash", self.head(reused))
        (reused / "later.txt").write_text("later\n")
        self.git(reused, "add", "later.txt")
        self.git(reused, "commit", "-q", "-m", "Add a later change")
        self.git(reused, "push", "-q")
        self.assertIn("merged=unknown", self.line(self.sweep("list").stdout, "feat-squash"))
        result = self.sweep("--remove", "--path", str(reused))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(reused.exists(), result.stdout)
        self.assertIn("merge state unknown", self.line(result.stdout, "feat-squash"))
        self.assertIn("feat-squash", self.git(self.main, "branch", "--list").stdout)

    def test_a_squash_merged_branch_with_a_deleted_upstream_is_not_unpushed(self):
        squash = self.worktree("feat-sq")
        self.git(self.main, "merge", "-q", "--squash", "origin/feat-sq")
        self.git(self.main, "commit", "-q", "-m", "Squash feat-sq")
        self.git(self.main, "push", "-q", "origin", "main")
        self.git(self.main, "push", "-q", "origin", "--delete", "feat-sq")
        self.git(self.main, "fetch", "-q", "--prune", "origin")
        self.forge_merged("feat-sq", "0" * 40)  # another head proves nothing
        self.assertIn("unpushed=1", self.line(self.sweep("list").stdout, "feat-sq"))
        self.forge_merged("feat-sq", self.head(squash))
        listed = self.line(self.sweep("list").stdout, "feat-sq")
        self.assertIn("unpushed=0", listed)
        self.assertIn("merged=yes", listed)
        result = self.sweep("--remove", "--path", str(squash))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(squash.exists(), result.stdout)

    def test_remove_refuses_a_worktree_whose_path_or_a_parent_is_a_symlink(self):
        self.ignore("private-draft.txt")
        direct = self.worktree("feat-link", merge=True)
        holder = self.main / "holder"
        holder.mkdir()
        via_parent = self.worktree("feat-plink", merge=True, parent=holder)
        for tree in (direct, via_parent):
            (tree / "private-draft.txt").write_text("draft\n")
        outside = self.base / "outside"
        direct.rename(outside)
        direct.symlink_to(outside)
        moved = self.base / "moved-holder"
        holder.rename(moved)
        holder.symlink_to(moved)
        result = self.sweep("--remove", "--path", str(direct), "--path", str(via_parent))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((outside / "private-draft.txt").exists(), result.stdout)
        self.assertTrue((moved / "feat-plink/private-draft.txt").exists(), result.stdout)
        for rel in (".wt/feat-link", "holder/feat-plink"):
            kept = self.at(result.stdout, rel)
            self.assertTrue(kept.startswith("kept"), kept)
            self.assertIn("symlink", kept)
        self.assertIn("symlink", self.at(self.sweep("list").stdout, ".wt/feat-link"))

    def test_remove_never_takes_a_worktree_that_holds_or_lies_inside_another(self):
        self.ignore("nested/")
        parent = self.worktree("feat-parent", merge=True)
        child = parent / "nested/child"
        self.git(self.main, "worktree", "add", "-q", "-b", "feat-child", str(child), "origin/main")
        self.git(self.main, "worktree", "lock", str(child))
        (child / "uncommitted.txt").write_text("draft\n")
        self.dispatch("d5", child, finished=False)
        inner = self.worktree("feat-inner", merge=True, parent=parent / "nested")
        result = self.sweep("--remove", "--path", str(parent), "--path", str(inner))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((child / "uncommitted.txt").exists(), result.stdout)
        self.assertTrue(parent.exists() and inner.exists(), result.stdout)
        self.assertIn("holds another worktree", self.at(result.stdout, ".wt/feat-parent"))
        self.assertIn("inside another worktree", self.at(result.stdout, ".wt/feat-parent/nested/feat-inner"))

    def test_remove_without_path_takes_only_finished_ledger_checkouts(self):
        finished = self.worktree("feat-finished", merge=True)
        running = self.worktree("feat-running", merge=True)
        other = self.worktree("feat-other", merge=True)
        self.dispatch("d1", finished, finished=True)
        self.dispatch("d2", running, finished=True)
        self.dispatch("d3", running, finished=False)
        result = self.sweep("--remove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(finished.exists(), result.stdout)
        self.assertTrue(running.exists())
        self.assertIn("open dispatch", self.line(result.stdout, "feat-running"))
        self.assertTrue(other.exists())
        self.assertIn("not named", self.line(result.stdout, "feat-other"))

    def test_remove_never_takes_a_named_worktree_with_an_open_dispatch(self):
        running = self.worktree("feat-running", merge=True)
        self.dispatch("d4", running, finished=False)
        result = self.sweep("--remove", "--path", str(running))
        self.assertTrue(running.exists())
        self.assertIn("open dispatch", self.line(result.stdout, "feat-running"))

    def test_remove_never_takes_the_working_directory_or_a_parent_of_it(self):
        merged = self.worktree("feat-merged", merge=True)
        inner = merged / "sub"
        inner.mkdir()
        (inner / "keep.txt").write_text("x\n")
        self.git(merged, "add", "sub/keep.txt")
        self.git(merged, "commit", "-q", "-m", "Add sub")
        self.git(merged, "push", "-q")
        self.git(self.main, "merge", "-q", "--no-ff", "-m", "Merge again", "feat-merged")
        self.git(self.main, "push", "-q", "origin", "main")
        self.git(self.main, "fetch", "-q", "origin")
        for cwd in (merged, inner):
            result = self.sweep("--remove", "--path", str(merged), cwd=cwd)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(merged.exists())
            self.assertIn("working directory", self.line(result.stdout, "feat-merged"))

    def test_remove_keeps_a_locked_worktree_and_refuses_the_main_checkout(self):
        locked = self.worktree("feat-locked", merge=True)
        self.git(self.main, "worktree", "lock", str(locked))
        result = self.sweep("--remove", "--path", str(locked), "--path", str(self.main))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(locked.exists())
        self.assertIn("locked", self.line(result.stdout, "feat-locked"))
        self.assertTrue((self.main / "README.md").exists())
        self.assertIn("main checkout", result.stdout)

    def test_remove_outside_a_repository_is_its_own_error(self):
        outside = self.base / "plain"
        outside.mkdir()
        self.assertNotEqual(self.sweep("--remove", cwd=outside).returncode, 0)

    def test_the_script_never_forces_and_runs_no_shell(self):
        tree = ast.parse(SWEEP.read_text())
        strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        for word in ("--force", "-f", "-D", "-ff"):
            self.assertNotIn(word, strings)
        self.assertNotIn("shell=True", SWEEP.read_text())

    def test_review_gate_copy_matches(self):
        copy = ROOT / "skills/review-gate/scripts/worktree_sweep.py"
        self.assertEqual(copy.read_bytes(), SWEEP.read_bytes())


if __name__ == "__main__":
    unittest.main()
