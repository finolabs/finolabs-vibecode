"""worktree_sweep.py lists linked worktrees and prints git's own removal commands for the safe ones.

It deletes nothing itself. Every repository here is a temporary one; the real checkout is never touched.
"""
import ast
import json
import os
import shlex
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
# The only git subcommands the script may run: all of them read.
READ_ONLY_GIT = {"worktree", "status", "rev-parse", "rev-list", "symbolic-ref", "merge-base"}


class SweepTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.base = Path(self.dir.name).resolve()
        self.home = account(self, self.base / "home")
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

    def git_paths(self):
        """The linked worktree paths exactly as `git worktree list --porcelain` writes them."""
        out = self.git(self.main, "worktree", "list", "--porcelain").stdout
        return [l[len("worktree "):] for l in out.splitlines() if l.startswith("worktree ")][1:]

    def sweep(self, *args, gh=True, cwd=None):
        env = {"PATH": os.pathsep.join([str(self.stub), self.path_without_gh]) if gh else self.path_without_gh,
               "HOME": str(self.home)}
        return subprocess.run([sys.executable, "-I", str(SWEEP), *args], capture_output=True, text=True,
                              cwd=str(cwd or self.main), env=env)

    def block(self, output, path):
        """The report line about the worktree git lists at this path, and the command lines under it."""
        lines = output.splitlines()
        starts = [i for i, l in enumerate(lines) if l.startswith(str(path) + "  branch=")]
        self.assertEqual(len(starts), 1, output)
        i = starts[0]
        commands = []
        for follow in lines[i + 1:]:
            if not follow.startswith("  "):
                break
            commands.append(follow.strip())
        return lines[i], commands

    def assert_not_candidate(self, output, path, reason):
        line, commands = self.block(output, path)
        self.assertIn("candidate=no", line)
        self.assertIn(reason, line)
        self.assertEqual(commands, [])

    def test_list_reports_each_linked_worktree_at_the_path_git_lists(self):
        self.worktree("feat-merged", merge=True)
        dirty = self.worktree("feat-dirty", merge=True)
        (dirty / "scratch.txt").write_text("untracked\n")
        self.worktree("feat-open")
        self.worktree("feat-local", push=False)
        squash = self.worktree("feat-squash")
        self.forge_merged("feat-squash", self.head(squash))
        result = self.sweep("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        listed = {p: self.block(result.stdout, p)[0] for p in self.git_paths()}
        self.assertEqual(len(listed), 5)
        merged = listed[str(self.main / ".wt/feat-merged")]
        self.assertIn("branch=feat-merged", merged)
        self.assertRegex(merged, r"size=\d")
        for word in ("clean", "unpushed=0", "merged=yes", "candidate=yes"):
            self.assertIn(word, merged)
        self.assertIn("dirty", listed[str(dirty)])
        self.assertIn("merged=no", listed[str(self.main / ".wt/feat-open")])
        local = listed[str(self.main / ".wt/feat-local")]
        self.assertIn("unpushed=1", local)
        self.assertIn("no upstream", local)
        self.assertIn("merged=yes", listed[str(squash)])  # gh reports its pull request merged at this head
        self.assertNotIn(str(self.main) + "  branch=", result.stdout)  # never the main checkout

    def test_list_without_gh_reports_unknown_for_a_branch_not_on_the_default_branch(self):
        opened = self.worktree("feat-open")
        merged = self.worktree("feat-merged", merge=True)
        result = self.sweep(gh=False)  # list is the default
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_not_candidate(result.stdout, opened, "merged=unknown")
        self.assertIn("merged=yes", self.block(result.stdout, merged)[0])

    def test_list_outside_a_repository_exits_zero(self):
        outside = self.base / "plain"
        outside.mkdir()
        self.assertEqual(self.sweep("list", cwd=outside).returncode, 0)

    def test_a_candidate_gets_the_two_git_commands_and_git_removes_it(self):
        self.ignore("build-output/")
        spaced = self.main / "my trees"
        merged = self.worktree("feat-merged", merge=True, parent=spaced)
        (merged / "build-output").mkdir()
        (merged / "build-output/cache.bin").write_text("ignored\n")
        result = self.sweep("list")
        line, commands = self.block(result.stdout, merged)
        self.assertIn("candidate=yes", line)
        self.assertEqual(commands, ["git worktree remove " + shlex.quote(str(merged)),
                                    "git branch -d feat-merged"])
        for command in commands:  # what the agent runs after the merge
            self.git(self.main, *shlex.split(command)[1:])
        self.assertFalse(merged.exists())  # git also removed the ignored files inside it
        self.assertNotIn("feat-merged", self.git(self.main, "branch", "--list").stdout)

    def test_only_merged_clean_fully_pushed_worktrees_are_candidates(self):
        dirty = self.worktree("feat-dirty", merge=True)
        (dirty / "scratch.txt").write_text("untracked\n")
        opened = self.worktree("feat-open")
        local = self.worktree("feat-local", push=False)
        output = self.sweep("list").stdout
        self.assert_not_candidate(output, dirty, "dirty")
        self.assert_not_candidate(output, opened, "merged=no")
        self.assert_not_candidate(output, local, "unpushed=1")
        for path in (dirty, opened, local):
            self.assertTrue(path.exists())
        self.assertTrue((dirty / "scratch.txt").exists())

    def test_a_branch_whose_upstream_was_deleted_after_merge_is_a_candidate(self):
        gone = self.worktree("feat-gone", merge=True, gone=True)
        self.assertIn("candidate=yes", self.block(self.sweep("list").stdout, gone)[0])

    def test_a_forge_merge_counts_only_at_the_branch_current_head(self):
        squash = self.worktree("feat-squash")
        self.forge_merged("feat-squash", self.head(squash))
        self.assertIn("candidate=yes", self.block(self.sweep("list").stdout, squash)[0])
        (squash / "later.txt").write_text("later\n")
        self.git(squash, "add", "later.txt")
        self.git(squash, "commit", "-q", "-m", "Add a later change")
        self.git(squash, "push", "-q")
        self.assert_not_candidate(self.sweep("list").stdout, squash, "merged=unknown")

    def test_a_squash_merged_branch_with_a_deleted_upstream_is_not_unpushed(self):
        squash = self.worktree("feat-sq")
        self.git(self.main, "merge", "-q", "--squash", "origin/feat-sq")
        self.git(self.main, "commit", "-q", "-m", "Squash feat-sq")
        self.git(self.main, "push", "-q", "origin", "main")
        self.git(self.main, "push", "-q", "origin", "--delete", "feat-sq")
        self.git(self.main, "fetch", "-q", "--prune", "origin")
        self.forge_merged("feat-sq", "0" * 40)  # another head proves nothing
        self.assert_not_candidate(self.sweep("list").stdout, squash, "unpushed=1")
        self.forge_merged("feat-sq", self.head(squash))
        line, _ = self.block(self.sweep("list").stdout, squash)
        for word in ("unpushed=0", "merged=yes", "candidate=yes"):
            self.assertIn(word, line)

    def test_locked_and_detached_worktrees_are_not_candidates(self):
        locked = self.worktree("feat-locked", merge=True)
        self.git(self.main, "worktree", "lock", str(locked))
        detached = self.main / ".wt/detached"
        self.git(self.main, "worktree", "add", "-q", "--detach", str(detached), "origin/main")
        output = self.sweep("list").stdout
        self.assert_not_candidate(output, locked, "locked")
        self.assert_not_candidate(output, detached, "detached")

    def test_the_working_folder_and_its_parents_are_not_candidates(self):
        merged = self.worktree("feat-merged", merge=True)
        inner = merged / "sub"
        inner.mkdir()
        for cwd in (merged, inner):
            with self.subTest(cwd=cwd.name):
                self.assert_not_candidate(self.sweep("list", cwd=cwd).stdout, merged, "working folder")

    def test_a_worktree_that_holds_or_lies_inside_another_is_not_a_candidate(self):
        self.ignore("nested/")
        parent = self.worktree("feat-parent", merge=True)
        inner = self.worktree("feat-inner", merge=True, parent=parent / "nested")
        beside = self.worktree("feat-beside", merge=True)  # inside the main checkout: the usual layout
        output = self.sweep("list").stdout
        self.assert_not_candidate(output, parent, "holds another worktree")
        self.assert_not_candidate(output, inner, "inside another worktree")
        self.assertIn("candidate=yes", self.block(output, beside)[0])

    def test_nesting_is_caught_through_another_spelling_of_the_path(self):
        self.ignore("nested/")
        parent = self.worktree("feat-parent", merge=True)
        respelled = self.main / ".wt/FEAT-PARENT/nested/feat-alias"
        if not (self.main / ".wt/FEAT-PARENT").exists():
            self.skipTest("this volume is case-sensitive")
        self.git(self.main, "worktree", "add", "-q", "-b", "feat-alias", str(respelled), "origin/main")
        self.assertIn(str(respelled), self.git_paths())  # git keeps the other spelling
        self.assert_not_candidate(self.sweep("list").stdout, parent, "holds another worktree")

    def test_list_removes_nothing_and_rejects_a_remove_option(self):
        merged = self.worktree("feat-merged", merge=True)
        before = self.git_paths()
        for args in (("list",), ("--remove",), ("--remove", "--path", str(merged))):
            self.sweep(*args)
        self.assertNotEqual(self.sweep("--remove").returncode, 0)
        self.assertEqual(self.git_paths(), before)
        self.assertTrue(merged.exists())
        self.assertIn("feat-merged", self.git(self.main, "branch", "--list").stdout)

    def test_the_script_runs_only_read_only_git_and_never_forces(self):
        source = SWEEP.read_text()
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id in ("git", "git_out")]
        self.assertTrue(calls)
        for call in calls:
            sub = call.args[1]
            if isinstance(sub, ast.Starred):  # git_out passing its own arguments on to git
                continue
            self.assertIsInstance(sub, ast.Constant, ast.dump(call))
            self.assertIn(sub.value, READ_ONLY_GIT)
            if sub.value == "worktree":
                self.assertEqual(call.args[2].value, "list")
        strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        for word in ("--force", "-f", "-D", "-ff"):
            self.assertNotIn(word, strings)
        for word in ("rmtree", "unlink", "rmdir", "shell=True", "os.remove", "--force"):
            self.assertNotIn(word, source)

    def test_review_gate_copy_matches(self):
        copy = ROOT / "skills/review-gate/scripts/worktree_sweep.py"
        self.assertEqual(copy.read_bytes(), SWEEP.read_bytes())


if __name__ == "__main__":
    unittest.main()
