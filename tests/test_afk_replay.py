"""Ledger replay (docs/specs/afk-autonomy.md acceptance 1): the 60 parked items of the lease ledger in `open`.

Each fixture is synthetic: rebuilt by hand from an item's enumerated fields and a reading of its note, never executed,
holding no note text and no real names. Both guards are on, and the lease allows one action an hour, so no limit
helps. Items 14, 29, 33 and 40 have no fixture: their notes are fully redacted."""
import json
import unittest

from tests.test_afk_open import OPEN, OpenBase

REDACTED = (14, 29, 33, 40)
# item -> (reason it parked, [argv list or {'paths': [...]}, ...]); every step must be Tier 1 in `open`.
FIXTURES = {
    1: ('owner judgment: live install', [['./scripts/install.sh', '--live']]),
    2: ('owner judgment: stale task boxes', [{'paths': ['specs/012-infra/tasks.md']}]),
    3: ('local merge of a task branch', [['git', 'merge', '--no-edit', 'task/u032']]),
    4: ('dispatch and package paths', [['codex', 'exec', 'review the pull request'],
                                       {'paths': ['packages/api/src/index.ts', 'services/worker/main.go']}]),
    5: ('own-plugin edits', [{'paths': ['skills/afk/SKILL.md', 'skills/setup/scripts/afk_setup.py']},
                             ['git', 'push', 'origin', 'topic']]),
    6: ('merge touching enforcers', [['gh', 'pr', 'merge', '239', '--merge']]),
    7: ('roots, local merge, dispatch', [{'paths': ['apps/web/page.tsx', 'deploy/k8s.yaml', 'Makefile']},
                                        ['git', 'merge', 'task/t1'], ['claude', '-p', 'implement T1'],
                                        ['codex', 'exec', 'implement T2']]),
    8: ('machine: disk full', [['go', 'clean', '-cache'], ['open', '-a', 'OrbStack']]),
    9: ('top-level file', [{'paths': ['BACKLOG.md']}]),
    10: ('session start', [['claude', '-p', 'run the spec task']]),
    11: ('spec paths', [{'paths': ['specs/025/research.md', 'specs/025/tasks.md']}]),
    12: ('product roots', [{'paths': ['core/a.md', 'templates/b.md', 'packs/c.md', 'evals/d.json', 'specs/e.md']}]),
    13: ('agent dispatch', [['agy', '-p', 'review'], ['claude', '-p', 'review']]),
    15: ('accept and merge', [['gh', 'pr', 'merge', '12', '--merge']]),
    16: ('owner judgment: visibility', [['gh', 'repo', 'edit', '--visibility', 'public',
                                         '--accept-visibility-change-consequences']]),
    17: ('owner judgment: first tag', [['git', 'tag', 'v0.1.0'], ['git', 'push', 'origin', 'v0.1.0']]),
    18: ('machine: quota for evals', [['claude', 'plugin', 'eval', '.']]),
    19: ('worktree removal', [['git', 'worktree', 'remove', '../wt-feature']]),
    20: ('pull request comment', [['gh', 'pr', 'comment', '73', '--body', 'Review record']]),
    21: ('owner judgment: renders', [['python3', 'scripts/render.py', '--png'], {'paths': ['docs/diagrams/a.html']}]),
    22: ('machine: quota for a rewrite', [{'paths': ['skills/example/SKILL.md']}]),
    23: ('merge touching hooks', [{'paths': ['hooks/hooks.json']}, ['gh', 'pr', 'merge', '80', '--merge']]),
    24: ('own-plugin edits and merge', [{'paths': ['skills/afk/SKILL.md', 'skills/delegate/scripts/afk.py']},
                                        ['gh', 'pr', 'merge', '81', '--merge']]),
    25: ('waits on merges: release', [['git', 'tag', 'v0.2.0'], ['gh', 'release', 'create', 'v0.2.0'],
                                      {'paths': ['catalog/marketplace.json']}]),
    26: ('same-family reviews', [['gh', 'pr', 'merge', '73', '--merge']]),
    27: ('machine: hook under memory pressure', [['git', 'push', '--no-verify', 'origin', 'topic']]),
    28: ('same-family reviews', [['gh', 'pr', 'merge', '90', '--merge']]),
    30: ('same-family reviews', [['gh', 'pr', 'merge', '258', '--merge']]),
    31: ('same-family reviews', [['gh', 'pr', 'merge', '43', '--merge']]),
    32: ('waits on a merge: release', [['gh', 'release', 'create', 'v0.15.0']]),
    34: ('waits on a tag: catalog pin', [{'paths': ['.claude-plugin/marketplace.json']},
                                         ['git', 'commit', '-m', 'Pin the plugin to its tag']]),
    35: ('local merge of main', [['git', 'merge', 'main']]),
    36: ('empty roots: commit to tag', [['git', 'add', 'evals/x.json'], ['git', 'commit', '-m', 'Fix the release'],
                                        ['git', 'push', 'origin', 'topic'], ['git', 'tag', 'v1.2.0'],
                                        ['claude', 'plugin', 'eval', '.']]),
    37: ('same-family reviews', [['gh', 'pr', 'merge', '43', '--merge']]),
    38: ('lease limit', [['git', 'push', 'origin', 'topic'], ['gh', 'pr', 'create', '--title', 'Fix', '--body', 'Body']]),
    39: ('router marker in a body', [['gh', 'pr', 'create', '--title', 'Release',
                                      '--body', 'Notes\n<!-- fnl-router depth=MIN trigger=none -->']]),
    41: ('machine: app relaunch', [['open', '-a', 'ExampleApp']]),
    42: ('local checks', [['python3', 'skills/checks/scripts/checks.py', 'run'], ['./scripts/ci-local.sh']]),
    43: ('dispatch, worktree, skill edits', [['git', 'worktree', 'add', '../wt-review', '-b', 'review'],
                                             {'paths': ['SKILL.md', 'references/a.md', 'profiles/p.md']},
                                             ['claude', '-p', 'review']]),
    44: ('dispatch, merge, tag', [['codex', 'exec', 'review'], ['gh', 'pr', 'merge', '5', '--merge'],
                                  ['git', 'tag', 'v0.3.0']]),
    45: ('spec paths', [{'paths': ['specs/023/tasks.md']}]),
    46: ('code paths', [{'paths': ['server/release.go']}]),
    47: ('owner judgment: fixture name', [{'paths': ['tests/fixtures/space.json']}]),
    48: ('review relay', [['gh', 'pr', 'comment', '293', '--body', 'Review relayed']]),
    49: ('owner judgment: rework limit', [['gh', 'pr', 'merge', '21', '--merge']]),
    50: ('unlisted test command', [['python3', '-m', 'unittest', 'tests.test_example']]),
    51: ('agent dispatch', [['agy', '-p', 'review PR 294']]),
    52: ('owner judgment: unreviewed fix', [['go', 'test', './...'], ['git', 'push', 'origin', 'topic']]),
    53: ('unlisted deploy target', [['wrangler', 'pages', 'deploy', 'dist']]),
    54: ('deploy with arguments', [['wrangler', 'pages', 'deploy', 'dist', '--project-name', 'demo', '--branch', 'preview']]),
    55: ('route path', [{'paths': ['src/pages/dev/gallery.astro']}]),
    56: ('bracketed paths', [{'paths': ['src/pages/[slug].astro', 'src/pages/og/[slug].png.ts', 'src/layouts/Base.astro']}]),
    57: ('unknown extension', [{'paths': ['scripts/check-site.mjs']}]),
    58: ('top-level file', [{'paths': ['package.json', 'package-lock.json']}, ['npm', 'install']]),
    59: ('owner judgment: uncommitted spec', [['git', 'add', 'specs/030/spec.md', 'specs/030/plan.md', 'specs/030/tasks.md'],
                                              ['git', 'commit', '-m', 'Add the spec']]),
    60: ('unknown path', [{'paths': ['design/moodboard.png']}, ['git', 'add', 'design/moodboard.png']]),
}


class ReplayTest(OpenBase):
    def setUp(self):
        super().setUp()
        self.restart(OPEN + '- Max actions per hour: 1\n')

    def test_counts(self):
        self.assertEqual(len(FIXTURES), 56)
        self.assertEqual(sorted(set(range(1, 61)) - set(FIXTURES)), list(REDACTED))

    def test_every_fixture_is_tier_1_in_open(self):
        rows = []
        for item, (reason, steps) in sorted(FIXTURES.items()):
            codes = []
            for step in steps:
                flags = ('--paths', *step['paths']) if isinstance(step, dict) else ('--argv-json', json.dumps(step))
                status, output = self.invoke('check', *flags)
                result = json.loads(output)
                codes.append(result['code'])
                with self.subTest(item=item, step=step):
                    self.assertNotIn(result['code'], {'floor', 'guarded'})
                    self.assertEqual((status, result), (0, {'tier': 1, 'code': 'allowed'}))
            rows.append(f'{item:>2}  3 -> {1 if set(codes) == {"allowed"} else 3}  {reason}')
        print('\nitem old new reason\n' + '\n'.join(rows))


if __name__ == '__main__':
    unittest.main()
