"""Synthetic, offline autopilot lease and classification tests."""
import contextlib
import importlib.util
import io
import json
import re
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


class AutopilotBase(unittest.TestCase):
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


class AutopilotTest(AutopilotBase):
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
                     ['git', 'commit', '-m', 'Fix example'], ['git', 'push', '-u', 'origin', 'HEAD:refs/heads/topic'],
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

    def test_review_findings_round_two(self):
        self.start()
        # A bare or abbreviated destination can resolve to a tag, so only an explicit branch ref is known.
        for refspec in ('v-example', 'topic:v-example', 'topic', 'HEAD', 'v-example:v-example'):
            self.check(['git', 'push', 'origin', refspec], tier=3, code='unknown')
        self.check(['git', 'push', 'origin', 'v-example:refs/heads/topic'])
        # Every trusted wrapper and its dependencies are protected as paths and through git add.
        for name in ('heavy_run.py', 'ledger.py', 'record.py', 'delegate_env.py', 'run_env.py', 'data_root.py', 'assignments.py'):
            path = 'skills/fnl-delegate/scripts/' + name
            self.check(paths=[path], tier=3, code='protected')
            self.check(['git', 'add', '--', path], tier=3, code='protected')
        self.check(paths=['skills/fnl-review-gate/scripts/merge_check.py'], tier=3, code='protected')
        # Case aliases name the same file on a case-insensitive filesystem.
        for name in ('Heavy_run.py', 'LEDGER.py', 'Run_env.py', 'Data_Root.py', 'Merge_Check.py'):
            path = 'skills/fnl-delegate/scripts/' + name
            self.check(paths=[path], tier=3, code='protected')
            self.check(['git', 'add', '--', path], tier=3, code='protected')

    def test_review_findings_security_one(self):
        self.start()
        self.repo = ROOT  # the checkout whose scripts are the installed wrappers
        # New modules next to the trusted wrappers could shadow an import in them, so the folders are protected.
        for folder in ('fnl-review-gate', 'fnl-delegate', 'fnl-setup'):
            for name in ('struct.py', 'zlib.py', 'helper.py', 'pkg/__init__.py'):
                path = 'skills/%s/scripts/%s' % (folder, name)
                self.check(paths=[path], tier=3, code='protected')
                self.check(['git', 'add', '--', path], tier=3, code='protected')

    def test_linked_sibling_skill_folders_are_protected_by_target_and_wrapper_refused(self):
        # A synthetic install whose review-gate skill is a link to another checkout.
        install = self.home / 'install/skills'
        (install / 'fnl-delegate/scripts').mkdir(parents=True)
        checkout = self.home / 'other/skills/fnl-review-gate/scripts'
        checkout.mkdir(parents=True)
        (checkout / 'merge_check.py').write_text('# synthetic')
        (install / 'fnl-review-gate').symlink_to(self.home / 'other/skills/fnl-review-gate')
        ap = self.load()
        copy = install / 'fnl-delegate/scripts/autopilot.py'
        copy.write_text(SCRIPT.read_text())
        spec = importlib.util.spec_from_file_location('autopilot_linked', copy)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch('os.getcwd', return_value=str(self.home / 'other')):
            self.assertTrue(module.plugin_code('skills/fnl-review-gate/scripts/difflib.py'))
        applied = dict(module.DEFAULTS, Merge='yes')
        wrapper = ['python3', '-I', str(install / 'fnl-review-gate/scripts/merge_check.py'), '7', '--independent']
        self.assertEqual(module.script_command(wrapper, applied), 'unknown')

    def test_merge_and_push_settings(self):
        self.start(SETUP.replace('- Merge: yes', '- Merge: no').replace('requests: yes', 'requests: no'))
        self.check(['gh', 'pr', 'merge', '7', '--match-head-commit', 'a' * 40], tier=3, code='merge-disabled')
        for argv in (['git', 'push', 'origin', 'HEAD:refs/heads/topic'], ['gh', 'pr', 'create']):
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


DISPATCH = 'd20261110-010203-abcd'
DECISION = re.compile(r'q[0-9]{8}-[0-9]{6}-[0-9a-f]{4}')
# Every row of the attempt schema in docs/specs/away-decisions.md "Record for analysis": flags and stored values.
ROWS = {
    'rule yes': (('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '1', '--of', '2'),
                 dict(by='rule', option=1, of=2)),
    'rule no': (('--rung', 'rule', '--settled', 'no', '--by', 'rule'), dict(by='rule')),
    'jev yes': (('--rung', 'jev', '--settled', 'yes', '--by', 'jev', '--option', '1', '--of', '2', '--probability', '0.9'),
                dict(by='jev', option=1, of=2, probability=0.9)),
    'jev no': (('--rung', 'jev', '--settled', 'no', '--by', 'jev', '--probability', '0.5'), dict(by='jev', probability=0.5)),
    'jev unavailable': (('--rung', 'jev', '--settled', 'unavailable', '--by', 'jev'), dict(by='jev')),
    'advisor yes': (('--rung', 'advisor', '--settled', 'yes', '--by', 'codex', '--option', '2', '--of', '3',
                     '--dispatch', DISPATCH, '--model', 'gpt-5.5'),
                    dict(by='codex', option=2, of=3, dispatch=DISPATCH, model='gpt-5.5')),
    'advisor no': (('--rung', 'advisor', '--settled', 'no', '--by', 'codexwork', '--dispatch', DISPATCH, '--model', 'gpt-5.5'),
                   dict(by='codexwork', dispatch=DISPATCH, model='gpt-5.5')),
    'advisor unavailable, selected': (('--rung', 'advisor', '--settled', 'unavailable', '--by', 'codex'), dict(by='codex')),
    'advisor unavailable, selected and started': (('--rung', 'advisor', '--settled', 'unavailable', '--by', 'codex',
                                                   '--dispatch', DISPATCH), dict(by='codex', dispatch=DISPATCH)),
    'advisor unavailable, no candidate': (('--rung', 'advisor', '--settled', 'unavailable'), {}),
    'host yes': (('--rung', 'host', '--settled', 'yes', '--by', 'claude', '--option', '1', '--of', '2', '--model', 'claude-opus-5-5'),
                 dict(by='claude', option=1, of=2, model='claude-opus-5-5')),
    'park yes': (('--rung', 'park', '--settled', 'yes', '--by', 'claude'), dict(by='claude')),
}
EXTRA = {'--by': 'codex', '--option': '1', '--of': '2', '--probability': '0.9', '--dispatch': DISPATCH, '--model': 'gpt-5.5'}
SETUP_AWAY = SETUP.replace('Claude Code', 'Claude Code, Codex') + '- Max actions per hour: 1000\n'
JUDGE = ['python3', '-I', str(SCRIPT.parent / 'judge.py'), 'ask', '--site', 'away-decision',
         '--question', 'Which schema fits the spec settings?', '--option', 'Keep one schema', '--option', 'Split it',
         '--evidence-file', '.finolabs/briefs/packet.json']
BRIEF = 'Choose one option for the config question.\n1 Keep one schema\n2 Split it\nReply with the number and a reason.'
ENV = ['python3', '-I', str(SCRIPT.parent / 'delegate_env.py')]
# Each form ends its options with a literal `--` right before the brief where the program's parser takes one.
CODEX = ENV + ['--family', 'codex', '--', 'codex', 'exec', '-m', 'gpt-5.5', '-c', 'model_reasoning_effort=high',
               '-s', 'read-only', '--', BRIEF]
CLAUDE = ENV + ['--family', 'claude', '--', 'claude', '-p', '--model', 'claude-opus-5-5',
                '--output-format', 'json', '--permission-mode', 'plan', '--', BRIEF]
AGY = ENV + ['--family', 'antigravity', '--', 'agy', '-p', BRIEF, '--model', 'gemini-4-argon', '--mode', 'plan',
             '--output-format', 'json']
SETUP_ALL = SETUP.replace('Claude Code', 'Claude Code, Codex, Antigravity') + '- Max actions per hour: 1000\n'
DANGER = {'codex': '--dangerously-bypass-approvals-and-sandbox', 'claude': '--dangerously-skip-permissions',
          'antigravity': '--yolo'}


class AwayDecisionTest(AutopilotBase):
    """Away decisions, scripts part: decision records, reviews, categories, the two ladder forms and the packet check."""

    def ledger(self):
        path = self.root / 'ledger.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def decide(self, *flags, project='demo', topic='schema choice', precedents='1'):
        return self.invoke('log', '--kind', 'decision', '--project', project, '--topic', topic,
                           '--precedents', precedents, *flags)

    def recorded(self, *flags, **kwargs):
        before = len(self.ledger())
        status, output = self.decide(*flags, **kwargs)
        self.assertEqual(status, 0, output)
        identifier = output.splitlines()[0]
        self.assertRegex(identifier, DECISION.pattern + '$')
        lines = self.ledger()
        self.assertEqual(len(lines), before + 1)
        return identifier, lines[-1]

    def refused(self, *flags, **kwargs):
        before = self.ledger()
        status, output = self.decide(*flags, **kwargs)
        self.assertEqual(status, 3, output)
        self.assertEqual(self.ledger(), before)

    def check_as(self, argv, coordinator='claude', tier=1, code='allowed'):
        flags = ('--coordinator', coordinator) if coordinator else ()
        status, output = self.invoke('check', *flags, '--argv-json', json.dumps(argv))
        self.assertEqual(status, 0, output)
        result = json.loads(output)
        if code is None:  # any Tier 3 code: a checkout under a protected folder may say `protected` first
            self.assertEqual(result['tier'], 3, argv)
        else:
            self.assertEqual(result, {'tier': tier, 'code': code}, argv)

    # Record for analysis

    def test_every_row_of_the_attempt_schema_records_its_fields_and_nothing_else(self):
        self.start()
        lease_start = self.lease()['start']
        for name, (flags, stored) in ROWS.items():
            with self.subTest(row=name):
                identifier, line = self.recorded(*flags)
                rung, settled = flags[1], flags[3]
                self.assertEqual(line, dict(event='decision', id=identifier, ts=line['ts'], project='demo',
                                            lease_start=lease_start, rung=rung, settled=settled, precedents=1,
                                            topic='schema choice', **stored))
                self.assertRegex(line['ts'], r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T')

    def test_every_row_refuses_each_unlisted_field_and_each_missing_required_field(self):
        self.start()
        optional = {'advisor unavailable, selected': {'--dispatch'}}
        for name, (flags, stored) in ROWS.items():
            given = {flags[i] for i in range(4, len(flags), 2)}
            for flag, value in EXTRA.items():
                if flag in given or flag in optional.get(name, set()):
                    continue
                if name == 'advisor unavailable, no candidate' and flag == '--by':
                    continue  # adding the advisor is the valid row "an advisor was selected"
                with self.subTest(row=name, extra=flag):
                    self.refused(*flags, flag, value)
            required = given - optional.get(name, set()) - ({'--dispatch'} if name.endswith('and started') else set())
            if name.startswith('advisor unavailable, selected'):
                required.discard('--by')  # without the advisor it is the valid row "no candidate"
                if name.endswith('and started'):
                    self.refused(*flags[:4], '--dispatch', DISPATCH)  # but a dispatch needs its advisor
            for flag in required:
                index = flags.index(flag)
                with self.subTest(row=name, missing=flag):
                    self.refused(*(flags[:index] + flags[index + 2:]))

    def test_values_combinations_and_common_fields_are_closed(self):
        self.start()
        for flags in (('--rung', 'rule', '--settled', 'unavailable', '--by', 'rule'),
                      ('--rung', 'host', '--settled', 'no', '--by', 'claude', '--model', 'm'),
                      ('--rung', 'park', '--settled', 'no', '--by', 'claude'),
                      ('--rung', 'user', '--settled', 'yes', '--by', 'claude'),
                      ('--rung', 'rule', '--settled', 'yes', '--by', 'jev', '--option', '1', '--of', '2'),
                      ('--rung', 'jev', '--settled', 'yes', '--by', 'jev', '--option', '1', '--of', '2', '--probability', '0.5'),
                      ('--rung', 'jev', '--settled', 'no', '--by', 'jev', '--probability', '0.9'),
                      ('--rung', 'jev', '--settled', 'no', '--by', 'jev', '--probability', 'nan'),
                      ('--rung', 'jev', '--settled', 'no', '--by', 'jev', '--probability', '1.5'),
                      ('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '3', '--of', '2'),
                      ('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '1', '--of', '7'),
                      ('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '1', '--of', '1'),
                      ('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '0', '--of', '2'),
                      ('--rung', 'advisor', '--settled', 'no', '--by', '../x', '--dispatch', DISPATCH, '--model', 'm'),
                      ('--rung', 'advisor', '--settled', 'no', '--by', 'codex', '--dispatch', 'bad', '--model', 'm'),
                      ('--rung', 'advisor', '--settled', 'no', '--by', 'codex', '--dispatch', DISPATCH, '--model', 'a b'),
                      ('--rung', 'host', '--settled', 'yes', '--by', 'gemini', '--option', '1', '--of', '2', '--model', 'm'),
                      ('--rung', 'host', '--settled', 'yes', '--by', 'codexwork', '--option', '1', '--of', '2', '--model', 'm'),
                      ('--rung', 'park', '--settled', 'yes', '--by', 'rule')):
            with self.subTest(flags=flags):
                self.refused(*flags)
        park = ROWS['park yes'][0]
        for kwargs in (dict(precedents='-1'), dict(precedents='9'), dict(precedents='x'), dict(topic=''),
                       dict(topic='   '), dict(topic='a' * 61), dict(topic='src/private.py'), dict(topic='ghp_' + 'x' * 30),
                       dict(topic='line\nbreak'), dict(project='../demo'), dict(project='')):
            with self.subTest(**kwargs):
                self.refused(*park, **kwargs)
        # Decision fields belong to the decision kind only, and a decision needs its common fields.
        self.assertEqual(self.invoke('log', '--kind', 'action', '--rung', 'park')[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'decision', *park)[0], 3)

    def test_a_judge_probability_round_trips_unchanged_and_the_threshold_holds(self):
        self.start()
        # The value judge.ask_choice returns, passed on as Python prints it, is stored as that same number.
        for p, settled in ((0.823456789, 'yes'), (0.8, 'yes'), (1.0, 'yes'), (0.7999999999999999, 'no'),
                           (1 / 3, 'no'), (0.5, 'no')):
            with self.subTest(p=p):
                flags = (('--rung', 'jev', '--settled', settled, '--by', 'jev', '--probability', str(p))
                         + (('--option', '1', '--of', '2') if settled == 'yes' else ()))
                _, line = self.recorded(*flags)
                self.assertEqual(line['probability'], p)
                self.assertIs(type(line['probability']), float)
        # The judge's own output, with the provider call stubbed (no network), reaches the record unchanged.
        self.load()
        import judge
        spread = {'1': 0.823456789, '2': 0.176543211}
        with patch.object(judge, 'configured_judge', return_value='jev'), patch.object(judge, 'post', return_value=spread), \
                patch.dict(os.environ, {'FNL_JUDGE': 'on'}):
            answer = judge.ask_choice('Which schema fits the spec?', ['Keep one schema', 'Split it'], 'Goal: one schema.')
        self.assertTrue(answer['settled'])
        _, line = self.recorded('--rung', 'jev', '--settled', 'yes', '--by', 'jev', '--option', str(answer['option']),
                                '--of', str(answer['of']), '--probability', str(answer['p']))
        self.assertEqual((line['option'], line['of'], line['probability']), (1, 2, answer['p']))
        # Just below 0.8 cannot settle, and 0.8 or above cannot be recorded as not settling.
        for p, settled in (('0.7999999999999999', 'yes'), ('0.79999', 'yes'), ('0.823456789', 'no')):
            with self.subTest(p=p, settled=settled):
                self.refused('--rung', 'jev', '--settled', settled, '--by', 'jev', '--probability', p,
                             *(('--option', '1', '--of', '2') if settled == 'yes' else ()))
        # Anything that is not a bounded plain number in 0..1 is refused.
        for p in ('nan', 'inf', '-0.1', '1.0000001', '1e400', '0x1', '0.5 ', ' 0.5', '0.' + '5' * 40, '', '.5', '1_0', '8e-1'):
            with self.subTest(p=p):
                self.refused('--rung', 'jev', '--settled', 'no', '--by', 'jev', '--probability', p)

    def test_the_id_is_generated_once_and_later_attempts_must_pass_an_existing_one(self):
        self.start()
        first, line = self.recorded(*ROWS['jev unavailable'][0])
        second, line = self.recorded(*ROWS['advisor yes'][0], '--decision', first)
        self.assertEqual((second, line['id']), (first, first))
        self.refused(*ROWS['host yes'][0], '--decision', 'q20261110-010203-ffff')  # unknown id
        self.refused(*ROWS['host yes'][0], '--decision', 'd20261110-010203-abcd')  # not a decision id
        other, _ = self.recorded(*ROWS['park yes'][0])
        self.assertNotEqual(other, first)

    def test_a_decision_needs_a_lease_and_the_autopilot_log_keeps_only_a_redacted_note(self):
        self.setup_config()
        self.refused(*ROWS['park yes'][0])
        self.start()
        identifier, _ = self.recorded(*ROWS['park yes'][0], '--note', 'Parked: git push origin main reaches production')
        record = json.loads((self.state / 'log.jsonl').read_text().splitlines()[-1])
        self.assertEqual((record['kind'], record['decision'], record['tier']), ('decision', identifier, 2))
        self.assertNotIn('git push', record['note'])
        self.assertNotIn('note', self.ledger()[-1])

    def test_outcomes_table_and_ladder_cases_share_one_decision_id(self):
        self.start()
        cases = {
            'jev not configured or options open': ['advisor yes'],
            'jev refuses, times out or fails': ['jev unavailable', 'advisor yes'],
            'jev below 0.8': ['jev no', 'advisor yes'],
            'host-only hosts, no advisor': ['jev unavailable', 'advisor unavailable, no candidate', 'host yes'],
            'advisor out of quota or failed': ['advisor unavailable, selected and started', 'host yes'],
            'advisor answers none': ['advisor no', 'host yes'],
            'advisor names an option outside the list': ['advisor no', 'host yes'],
            'a new fact at the same rung': ['advisor yes', 'advisor yes'],
            'a new fact and the answer does not hold': ['advisor yes', 'advisor no', 'host yes'],
            'a rule invalidated by new evidence': ['rule yes', 'rule no', 'host yes'],
            'where it must stop': ['park yes'],
            'a rung answered, then the check parked it': ['jev yes', 'park yes'],
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                before = len(self.ledger())
                identifier, _ = self.recorded(*ROWS[rows[0]][0], precedents='0')
                for row in rows[1:]:
                    self.recorded(*ROWS[row][0], '--decision', identifier, precedents='0')
                lines = self.ledger()[before:]
                self.assertEqual({line['id'] for line in lines}, {identifier})
                self.assertEqual([(line['rung'], line['settled']) for line in lines],
                                 [tuple(ROWS[row][0][1:4:2]) for row in rows])
                self.assertEqual({line['precedents'] for line in lines}, {0})

    def test_review_records_kept_or_reversed_for_an_existing_decision_only(self):
        self.start()
        identifier, _ = self.recorded(*ROWS['host yes'][0])
        self.assertEqual(self.invoke('stop')[0], 0)  # reviews happen after the user returns
        for verdict in ('kept', 'reversed'):
            status, output = self.invoke('review', '--decision', identifier, verdict)
            self.assertEqual(status, 0, output)
            line = self.ledger()[-1]
            self.assertEqual(line, dict(event='decision_review', id=identifier, ts=line['ts'], verdict=verdict))
        before = self.ledger()
        for identifier in ('q20261110-010203-ffff', 'bad'):
            self.assertEqual(self.invoke('review', '--decision', identifier, 'kept')[0], 3)
        self.assertEqual(self.ledger(), before)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke('review', '--decision', identifier, 'maybe')

    # Where it must stop

    def test_category_settings_fixed_rows_unknown_values_consent_and_targets(self):
        ap = self.load()
        self.setup_config()
        applied = ap.settings()
        for category in ap.CATEGORIES:
            self.assertEqual(applied[category], 'stop', category)  # missing is stop, even for decide-default rows
        self.assertEqual((applied['Excerpts leave the machine'], applied['Non-production targets']), ('no', []))
        self.setup_config(SETUP + '- Production: decide\n- Real users and customer data: decide\n'
                          '- Tags and releases: decide\n- Publishing: maybe\n- Recoverable deletion: decide\n'
                          '- Excerpts leave the machine: Yes\n'
                          '- Non-production targets: npx wrangler deploy --env uat; make deploy-dev\n')
        applied = ap.settings()
        self.assertEqual((applied['Production'], applied['Real users and customer data']), ('stop', 'stop'))
        self.assertEqual((applied['Tags and releases'], applied['Publishing'], applied['Recoverable deletion']),
                         ('decide', 'stop', 'decide'))
        self.assertEqual(applied['Excerpts leave the machine'], 'no')
        self.assertEqual(applied['Non-production targets'], ['npx wrangler deploy --env uat', 'make deploy-dev'])
        self.setup_config(SETUP + '- Excerpts leave the machine: yes\n- Non-production targets: ok; \x07bad\n')
        applied = ap.settings()
        self.assertEqual((applied['Excerpts leave the machine'], applied['Non-production targets']), ('yes', []))
        self.assertTrue(ap.permits({'Tags and releases'}, dict(applied, **{'Tags and releases': 'decide'})))
        self.assertFalse(ap.permits({'Tags and releases', 'Publishing'},
                                    dict(applied, **{'Tags and releases': 'decide', 'Publishing': 'stop'})))
        self.assertFalse(ap.permits({'Tags and releases'}, {}))
        self.assertFalse(ap.permits(set(), applied))

    def test_precedence_table_rows_and_examples(self):
        targets = '- Non-production targets: npx wrangler deploy --env uat; npx wrangler deploy --env production\n'
        self.start(SETUP + '- Max actions per hour: 1000\n' + targets)
        # Row 3: tags, releases and publishing stay Tier 3 while their category is stop, missing or invalid.
        for argv in (['git', 'tag', 'v1.2.0'], ['gh', 'release', 'create', 'v1.2.0'], ['npm', 'publish']):
            self.check(argv, tier=3, code='forbidden')
        # Row 5: a listed deploy goes on (a listed UAT run).
        self.check(['npx', 'wrangler', 'deploy', '--env', 'uat'])
        # Row 2: production parks even when listed by mistake; row 4: an unlisted or changed deploy parks.
        for argv in (['npx', 'wrangler', 'deploy', '--env', 'production'], ['npx', 'wrangler', 'deploy', '--env', 'uat2'],
                     ['npx', 'wrangler', 'deploy', '--env', 'uat', '--minify'], ['npx', 'wrangler', 'deploy'],
                     ['npx', 'wrangler', 'deploy', '--env', 'live']):
            self.check(argv, tier=3, code='forbidden')
        # Row 1: credentials or the agent's own limits win over every listed target.
        self.check(['npx', 'wrangler', 'deploy', '--env', 'uat', '--var', 'API_TOKEN'], tier=3, code='protected')
        # Row 6: local work no category names is classified as today.
        self.check(['git', 'status'])

    def test_decide_categories_open_only_the_closed_tag_release_and_publish_forms(self):
        self.start(SETUP + '- Max actions per hour: 1000\n- Tags and releases: decide\n- Publishing: decide\n')
        for argv in (['git', 'tag', 'v1.2.0'], ['git', 'tag', '-a', 'v1.2.0', '-m', 'Release 1.2.0'],
                     ['git', 'tag', 'v1.2.0', 'a' * 40], ['gh', 'release', 'create', 'v1.2.0', '--title', 'v1.2.0',
                                                          '--notes', 'Changes', '--verify-tag'],
                     ['gh', 'release', 'view', 'v1.2.0'], ['gh', 'release', 'list'], ['npm', 'publish'],
                     ['npm', 'publish', '--access', 'public'], ['pnpm', 'publish', '--tag', 'next']):
            with self.subTest(argv=argv):
                self.check(argv)
        for argv in (['git', 'tag', '-d', 'v1.2.0'], ['git', 'tag', '-f', 'v1.2.0'], ['git', 'tag', '--delete', 'v1'],
                     ['gh', 'release', 'delete', 'v1.2.0'], ['gh', 'release', 'upload', 'v1.2.0', 'dist/x.zip'],
                     ['npm', 'publish', '--registry', 'https://example.invalid'], ['npm', 'unpublish'],
                     ['git', 'push', 'origin', 'refs/tags/v1.2.0'], ['twine', 'upload', 'dist/x'],
                     ['npx', 'wrangler', 'deploy', '--env', 'uat']):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code='unknown' if argv[0] == 'twine' or 'unpublish' in argv else 'forbidden')
        # Recursive deletion keeps its Tier 3 classification in this slice.
        self.check(['rm', '-rf', 'build'], tier=3, code='forbidden')

    def test_categories_come_from_the_command_not_from_its_free_text(self):
        base = SETUP + '- Max actions per hour: 1000\n'
        tag = (['gh', 'release', 'create', 'v1', '--notes', 'publish'], ['git', 'tag', '-a', 'v1', '-m', 'publish'],
               ['git', 'tag', '-a', 'v1', '-m', 'deploy'], ['gh', 'release', 'create', 'v1', '--title', 'deploy:uat'])
        publish = (['npm', 'publish', '--tag', 'next'], ['pnpm', 'publish', '--access', 'public'])
        local = (['git', 'commit', '-m', 'publish'], ['gh', 'pr', 'create', '--title', 'deploy', '--body', 'publish'],
                 ['git', 'commit', '-m', 'deploy'])
        # Tags and releases stop, Publishing decide: free text naming publishing opens no tag or release.
        self.start(base + '- Tags and releases: stop\n- Publishing: decide\n')
        for argv in tag:
            with self.subTest(setup='tags stop', argv=argv):
                self.check(argv, tier=3, code='forbidden')
        for argv in publish + local:
            with self.subTest(setup='tags stop', argv=argv):
                self.check(argv)
        # The reverse: tags and releases decide, Publishing stop.
        self.assertEqual(self.invoke('stop')[0], 0)
        self.start(base + '- Tags and releases: decide\n- Publishing: stop\n')
        for argv in tag + local:
            with self.subTest(setup='publishing stop', argv=argv):
                self.check(argv)
        for argv in publish:
            with self.subTest(setup='publishing stop', argv=argv):
                self.check(argv, tier=3, code='forbidden')

    # How the ladder's calls pass the action gate

    def test_the_judge_form_is_tier_one_under_a_live_lease_and_reserves_an_action(self):
        self.start(SETUP_AWAY)
        self.check_as(JUDGE)
        self.check_as(JUDGE + ['--option', 'Third', '--judge', 'jev'])
        self.assertEqual(self.lease()['counters']['actions'], 2)
        self.assertEqual(self.lease()['counters']['runs'], 0)

    def test_the_judge_form_denies_any_other_site_flag_shape_or_copy(self):
        self.start(SETUP_AWAY)
        site = JUDGE.index('away-decision')
        other = str(ROOT / 'skills/fnl-verification/scripts/judge.py')
        option = JUDGE.index('Split it')
        for argv in (JUDGE[:site] + ['navigator'] + JUDGE[site + 1:], JUDGE + ['--base-url', 'http://127.0.0.1:9'],
                     JUDGE + ['--dry-run'], JUDGE + ['--answers', 'docs/answers.json'],
                     JUDGE[:option - 1] + JUDGE[option + 1:],  # one option
                     JUDGE + [t for n in range(5) for t in ('--option', 'Extra %d' % n)],  # seven options
                     JUDGE[:option] + ['ghp_' + 'x' * 30] + JUDGE[option + 1:],
                     JUDGE[:option] + ['Keep one schema'] + JUDGE[option + 1:],  # duplicate option
                     JUDGE[:7] + ['Which file under /Us' + 'ers/synthetic/private?'] + JUDGE[8:],
                     JUDGE + ['--judge', 'host'], JUDGE + ['--site', 'away-decision'],
                     JUDGE[:-1] + ['../packet.json'], JUDGE[:-1] + ['.env'], JUDGE[:-1] + ['/tmp/packet.json'],
                     JUDGE[:-1] + ['.finolabs/briefs/packet.sh'],
                     JUDGE[:3] + ['check-host'] + JUDGE[4:], JUDGE[:3] + JUDGE[5:]):
            with self.subTest(argv=argv[3:6] + argv[-2:]):
                self.check_as(argv, tier=3, code='unknown')
        # Another copy of judge.py or a call without isolated Python is not the ladder form.
        for argv in (JUDGE[:2] + [other] + JUDGE[3:], ['python3'] + JUDGE[2:]):
            self.check_as(argv, tier=3, code=None)
        self.assertEqual(self.lease()['counters']['actions'], 0)

    def test_the_advisor_form_is_tier_one_for_another_family_in_hosts(self):
        self.start(SETUP_AWAY)
        self.check_as(CODEX)
        self.check_as(CODEX[:5] + ['--', 'perl', '-e', 'alarm 900; exec @ARGV'] + CODEX[6:])
        self.check_as(CODEX[:6] + ['/opt/tools/codex'] + CODEX[7:])
        self.check_as(CLAUDE, coordinator='codex')
        self.check_as(CLAUDE[:-2] + ['--effort', 'high', '--max-turns', '8', '--max-budget-usd', '2'] + CLAUDE[-2:],
                      coordinator='codex')
        self.assertEqual(self.lease()['counters']['actions'], 5)
        self.assertEqual(self.lease()['counters']['runs'], 0)  # the advisor's ledger start reserves its run, as today

    def test_the_advisor_form_denies_writes_other_families_programs_and_shapes(self):
        self.start(SETUP_AWAY)
        mode = CODEX.index('read-only')
        permission = CLAUDE.index('plan')
        for argv, coordinator in (
                (CODEX[:mode] + ['workspace-write'] + CODEX[mode + 1:], 'claude'),
                (CODEX[:mode] + ['danger-full-access'] + CODEX[mode + 1:], 'claude'),
                (CODEX[:-2] + ['--dangerously-bypass-approvals-and-sandbox', '--', BRIEF], 'claude'),
                (CODEX[:-2] + ['-o', 'docs/answer.md', '--', BRIEF], 'claude'),
                (CODEX[:-2] + ['--full-auto', '--', BRIEF], 'claude'),
                (CODEX[:6] + ['codex', 'review'] + CODEX[8:], 'claude'),
                (CLAUDE[:permission] + ['acceptEdits'] + CLAUDE[permission + 1:], 'codex'),
                (CLAUDE[:-2] + ['--allowedTools', 'Bash', '--', BRIEF], 'codex'),
                (CLAUDE[:-2] + ['--dangerously-skip-permissions', '--', BRIEF], 'codex'),
                (CLAUDE, 'claude'),  # the host's own family
                (CODEX, 'codex'),
                (CODEX, None),  # the coordinator's family must be stated
                (ENV + ['--family', 'antigravity', '--', 'agy', '-p', BRIEF, '--model', 'm', '--mode', 'plan',
                        '--output-format', 'json'], 'claude'),  # a family outside Hosts
                (CODEX[:6] + ['bash', '-c', 'codex'] + CODEX[9:], 'claude'),  # an unknown program
                (CODEX[:6] + ['./codex'] + CODEX[7:], 'claude'),
                (CODEX[:6] + [str(self.repo / 'tools/codex')] + CODEX[7:], 'claude'),
                (CODEX[:6] + ['claude'] + CODEX[7:], 'claude'),  # another family's program
                (CODEX[:5] + ['--', 'perl', '-e', 'system("x"); exec @ARGV'] + CODEX[6:], 'claude'),
                (CODEX[:5] + ['--claude-config-dir', '/opt/x', '--'] + CODEX[6:], 'claude'),
                (CODEX[:4] + ['claude'] + CODEX[5:], 'claude'),  # wrapper family differs from the program
                (CODEX[:-1] + ['ghp_' + 'x' * 30], 'claude'),  # a brief with a secret
                (CODEX[:-1], 'claude'),  # no brief
                (CODEX[:-2], 'claude'),  # no brief and no separator
                (['python3', '-I', str(ROOT / 'scripts/delegate_env.py')] + CODEX[3:], 'claude'),
                (['python3'] + CODEX[2:], 'claude')):
            with self.subTest(argv=argv[3:9], coordinator=coordinator):
                self.check_as(argv, coordinator=coordinator, tier=3, code='unknown')
        self.assertEqual(self.lease()['counters']['actions'], 0)

    def test_the_brief_position_never_accepts_an_option(self):
        self.start(SETUP_ALL)
        forms = {'codex': (CODEX, 'claude'), 'claude': (CLAUDE, 'codex'), 'antigravity': (AGY, 'claude')}
        for family, (form, coordinator) in forms.items():
            danger = DANGER[family]
            brief = form.index(BRIEF)
            shapes = {
                'dangerous flag as the brief': form[:brief] + [danger] + form[brief + 1:],
                'stdin as the brief': form[:brief] + ['-'] + form[brief + 1:],
                'brief starting with a dash': form[:brief] + ['-x ' + BRIEF] + form[brief + 1:],
                'dangerous flag as the final token': form + [danger],
                'dangerous flag after the brief': form + [danger, BRIEF],
            }
            if family == 'codex':  # the reviewed shape: the last token became the brief, with no separator
                shapes['old form, dangerous flag last'] = CODEX[:-2] + [danger]
                shapes['old form, stdin'] = CODEX[:-2] + ['-']
                shapes['old form'] = CODEX[:-2] + [BRIEF]
                shapes['flag before the brief'] = CODEX[:-2] + [danger, '--', BRIEF]
            if family == 'claude':  # -p is a switch; the brief is the positional prompt after `--`
                shapes['old form, dangerous flag as prompt'] = CLAUDE[:8] + [danger] + CLAUDE[8:-2]
                shapes['old form, stdin'] = CLAUDE[:8] + ['-'] + CLAUDE[8:-2]
                shapes['old form'] = CLAUDE[:8] + [BRIEF] + CLAUDE[8:-2]
                shapes['flag before the brief'] = CLAUDE[:-2] + [danger, '--', BRIEF]
            if family == 'antigravity':  # the brief is the value of -p
                shapes['flag before the brief'] = AGY[:7] + [danger] + AGY[7:]
                shapes['separator then brief'] = AGY[:8] + AGY[9:] + ['--', BRIEF]
            for name, argv in shapes.items():
                with self.subTest(family=family, shape=name):
                    self.check_as(argv, coordinator=coordinator, tier=3, code='unknown')
        self.assertEqual(self.lease()['counters']['actions'], 0)
        for form, coordinator in forms.values():
            self.check_as(form, coordinator=coordinator)

    def test_the_advisor_brief_is_screened_like_the_judge_and_packet_paths(self):
        self.start(SETUP_AWAY)
        home = '/Us' + 'ers/synthetic'
        # A sensitive name with any assigned value, however short, and any machine path deny.
        for brief in ('Use db_password=fixture123 in the fixture.', 'Set API_TOKEN=ab and continue.',
                      'The test sets secret: x1 first.', "Config has auth_token = 'q'.", 'export PASSWORD=1',
                      'Read ' + home + '/notes.md first.', 'See ~/private/notes.', 'Look in /home/synthetic/x.',
                      'Open C:\\work\\x.txt.', BRIEF + '\nsession_cookie=abc'):
            with self.subTest(brief=brief):
                self.check_as(CODEX[:-1] + [brief], tier=3, code='unknown')
        self.assertEqual(self.lease()['counters']['actions'], 0)
        # Discussing configuration without an assigned value stays possible.
        for brief in ('Should the db password setting move to the vault, or stay in the env file?',
                      'Rotate the API key before the release, or after it?',
                      'Choose: keep the token cache, or drop it.', BRIEF):
            with self.subTest(brief=brief):
                self.check_as(CODEX[:-1] + [brief])

    def test_both_forms_deny_without_a_live_lease(self):
        self.setup_config(SETUP_AWAY)
        self.check_as(JUDGE, tier=3, code='no-lease')
        self.check_as(CODEX, tier=3, code='no-lease')

    # The precedent packet

    def packet(self, excerpts, goal='Ship the parser with one schema, as the spec says.'):
        path = self.home / 'packet.json'
        path.write_text(json.dumps({'goal': goal, 'excerpts': excerpts}))
        return path

    def excerpt(self, n, text=None):
        return {'decision': text or 'Chose one table for settings (%d)' % n, 'date': '2026-11-0%d' % (n % 9 + 1),
                'source': 'decisions/schema-%d' % n}

    def test_packet_check_caps_drops_and_counts(self):
        self.setup_config(SETUP + '- Excerpts leave the machine: yes\n')
        status, output = self.invoke('packet-check', '--file', str(self.packet([self.excerpt(n) for n in range(8)])))
        self.assertEqual(status, 0, output)
        self.assertEqual((len(json.loads(output)['excerpts']), json.loads(output)['dropped']), (8, 0))
        secret, path = 'ghp_' + 'x' * 30, '/Us' + 'ers/synthetic/notes'
        excerpts = [self.excerpt(n) for n in range(4)] + [self.excerpt(5, 'Kept key ' + secret), self.excerpt(6, 'See ' + path)]
        excerpts.append(dict(self.excerpt(7), source='~/private/notes'))
        status, output = self.invoke('packet-check', '--file', str(self.packet(excerpts)))
        self.assertEqual(status, 0, output)
        cleaned = json.loads(output)
        self.assertEqual((len(cleaned['excerpts']), cleaned['dropped']), (4, 3))
        for value in (secret, path, '~/private'):
            self.assertNotIn(value, output)
        for excerpts in ([self.excerpt(n) for n in range(9)], [self.excerpt(n, 'x' * 1100) for n in range(8)],
                         [dict(self.excerpt(1), extra='x')], [dict(self.excerpt(1), date='yesterday')],
                         [{'decision': 'Only text'}]):
            with self.subTest(count=len(excerpts)):
                self.assertEqual(self.invoke('packet-check', '--file', str(self.packet(excerpts)))[0], 3)
        self.assertEqual(self.invoke('packet-check', '--file', str(self.packet([], goal='Use ' + secret)))[0], 3)
        self.assertEqual(self.invoke('packet-check', '--file', str(self.home / 'missing.json'))[0], 3)

    def test_packet_check_without_consent_lets_no_excerpt_leave(self):
        self.setup_config()
        self.assertEqual(self.invoke('packet-check', '--file', str(self.packet([self.excerpt(1)])))[0], 3)
        status, output = self.invoke('packet-check', '--file', str(self.packet([])))
        self.assertEqual(status, 0, output)
        self.assertEqual(json.loads(output)['excerpts'], [])


if __name__ == '__main__':
    unittest.main()
