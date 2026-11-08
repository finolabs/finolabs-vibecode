"""Synthetic, offline autopilot lease and classification tests."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/fnl-delegate/scripts/autopilot.py'
SETUP = ('## Autopilot\n- Hosts: Claude Code\n- Task choice: choose\n'
         '- Push and pull requests: yes\n- Merge: yes\n- Trusted authors: own\n')


class AutopilotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / 'home')
        self.root = self.home / '.finolabs/vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        self.repo = self.home / 'checkout'
        (self.repo / '.git/refs/remotes/origin').mkdir(parents=True)
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/topic\n')
        (self.repo / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/main\n')
        self.clock = 1800000000

    def load(self):
        self.assertTrue(SCRIPT.exists(), 'autopilot lease/classifier has not been implemented')
        spec = importlib.util.spec_from_file_location('autopilot_tested', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def setup_config(self, text=SETUP):
        (self.root / 'host.md').write_text(text)
        (self.root / 'host.md').chmod(0o600)

    def invoke(self, *argv):
        ap = self.load()
        with patch.object(ap, 'now', return_value=self.clock), patch('os.getcwd', return_value=str(self.repo)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = ap.main(list(argv))
        return status, out.getvalue()

    @property
    def state(self):
        return self.root / 'state/autopilot'

    def lease(self):
        return json.loads((self.state / 'lease.json').read_text())

    def change_lease(self, change):
        value = self.lease()
        change(value)
        (self.state / 'lease.json').write_text(json.dumps(value))

    def start(self, text=SETUP):
        self.setup_config(text)
        status, output = self.invoke('start')
        self.assertEqual(status, 0, output)

    def check(self, argv=None, paths=None, tier=1, code='allowed'):
        flags = ('--argv-json', json.dumps(argv)) if argv is not None else ('--paths', *paths)
        status, output = self.invoke('check', *flags)
        self.assertEqual(status, 0, output)
        self.assertEqual(json.loads(output), {'tier': tier, 'code': code})

    def test_start_requires_setup_and_merge(self):
        for text in ('', '## Other\n', SETUP.replace('- Merge: yes\n', '')):
            self.setup_config(text)
            status, output = self.invoke('start')
            self.assertEqual(status, 3, output)
            self.assertFalse((self.state / 'lease.json').exists())

    def test_summary_private_lease_second_start_and_stop(self):
        self.setup_config()
        status, summary = self.invoke('start', '--hours', '2')
        self.assertEqual(status, 0, summary)
        for value in ('Hosts: Claude Code', 'Merge: yes', 'Lease hours: 2', 'Max runs: 20',
                      'Max runtime minutes: 480', 'Max actions per hour: 30', 'Quota floor percent: 15'):
            self.assertIn(value, summary)
        self.assertEqual(self.lease()['expiry'] - self.lease()['start'], 7200)
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.state / 'lease.json').stat().st_mode), 0o600)
        self.assertEqual(self.invoke('start')[0], 3)
        for _ in range(2):
            status, output = self.invoke('stop')
            self.assertEqual(status, 0, output)
            self.assertFalse((self.state / 'lease.json').exists())
            self.assertTrue((self.state / 'stop').is_file())
        self.assertIn('already absent', output)
        self.assertEqual(stat.S_IMODE((self.state / 'stop').stat().st_mode), 0o600)
        self.assertEqual(self.invoke('start')[0], 0)
        self.assertFalse((self.state / 'stop').exists())

    def test_invalid_setup_and_hours_fail_closed(self):
        for text in (SETUP + '- Merge: no\n', SETUP + '- Unknown: yes\n',
                     SETUP + '- Lease hours: 25\n', SETUP + '- Max runs: 0\n',
                     SETUP.replace('choose', 'anything'), SETUP + '## Autopilot\n- Merge: yes\n'):
            self.setup_config(text)
            self.assertEqual(self.invoke('start')[0], 3)
        self.setup_config()
        for hours in ('0', '25', 'nan'):
            self.assertEqual(self.invoke('start', '--hours', hours)[0], 3)

    def test_symlinks_refused_without_touching_target(self):
        self.setup_config()
        target = self.home / 'target'
        target.write_text('untouched')
        (self.root / 'state').mkdir(mode=0o700)
        self.state.symlink_to(self.home, target_is_directory=True)
        self.assertEqual(self.invoke('start')[0], 3)
        self.state.unlink()
        self.state.mkdir(mode=0o700)
        for name in ('lease.json', 'stop', 'log.jsonl', 'lock'):
            with self.subTest(name=name):
                (self.state / name).unlink(missing_ok=True)
                (self.state / name).symlink_to(target)
                command = ('log', '--kind', 'action') if name == 'log.jsonl' else ('start',)
                self.assertEqual(self.invoke(*command)[0], 3)
                self.assertEqual(target.read_text(), 'untouched')
                (self.state / name).unlink()

    def test_no_repository_state_and_no_environment_config_override(self):
        with patch.dict(os.environ, {'HOME': str(self.repo), 'ORCHESTRATION_HOST_CONFIG': str(self.repo / 'host.md')}, clear=True):
            self.assertEqual(self.invoke('start')[0], 3)
        (self.root / '.git').mkdir()
        self.setup_config()
        self.assertEqual(self.invoke('start')[0], 3)

    def test_lease_guards_synthetic_clock(self):
        self.check(['git', 'status'], tier=3, code='no-lease')
        self.start()
        self.clock += 8 * 3600
        self.check(['git', 'status'], tier=3, code='expired')
        self.clock -= 8 * 3600
        (self.state / 'stop').write_text('')
        (self.state / 'stop').chmod(0o600)
        self.check(['git', 'status'], tier=3, code='stopped')
        (self.state / 'stop').unlink()
        self.setup_config(SETUP.replace('choose', 'listed'))
        self.check(['git', 'status'], tier=3, code='setup-changed')
        self.setup_config()
        self.change_lease(lambda v: v['counters'].update(runs=20))
        self.check(['git', 'status'], tier=3, code='limit')
        self.change_lease(lambda v: v['counters'].update(runs=0, runtime_minutes=480))
        self.check(['git', 'status'], tier=3, code='limit')
        self.change_lease(lambda v: v['counters'].update(runtime_minutes=0, hour_actions=[self.clock] * 30))
        self.check(['git', 'status'], tier=3, code='limit')
        self.clock += 3601
        self.check(['git', 'status'])
        self.assertEqual(self.lease()['counters']['actions'], 1)

    def test_runtime_limit_uses_elapsed_time(self):
        self.start(SETUP + '- Max runtime minutes: 10\n')
        self.clock += 600
        self.check(['git', 'status'], tier=3, code='limit')

    def test_tier_one_commands_and_paths(self):
        self.start(SETUP + '- Max actions per hour: 100\n')
        for argv in (['git', 'status', '--short'], ['git', 'log', '-5', '--oneline'],
                     ['git', 'diff', '--stat', 'origin/main...HEAD'], ['git', 'show', '--stat', 'HEAD'],
                     ['git', 'rev-parse', 'HEAD'], ['git', 'branch', '--show-current'],
                     ['git', 'add', '--', 'src/example.py', 'tests/test_example.py'],
                     ['git', 'commit', '-m', 'Fix example'], ['git', 'push', '-u', 'origin', 'topic'],
                     ['git', 'merge', 'origin/main'], ['gh', 'pr', 'view', '7', '--json', 'headRefOid'],
                     ['gh', 'pr', 'checks', '7'], ['gh', 'pr', 'create', '--title', 'Example', '--body', 'Details'],
                     ['gh', 'pr', 'edit', '7', '--title', 'Example'], ['gh', 'issue', 'list'],
                     ['gh', 'pr', 'merge', '7', '--squash', '--match-head-commit', 'a' * 40]):
            with self.subTest(argv=argv):
                self.check(argv)
        for name in ('ledger.py', 'record.py'):
            self.check(['python3', '-I', str(SCRIPT.parent / name), 'start' if name == 'ledger.py' else 'run'])
        self.check(['python3', '-I', str(SCRIPT.parent / 'heavy_run.py'), 'run', '--label', 'tests', '--', 'gh', 'pr', 'view', '7'])
        self.check(['python3', '-I', str(ROOT / 'skills/fnl-review-gate/scripts/merge_check.py'), '7', '--independent'])
        self.check(paths=['src/example.py', 'tests/test_example.py', 'docs/guide.md'])
        self.assertEqual(self.lease()['counters']['runs'], 1)

    def test_tier_three_commands(self):
        self.start()
        for argv, code in ((['git', 'tag', 'v1'], 'forbidden'), (['gh', 'release', 'view'], 'forbidden'),
                           (['npm', 'publish'], 'forbidden'), (['wrangler', 'deploy'], 'forbidden'),
                           (['rm', '-rf', 'temp'], 'forbidden'), (['rm', '-r', 'temp'], 'forbidden'),
                           (['git', 'show', 'HEAD:.env'], 'protected'),
                           (['git', 'add', 'credentials.json'], 'protected'),
                           (['git', 'push', '--force-with-lease', 'origin', 'topic'], 'forbidden'),
                           (['git', 'push', 'origin', 'topic:main'], 'forbidden'),
                           (['git', 'push', 'origin', 'main'], 'forbidden'),
                           (['git', 'push'], 'unknown'), (['git', '-c', 'alias.x=!bad', 'x'], 'unknown'),
                           (['git', 'branch', '-D', 'topic'], 'unknown'),
                           (['git', 'log', '--output=result'], 'unknown'),
                           (['git', 'merge', 'other'], 'unknown'), (['gh', 'api', '-X', 'POST', 'anything'], 'unknown'),
                           (['gh', 'pr', 'checkout', '7'], 'unknown'), (['git', 'commit', '--no-verify'], 'unknown'),
                           (['git', 'diff', '--output', 'result.txt'], 'unknown'),
                           (['git', 'status', 'unknown/file.py'], 'unknown'),
                           (['git', 'show', 'API_KEY'], 'protected'),
                           (['gh', 'pr', 'merge', '7', '--admin', '--match-head-commit', 'a' * 40], 'unknown'),
                           (['python3', '-I', str(SCRIPT.parent / 'heavy_run.py'), 'run', '--', 'rm', '-rf', 'temp'], 'forbidden'),
                           (['gh', 'pr', 'merge', '7'], 'unpinned'),
                           (['gh', 'pr', 'merge', '7', '--match-head-commit', 'bad'], 'unpinned'),
                           (['echo', 'safe'], 'unknown'), (['python3', '/tmp/ledger.py', 'start'], 'unknown'),
                           (['git', 'status', ';', 'bad'], 'unknown')):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code=code)
        self.assertEqual(self.lease()['counters']['actions'], 0)

    def test_paths_fail_closed(self):
        self.start()
        for path in ('.github/workflows/check.yml', 'src/.github/settings.json', 'hooks/check.py',
                     'src/pre-commit', 'CLAUDE.md', 'docs/AGENTS.md', 'GEMINI.md',
                     'src/settings.json', 'host.md', 'state/autopilot/lease.json', 'setup.json',
                     '.env.local', 'src/secret.key', '.ssh/id_rsa', 'unknown/file.py', '../src/example.py',
                     '/tmp/example.py', 'skills/example/SKILL.md',
                     'skills/fnl-delegate/scripts/autopilot.py', 'skills/fnl-review-gate/scripts/merge_check.py'):
            with self.subTest(path=path):
                self.check(paths=[path], tier=3, code='unknown' if path in {'unknown/file.py', '../src/example.py', '/tmp/example.py'} else 'protected')

    def test_review_findings_round_one(self):
        self.start(SETUP.replace('- Merge: yes', '- Merge: no'))
        wrapper = ['python3', '-I', str(SCRIPT.parent / 'heavy_run.py')]
        pin = ['gh', 'pr', 'merge', '7', '--match-head-commit', 'a' * 40]
        # The wrapper grammar: a command with no separator, or anything unknown, is never allowed.
        self.check(wrapper + ['run'] + pin, tier=3, code='unknown')
        self.check(wrapper + ['run', 'echo', 'safe'], tier=3, code='unknown')
        self.check(wrapper + ['run', '--poll', '1', '--'] + pin, tier=3, code='unknown')
        self.check(wrapper + ['run', '--label', 'x', '--'] + pin, tier=3, code='merge-disabled')
        self.check(wrapper + ['run', '--', 'echo', 'safe'], tier=3, code='unknown')
        self.check(wrapper + ['status'])
        # A push to a tag or any other non-branch ref namespace is a Tier 3 action.
        for refspec in ('topic:refs/tags/v-example', 'topic:tags/v-example', 'topic:refs/remotes/origin/x',
                        'topic:refs/notes/x', 'refs/tags/v1:topic'):
            self.check(['git', 'push', 'origin', refspec], tier=3, code='forbidden')
        self.check(['git', 'push', 'origin', 'topic:refs/heads/topic'])
        # Instruction files and review enforcers are protected wherever they live.
        for path in ('docs/CONVENTIONS.md', 'docs/copilot-instructions.md', 'skills/fnl-review-gate/scripts/review_route.py'):
            self.check(paths=[path], tier=3, code='protected')
        # A directory operand would stage everything below it, including a protected descendant.
        (self.repo / 'src/bundle.py').mkdir(parents=True)
        (self.repo / 'src/bundle.py/settings.json').write_text('{}')
        self.check(['git', 'add', '--', 'src/bundle.py'], tier=3, code='unknown')
        self.check(paths=['src/bundle.py/settings.json'], tier=3, code='protected')

    def test_merge_and_push_settings(self):
        self.start(SETUP.replace('- Merge: yes', '- Merge: no').replace('requests: yes', 'requests: no'))
        self.check(['gh', 'pr', 'merge', '7', '--match-head-commit', 'a' * 40], tier=3, code='merge-disabled')
        for argv in (['git', 'push', 'origin', 'topic'], ['gh', 'pr', 'create']):
            self.check(argv, tier=3, code='push-disabled')
        self.check(['gh', 'pr', 'view', '7'])

    def test_log_redaction_caps_retention_and_ids(self):
        self.start()
        synthetic = 'ghp_' + 'x' * 24
        note = 'Reason\n\x00 ' + synthetic + ' API_TOKEN=short /tmp/record.txt src/example.py ' + 'x' * 700
        status, output = self.invoke('log', '--kind', 'parked', '--task', 'T001', '--pr', '7', '--run', 'd-example', '--note', note)
        self.assertEqual(status, 0, output)
        path = self.state / 'log.jsonl'
        record = json.loads(path.read_text())
        self.assertEqual(record['tier'], 3)
        self.assertEqual(record['task'], 'T001')
        self.assertLessEqual(len(record['note']), 500)
        self.assertNotIn(synthetic, record['note'])
        self.assertNotIn('short', record['note'])
        self.assertNotIn('/tmp/', record['note'])
        self.assertNotIn('src/example.py', record['note'])
        self.assertFalse(any(ord(c) < 32 for c in record['note']))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.clock += 31 * 86400
        self.assertEqual(self.invoke('log', '--kind', 'stop', '--note', 'Returned')[0], 0)
        self.assertEqual(len(path.read_text().splitlines()), 1)
        self.assertEqual(self.invoke('log', '--kind', 'action', '--note', 'git push origin topic')[0], 0)
        self.assertNotIn('git push', path.read_text())
        for flags in (('--task', '../bad'), ('--run', synthetic)):
            self.assertEqual(self.invoke('log', '--kind', 'action', *flags)[0], 3)

    def test_unsafe_state_invalid_argv_and_no_execution(self):
        self.start()
        for raw in ('null', '{}', '[1]', 'invalid', '[]'):
            status, output = self.invoke('check', '--argv-json', raw)
            self.assertEqual(status, 0, output)
            self.assertEqual(json.loads(output), dict(tier=3, code='unknown'))
        (self.state / 'lease.json').chmod(0o644)
        self.check(['git', 'status'], tier=3, code='unsafe')
        (self.state / 'lease.json').chmod(0o600)
        with patch('subprocess.run', side_effect=AssertionError('check must not execute')):
            self.check(['git', 'status'])

    def test_path_symlink_is_protected_without_reading_target(self):
        self.start()
        (self.repo / 'src').mkdir()
        target = self.home / 'synthetic'
        target.write_text('unread')
        (self.repo / 'src/example.py').symlink_to(target)
        self.check(paths=['src/example.py'], tier=3, code='protected')

    def test_branch_default_is_read_from_metadata_and_main_merge_needs_work_branch(self):
        self.start()
        (self.repo / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/stable\n')
        self.check(['git', 'push', 'origin', 'topic:stable'], tier=3, code='forbidden')
        self.check(['git', 'push', 'origin', 'HEAD:refs/heads/topic'])
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/stable\n')
        self.check(['git', 'merge', 'origin/main'], tier=3, code='forbidden')

    def test_held_lock_and_lease_hash_mismatch_refuse(self):
        self.start()
        ap = self.load()
        with ap.private_folder():
            self.check(['git', 'status'], tier=3, code='unsafe')
        self.change_lease(lambda v: v.update(settings_hash='0' * 64))
        self.check(['git', 'status'], tier=3, code='setup-changed')


if __name__ == '__main__':
    unittest.main()
