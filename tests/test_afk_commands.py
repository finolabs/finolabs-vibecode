"""`afk.py check --commands-json`: the hook's command sites judged one by one and recorded once (docs/specs/
afk-hook-tokenizer.md B, decision 2). Synthetic account home only."""

import json
import unittest

from tests import test_afk

SCRIPT, SETUP = test_afk.SCRIPT, test_afk.SETUP
HEAD = 'a' * 40
HOST_YES = ('--rung', 'host', '--settled', 'yes', '--by', 'claude', '--option', '1', '--of', '2',
            '--model', 'claude-opus-5-5')


def site(*argv, assignments=(), redirects=(), repeated=False):
    return {'assignments': list(assignments), 'argv': list(argv), 'redirects': [list(r) for r in redirects],
            'repeated': repeated}


def merge(number):
    return site('gh', 'pr', 'merge', str(number), '--squash', '--match-head-commit', HEAD,
                '--repo', 'github.com/example/demo')


class CommandsJsonTest(test_afk.AfkBase):
    def sites(self, *sites, tier=1, code='allowed'):
        status, output = self.invoke('check', '--coordinator', 'claude', '--commands-json', json.dumps(list(sites)))
        self.assertEqual(status, 0 if tier == 1 else 3, output)
        self.assertEqual(json.loads(output), {'tier': tier, 'code': code})

    def approve(self, argv):
        status, output = self.invoke('log', '--kind', 'decision', '--project', 'demo', '--topic', 'run it',
                                     '--precedents', '0', *HOST_YES, '--approve-argv-json', json.dumps(argv))
        self.assertEqual(status, 0, output)

    def log(self, kind):
        path = self.state / 'log.jsonl'
        lines = path.read_text().splitlines() if path.exists() else []
        return [entry for entry in map(json.loads, lines) if entry.get('kind') == kind]

    def ci_script(self):
        (self.repo / 'scripts').mkdir(exist_ok=True)
        (self.repo / 'scripts/ci-local.sh').write_text('#!/bin/sh\n')
        return ['scripts/ci-local.sh', 'fast']

    def test_a_denied_site_records_nothing(self):
        self.start()
        self.merge_ok(7, HEAD)
        self.sites(site('git', 'status'), merge(7), site('curl', 'https://example.com'), tier=3, code='unknown')
        self.assertEqual(self.lease()['counters'], {})
        self.assertEqual(self.log('merge-pin'), [])

    def test_an_allowed_call_counts_one_action_and_pins_each_merge(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.merge_ok(7, HEAD)
        self.merge_ok(8, HEAD)
        self.sites(site('git', 'status'), site('git', 'log', '--oneline'), merge(7), merge(8))
        self.assertEqual(self.counts()['actions'], 1)
        self.assertEqual(sorted(p['pr'] for p in self.log('merge-pin')), [7, 8])

    def test_a_log_with_room_for_one_pin_keeps_neither(self):
        # Review of b1faa973: the call's records are written all or none, so a refused call leaves no pin behind.
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.merge_ok(7, HEAD)
        self.merge_ok(8, HEAD)
        log = self.state / 'log.jsonl'
        kept = log.read_bytes() if log.exists() else b''
        pin = len(json.dumps(dict(time=self.clock, tier=1, kind='merge-pin', pr=7, head=HEAD,
                                  repo='github.com/example/demo', note=''), separators=(',', ':'))) + 1
        filler = json.dumps({'time': self.clock, 'kind': 'filler', 'note': ''}, separators=(',', ':')).encode()
        room = self.load().MAX_LOG - len(kept) - pin - pin // 2
        pad = json.dumps({'time': self.clock, 'kind': 'filler', 'note': 'x' * (room - len(filler) - 1)},
                         separators=(',', ':')).encode()
        log.write_bytes(kept + pad + b'\n')
        log.chmod(0o600)
        self.sites(merge(7), merge(8), tier=3, code='log-unwritable')
        self.assertEqual(self.log('merge-pin'), [])
        self.assertEqual(self.lease()['counters'], {})

    def test_an_approval_is_used_by_its_exact_subject_once(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        argv = self.ci_script()
        self.approve(argv)
        # Two sites that need the same one-time approval: the second denies and nothing is used.
        self.sites(site(*argv), site(*argv), tier=3, code='unknown')
        self.assertEqual(self.log('approval-used'), [])
        # A site in a loop cannot use it: its count is unknown before it runs.
        self.sites(site(*argv, repeated=True), tier=3, code='unknown')
        self.sites(site('git', 'status'), site(*argv), code='decided')
        self.assertEqual(len(self.log('approval-used')), 1)
        self.sites(site(*argv), tier=3, code='unknown')

    def test_runs_are_reserved_per_site_and_checked_before_any_is_kept(self):
        self.start(SETUP + '- Max runs: 2\n- Max actions per hour: 1000\n')
        ledger = ['python3', '-I', str(SCRIPT.parent / 'ledger.py'), 'start']
        self.sites(site(*ledger))
        self.sites(site(*ledger), site(*ledger), tier=3, code='spent')
        self.assertEqual(self.counts()['runs'], 1)
        self.sites(site(*ledger, repeated=True), tier=3, code='unknown')
        self.sites(site(*ledger), site('git', 'status'))
        self.assertEqual(self.counts()['runs'], 2)

    def test_a_merge_in_a_loop_denies(self):
        self.start()
        self.merge_ok(7, HEAD)
        loop = merge(7)
        loop['repeated'] = True
        self.sites(loop, tier=3, code='unknown')
        self.assertEqual(self.log('merge-pin'), [])

    def test_redirect_targets_are_floored_and_path_checked_in_strict(self):
        self.start()
        # `strict` answers as `check --paths` does: a key file is a protected name there (the floor in `open`).
        self.sites(site('git', 'status', redirects=[('write', '/tmp/afk/server.pem')]), tier=3, code='protected')
        self.sites(site('git', 'status', redirects=[('write', 'AGENTS.afk.md')]), tier=3, code='protected')
        self.sites(site('git', 'status', redirects=[('read', '/tmp/input')]), tier=3, code='unknown')
        self.sites(site('git', 'status', redirects=[('write', 'src/out.txt')]))
        self.assertEqual(self.counts()['actions'], 1)

    def test_open_judges_the_floor_and_targets_only(self):
        self.start(SETUP.replace('- Mode: strict\n', '- Mode: open\n'))
        self.sites(site('ls', '/tmp'), site('git', 'status', redirects=[('write', 'AGENTS.afk.md')]))
        self.sites(site('ls'), site('env'), tier=3, code='floor')
        self.sites(site('cat', redirects=[('read', '/tmp/.netrc')]), tier=3, code='floor')
        self.assertEqual(self.lease()['counters'], {})

    def test_assignments_stay_on_their_site(self):
        self.start(SETUP.replace('- Mode: strict\n', '- Mode: open\n'))
        guard = site('git', 'push', 'origin', assignments=['GIT_CONFIG_COUNT=1', 'GIT_CONFIG_KEY_0=remote.origin.push',
                                                           'GIT_CONFIG_VALUE_0=HEAD:refs/heads/main'])
        self.sites(guard, tier=3, code='guarded')
        self.sites(site('ls'), site(assignments=['API_TOKEN=x']), tier=3, code='floor')

    def test_invalid_sites_are_unknown_and_argv_json_is_unchanged(self):
        self.start()
        for raw in ('[]', '{}', 'not json', json.dumps([{'argv': ['ls']}]),
                    json.dumps([site('ls', redirects=[('exec', 'x')])])):
            with self.subTest(raw=raw):
                status, output = self.invoke('check', '--commands-json', raw)
                self.assertEqual((status, json.loads(output)), (3, {'tier': 3, 'code': 'unknown'}))
        self.check(['git', 'status'])
        self.check(['curl', 'https://example.com'], tier=3, code='unknown')


if __name__ == '__main__':
    unittest.main()
