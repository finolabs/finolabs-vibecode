"""Zero-park `open` lease, end to end (docs/specs/afk-autonomy.md acceptance 2).

One `open` lease with both guards on runs a whole task in a scratch repository whose origin is a local bare remote.
Every step is judged through `afk.py check` first. Only `git` runs for real; `gh`, `npm` and `wrangler` are recording
stubs on PATH, and `post_review.py` is checked without running. The test passes when every verdict is Tier 1 and the
lease log holds no `parked` entry."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

from tests.test_afk import ROOT, SETUP, AfkBase

OPEN = SETUP.replace('- Mode: strict\n', '')  # a missing Mode line is `open`; both guards default to `guard`
POST_REVIEW = str(ROOT / 'skills/review-gate/scripts/post_review.py')
STUB = """#!{python}
import json, os, sys
with open(os.environ['STUB_LOG'], 'a') as log:
    log.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + '\\n')
"""


class ZeroParkLeaseTest(AfkBase):
    def setUp(self):
        super().setUp()
        if shutil.which('git') is None:
            self.skipTest('git is not installed')
        base = Path(self.tmp.name)
        self.bare = base / 'remote.git'
        self.stubs = base / 'bin'
        self.stubs.mkdir()
        self.calls = base / 'stub-calls.jsonl'
        for name in ('gh', 'npm', 'wrangler'):
            stub = self.stubs / name
            stub.write_text(STUB.format(python=sys.executable))
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        self.env = {'PATH': f'{self.stubs}{os.pathsep}{os.environ.get("PATH", os.defpath)}', 'HOME': str(self.home),
                    'STUB_LOG': str(self.calls), 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
                    'GIT_AUTHOR_NAME': 'Synthetic', 'GIT_AUTHOR_EMAIL': 'synthetic@example.com',
                    'GIT_COMMITTER_NAME': 'Synthetic', 'GIT_COMMITTER_EMAIL': 'synthetic@example.com',
                    # Only the real git runs see the local bare remote; the checkout's own origin stays the GitHub
                    # repository that `check` verifies as the target.
                    'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': f'url.{self.bare}.insteadOf',
                    'GIT_CONFIG_VALUE_0': 'https://github.com/example/demo.git'}
        # A real repository replaces the fixture's synthetic .git; its origin is the local bare remote.
        shutil.rmtree(self.repo / '.git')
        self.git('init', '-q', '--bare', '-b', 'main', str(self.bare), cwd=base)
        self.git('init', '-q', '-b', 'main')
        self.git('remote', 'add', 'origin', 'https://github.com/example/demo.git')
        (self.repo / 'TASKS.md').write_text('- [ ] T001 Add the demo page\n')
        (self.repo / 'package.json').write_text('{"name": "demo", "version": "0.1.0"}\n')
        self.git('add', 'TASKS.md', 'package.json')
        self.git('commit', '-q', '-m', 'Start the demo')
        self.git('push', '-q', 'origin', 'main')
        self.git('fetch', '-q', 'origin')
        self.git('remote', 'set-head', 'origin', 'main')
        self.verdicts = []

    def git(self, *args, cwd=None):
        done = subprocess.run(['git', *args], cwd=cwd or self.repo, env=self.env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def judge(self, label, argv=None, paths=None):
        flags = ('--argv-json', json.dumps(argv)) if argv is not None else ('--paths', *paths)
        status, output = self.invoke('check', *flags)
        verdict = json.loads(output)
        self.verdicts.append((label, verdict))
        if verdict['tier'] != 1:  # the agent parks what check refuses
            self.invoke('log', '--kind', 'parked', '--note', 'step refused')
        return status == 0 and verdict['tier'] == 1

    def step(self, label, argv, run=True):
        """Judge one command and run it only on Tier 1: git for real, the stubs through PATH."""
        if self.judge(label, argv) and run:
            program = shutil.which(argv[0], path=self.env['PATH'])
            done = subprocess.run([program, *argv[1:]], cwd=self.repo, env=self.env, capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL, check=False)
            self.assertEqual(done.returncode, 0, (label, done.stderr))

    def test_one_open_lease_finishes_a_task_with_zero_parked_entries(self):
        self.start(OPEN)
        # Pick a task and create a branch.
        self.step('read the task list', ['git', 'show', 'HEAD:TASKS.md'])
        self.step('create a branch', ['git', 'switch', '-c', 'feat/demo-page'])
        # Edit the four files of the task.
        files = {'package.json': '{"name": "demo", "version": "0.2.0", "scripts": {"test": "x", "build": "y"}}\n',
                 'specs/plan.md': '# Plan\n\nOne page.\n', 'src/pages/[slug].astro': '---\n---\n<h1>Demo</h1>\n',
                 'scripts/check-site.mjs': 'console.log("ok");\n'}
        if self.judge('edit the files', paths=list(files)):
            for name, text in files.items():
                (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
                (self.repo / name).write_text(text)
        self.step('run the tests', ['npm', 'test'])
        self.step('build', ['npm', 'run', 'build'])
        self.step('stage', ['git', 'add', *files])
        self.step('commit', ['git', 'commit', '-q', '-m', 'Add the demo page'])
        self.step('push the branch', ['git', 'push', '-q', 'origin', 'HEAD:refs/heads/feat/demo-page'])
        self.step('open the pull request', ['gh', 'pr', 'create', '--head', 'feat/demo-page', '--repo',
                                            'github.com/example/demo', '--title', 'Add the demo page',
                                            '--body', 'Adds the demo page.'])
        body = self.repo / '.finolabs/review.md'
        body.parent.mkdir()
        body.write_text('<!-- fnl-review kind=code head=%s verdict=APPROVE -->\nReviewer: claude\n' % ('a' * 40))
        for kind in ('code', 'security'):
            self.step(f'post the {kind} review', ['python3', '-I', POST_REVIEW, '7', '--body-file', str(body)], run=False)
        head = self.git('rev-parse', 'HEAD')
        self.step('merge', ['gh', 'pr', 'merge', '7', '--merge', '--match-head-commit', head, '--repo',
                            'github.com/example/demo'])
        status, output = self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)
        self.assertEqual(status, 0, output)
        self.step('tag', ['git', 'tag', 'v0.2.0'])
        self.step('release', ['gh', 'release', 'create', 'v0.2.0', '--repo', 'github.com/example/demo',
                              '--notes', 'The demo page.'])
        self.step('preview deploy', ['wrangler', 'pages', 'deploy', 'dist', '--project-name', 'demo',
                                     '--branch', 'preview'])

        # What really happened: the branch reached the bare remote, the tag exists, the stubs ran.
        self.assertEqual(self.git('rev-parse', 'refs/heads/feat/demo-page', cwd=self.bare), head)
        self.assertEqual(self.git('rev-parse', 'v0.2.0'), head)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([call[:3] for call in calls],
                         [['npm', 'test'], ['npm', 'run', 'build'], ['gh', 'pr', 'create'], ['gh', 'pr', 'merge'],
                          ['gh', 'release', 'create'], ['wrangler', 'pages', 'deploy']])
        # The pass condition: every verdict is Tier 1 and the lease log holds zero parked entries.
        table = '\n'.join(f'{label}: tier {v["tier"]} {v["code"]}' for label, v in self.verdicts)
        print('\nzero-park lease (open, both guards on):\n' + table)
        self.assertEqual([label for label, v in self.verdicts if v['tier'] != 1], [], table)
        log = [json.loads(line) for line in (self.state / 'log.jsonl').read_text().splitlines()]
        self.assertEqual([e for e in log if e.get('kind') == 'parked'], [])
        self.assertIn('merge', {e.get('kind') for e in log})

    def test_the_guard_still_answers_on_the_default_branch(self):
        # The same lease refuses a push to the default branch, so the zero-park result is not a gate that is off.
        self.start(OPEN)
        self.assertFalse(self.judge('push to main', ['git', 'push', 'origin', 'HEAD:refs/heads/main']))
        self.assertEqual(self.verdicts[-1][1], {'tier': 3, 'code': 'guarded'})
        log = [json.loads(line) for line in (self.state / 'log.jsonl').read_text().splitlines()]
        self.assertEqual(len([e for e in log if e.get('kind') == 'parked']), 1)


if __name__ == '__main__':
    import unittest
    unittest.main()
