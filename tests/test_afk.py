"""Synthetic, offline afk lease and classification tests."""
import contextlib
import hashlib
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
SCRIPT = ROOT / 'skills/delegate/scripts/afk.py'
SETUP = ('## afk\n- Hosts: Claude Code\n- Task choice: choose\n'
         '- Push and pull requests: yes\n- Merge: yes\n- Trusted authors: own\n')
ORIGIN_CONFIG = ('[core]\n\trepositoryformatversion = 0\n\tbare = false\n'
                 '[remote "origin"]\n\turl = https://github.com/example/demo.git\n'
                 '\tfetch = +refs/heads/*:refs/remotes/origin/*\n')


# An ended or exhausted lease tells the caller, in one fixed line, to stop any loop it started for the lease.
ENDED_CODES = {'no-lease', 'expired', 'stopped', 'setup-changed'}
ENDED_LINE = 'The away lease has ended: stop any loop or wakeup you started for it, then report to the user.'

class AfkBase(unittest.TestCase):
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
        (self.repo / '.git/config').write_text(ORIGIN_CONFIG)
        self.cwd = self.repo
        self.clock = 1800000000

    def load(self):
        self.assertTrue(SCRIPT.exists(), 'afk lease/classifier has not been implemented')
        spec = importlib.util.spec_from_file_location('afk_tested', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def setup_config(self, text=SETUP):
        (self.root / 'host.md').write_text(text)
        (self.root / 'host.md').chmod(0o600)

    def invoke(self, *argv):
        ap = self.load()
        with patch.object(ap, 'now', return_value=self.clock), patch('os.getcwd', return_value=str(self.cwd)):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = ap.main(list(argv))
        return status, out.getvalue()

    @property
    def state(self):
        return self.root / 'state/autopilot'

    def lease(self):
        return json.loads((self.state / 'lease.json').read_text())

    def counts(self):
        """The counters of the one project this test's checks ran in (zeros before any reserved action)."""
        table = self.lease()['counters']
        self.assertLessEqual(len(table), 1, table)
        return next(iter(table.values()), dict(runs=0, actions=0, hour_actions=[], first=None))

    def change_counts(self, **values):
        """Set counters of the one project entry, creating it from a first reserved action when absent."""
        if not self.lease()['counters']:
            self.check(['git', 'status'])
        self.change_lease(lambda v: next(iter(v['counters'].values())).update(values))

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
        self.assertEqual(status, 0 if tier == 1 else 3, output)  # a denied check never exits 0
        expected = {'tier': tier, 'code': code}
        if code in ENDED_CODES:
            expected['end'] = ENDED_LINE
        self.assertEqual(json.loads(output), expected)


class AfkTest(AfkBase):
    def test_start_requires_setup_and_merge(self):
        for text in ('', '## Other\n', SETUP.replace('- Merge: yes\n', '')):
            self.setup_config(text)
            status, output = self.invoke('start')
            self.assertEqual(status, 3, output)
            self.assertFalse((self.state / 'lease.json').exists())

    def test_only_the_afk_heading_is_read_never_the_old_autopilot_heading(self):
        old = SETUP.replace('## afk\n', '## Autopilot\n')
        for text in (old, '## Autopilot\n- Merge: yes\n'):
            self.setup_config(text)
            status, output = self.invoke('start')
            self.assertEqual(status, 3, output)
            self.assertFalse((self.state / 'lease.json').exists())
        # Beside a leftover old section, the new one is read and the old one ignored.
        self.setup_config('## Autopilot\n- Merge: perhaps\n- Lease hours: 99\n\n' + SETUP)
        status, summary = self.invoke('start')
        self.assertEqual(status, 0, summary)
        self.assertIn('Merge: yes', summary)
        self.assertIn('Lease hours: 8', summary)

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
        before = (self.state / 'lease.json').read_bytes()
        status, joined = self.invoke('start')
        self.assertEqual(status, 0, joined)  # a second session joins the machine-wide lease instead of failing
        self.assertIn('afk already live until ', joined)
        self.assertIn('covers every session on this machine', joined)
        self.assertEqual((self.state / 'lease.json').read_bytes(), before)  # nothing extended or reset
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
                     SETUP.replace('choose', 'anything'), SETUP + '## afk\n- Merge: yes\n'):
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
        self.change_counts(runs=20)
        self.check(['git', 'status'], tier=3, code='spent')
        self.change_counts(runs=0, first=self.clock - 480 * 60)
        self.check(['git', 'status'], tier=3, code='spent')
        self.change_counts(first=self.clock, hour_actions=[self.clock] * 30)
        self.check(['git', 'status'], tier=3, code='limit')
        self.clock += 3601
        self.check(['git', 'status'])
        self.assertEqual(self.counts()['actions'], 2)

    def test_runtime_limit_uses_elapsed_time_since_the_projects_first_action(self):
        self.start(SETUP + '- Max runtime minutes: 10\n')
        self.clock += 600
        self.check(['git', 'status'])  # the project's clock starts at its first reserved action
        self.clock += 600
        self.check(['git', 'status'], tier=3, code='spent')

    def test_tier_one_commands_and_paths(self):
        self.start(SETUP + '- Max actions per hour: 100\n')
        for argv in (['git', 'status', '--short'], ['git', 'log', '-5', '--oneline'],
                     ['git', 'diff', '--stat', 'origin/main...HEAD'], ['git', 'show', '--stat', 'HEAD'],
                     ['git', 'rev-parse', 'HEAD'], ['git', 'branch', '--show-current'],
                     ['git', 'add', '--', 'src/example.py', 'tests/test_example.py'],
                     ['git', 'commit', '-m', 'Fix example'], ['git', 'push', '-u', 'origin', 'HEAD:refs/heads/topic'],
                     ['git', 'merge', 'origin/main'], ['gh', 'pr', 'view', '7', '--json', 'headRefOid'],
                     ['gh', 'pr', 'checks', '7'],
                     ['gh', 'pr', 'create', '--title', 'Example', '--body', 'Details', '--head', 'topic',
                      '--repo', 'github.com/example/demo'],
                     ['gh', 'pr', 'edit', '7', '--title', 'Example', '--repo', 'github.com/example/demo'],
                     ['gh', 'issue', 'list'],
                     ['gh', 'pr', 'merge', '7', '--squash', '--match-head-commit', 'a' * 40,
                      '--repo', 'github.com/example/demo']):
            with self.subTest(argv=argv):
                self.check(argv)
        for name in ('ledger.py', 'record.py'):
            self.check(['python3', '-I', str(SCRIPT.parent / name), 'start' if name == 'ledger.py' else 'run'])
        self.check(['python3', '-I', str(SCRIPT.parent / 'heavy_run.py'), 'run', '--label', 'tests', '--', 'gh', 'pr', 'view', '7'])
        self.check(['python3', '-I', str(ROOT / 'skills/review-gate/scripts/merge_check.py'), '7', '--independent'])
        self.check(paths=['src/example.py', 'tests/test_example.py', 'docs/guide.md'])
        self.assertEqual(self.counts()['runs'], 1)

    def test_install_under_a_dot_claude_folder_keeps_its_own_wrappers(self):
        # Plugins install under ~/.claude/plugins or ~/.codex; the install path itself must not make
        # this install's own wrapper scripts protected, while any other .claude token still is.
        import shutil
        install = self.home / '.claude/plugins/cache/example/plugin/1.0.0/skills'
        for skill in ('delegate', 'review-gate'):
            shutil.copytree(ROOT / 'skills' / skill / 'scripts', install / skill / 'scripts')
        global SCRIPT
        saved, SCRIPT = SCRIPT, install / 'delegate/scripts/afk.py'
        try:
            self.start()
            own = install / 'delegate/scripts'
            self.check(['python3', '-I', str(own / 'ledger.py'), 'start'])
            self.check(['python3', '-I', str(own / 'heavy_run.py'), 'run', '--label', 'tests', '--', 'gh', 'pr', 'view', '7'])
            self.check(['python3', '-I', str(install / 'review-gate/scripts/merge_check.py'), '7', '--independent'])
            self.check(['python3', '-I', str(own / 'heavy_run.py'), 'run', '--', 'rm', '-rf', 'temp'], tier=3, code='forbidden')
            self.check(['python3', '-I', str(own / 'ledger.py'), 'start', '--note', '.claude'], tier=3, code='protected')
            self.check(['python3', '-I', str(own / 'heavy_run.py'), 'run', '--', 'cat', str(own / 'ledger.py')], tier=3, code='protected')
            self.check(['python3', '-I', str(own / 'other.py')], tier=3, code='protected')
        finally:
            SCRIPT = saved

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
        self.assertEqual(self.counts()['actions'], 0)

    def test_paths_fail_closed(self):
        self.start()
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')  # source paths are known on a work branch only
        for path in ('.github/workflows/check.yml', 'src/.github/settings.json', 'hooks/check.py',
                     'src/pre-commit', 'CLAUDE.md', 'docs/AGENTS.md', 'GEMINI.md',
                     'src/settings.json', 'host.md', 'state/autopilot/lease.json', 'setup.json',
                     '.env.local', 'src/secret.key', '.ssh/id_rsa', 'unknown/file.py', '../src/example.py',
                     '/tmp/example.py', 'skills/example/SKILL.md',
                     'skills/delegate/scripts/afk.py', 'skills/review-gate/scripts/merge_check.py'):
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
        # Instruction files and review enforcers are protected wherever they live (on the default branch).
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')
        for path in ('docs/CONVENTIONS.md', 'docs/copilot-instructions.md', 'skills/review-gate/scripts/review_route.py'):
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
        # Every trusted wrapper and its dependencies are protected as paths and through git add on the default branch.
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')
        for name in ('heavy_run.py', 'ledger.py', 'record.py', 'delegate_env.py', 'run_env.py', 'data_root.py', 'assignments.py'):
            path = 'skills/delegate/scripts/' + name
            self.check(paths=[path], tier=3, code='protected')
            self.check(['git', 'add', '--', path], tier=3, code='protected')
        self.check(paths=['skills/review-gate/scripts/merge_check.py'], tier=3, code='protected')
        # Case aliases name the same file on a case-insensitive filesystem.
        for name in ('Heavy_run.py', 'LEDGER.py', 'Run_env.py', 'Data_Root.py', 'Merge_Check.py'):
            path = 'skills/delegate/scripts/' + name
            self.check(paths=[path], tier=3, code='protected')
            self.check(['git', 'add', '--', path], tier=3, code='protected')

    def test_review_findings_security_one(self):
        self.start()
        self.repo = self.cwd = ROOT  # the checkout whose scripts are the installed wrappers
        # New modules next to the trusted wrappers could shadow an import in them, so the folders are protected.
        for folder in ('review-gate', 'delegate', 'setup'):
            for name in ('struct.py', 'zlib.py', 'helper.py', 'pkg/__init__.py'):
                path = 'skills/%s/scripts/%s' % (folder, name)
                self.check(paths=[path], tier=3, code='protected')
                self.check(['git', 'add', '--', path], tier=3, code='protected')

    def test_linked_sibling_skill_folders_are_protected_by_target_and_wrapper_refused(self):
        # A synthetic install whose review-gate skill is a link to another checkout.
        install = self.home / 'install/skills'
        (install / 'delegate/scripts').mkdir(parents=True)
        checkout = self.home / 'other/skills/review-gate/scripts'
        checkout.mkdir(parents=True)
        (checkout / 'merge_check.py').write_text('# synthetic')
        (install / 'review-gate').symlink_to(self.home / 'other/skills/review-gate')
        ap = self.load()
        copy = install / 'delegate/scripts/afk.py'
        copy.write_text(SCRIPT.read_text())
        spec = importlib.util.spec_from_file_location('afk_linked', copy)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch('os.getcwd', return_value=str(self.home / 'other')):
            self.assertTrue(module.plugin_code('skills/review-gate/scripts/difflib.py'))
        applied = dict(module.DEFAULTS, Merge='yes')
        wrapper = ['python3', '-I', str(install / 'review-gate/scripts/merge_check.py'), '7', '--independent']
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
            self.assertEqual(status, 3, output)
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


class AwayDecisionTest(AfkBase):
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

    def record_programs(self, folder=None, programs=None):
        """The canonical `## Quota probe` record setup writes, for synthetic native programs in a temporary folder."""
        folder = folder or self.home / 'bin'
        folder.mkdir(mode=0o700, exist_ok=True)
        self.load()  # puts the script folder on sys.path
        import quota_probe
        excluded = quota_probe.excluded
        # The temporary folder sits under the system temporary root, which the probe excludes; keep every other check.
        patcher = patch.object(quota_probe, 'excluded',
                               side_effect=lambda path: excluded(path) if 'downloads' in str(path).lower() else None)
        patcher.start()
        self.addCleanup(patcher.stop)
        lines = ['## Quota probe', '', '- Quota probe: on', '- Date: 2026-11-05', '- Agents: claude, codex, agy',
                 '- Claude config: default: ' + str(self.home / 'claude-config')]
        self.paths = {}
        for agent in ('claude', 'codex', 'agy'):
            path = (programs or {}).get(agent)
            if path is None:
                path = folder / agent
                path.write_bytes(b'\x7fsynthetic native program\n')
                path.chmod(0o700)
            resolved = str(Path(path).resolve())
            lines += ['- Executable %s: %s' % (agent, path), '- Resolved %s: %s' % (agent, resolved),
                      '- Resolved digest %s: %s' % (agent, hashlib.sha256(resolved.encode()).hexdigest())]
            self.paths[agent] = str(path)
        return '\n' + '\n'.join(lines) + '\n'

    def start_away(self, text=SETUP_AWAY, **kwargs):
        self.start(text + self.record_programs(**kwargs))

    def real(self, argv):
        """Put the recorded executable where a form names its program by the placeholder name."""
        paths = getattr(self, 'paths', {})
        if len(argv) > 6 and argv[:3] == ENV and argv[5] == '--' and argv[6] in paths:
            return argv[:6] + [paths[argv[6]]] + argv[7:]
        return argv

    def check_as(self, argv, coordinator='claude', tier=1, code='allowed', real=True):
        argv = self.real(argv) if real else argv
        flags = ('--coordinator', coordinator) if coordinator else ()
        status, output = self.invoke('check', *flags, '--argv-json', json.dumps(argv))
        result = json.loads(output)
        self.assertEqual(status, 0 if result['tier'] == 1 else 3, output)
        if code is None:  # any Tier 3 code: a checkout under a protected folder may say `protected` first
            self.assertEqual(result['tier'], 3, argv)
        else:
            expected = {'tier': tier, 'code': code}
            if code in ENDED_CODES:
                expected['end'] = ENDED_LINE
            self.assertEqual(result, expected, argv)

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

    def test_a_decision_needs_a_lease_and_the_afk_log_keeps_only_a_redacted_note(self):
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
                                                          '--notes', 'Changes', '--verify-tag', '--repo', 'github.com/example/demo'],
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

    def test_a_release_names_the_verified_target_like_a_merge(self):
        self.start(SETUP + '- Max actions per hour: 1000\n- Tags and releases: decide\n')
        create = ['gh', 'release', 'create', 'v1.2.0']
        self.check(create + ['--repo', 'github.com/example/demo'])
        self.check(create, tier=3, code='unknown')
        self.check(create + ['-R', 'example/demo'], tier=3, code='unknown')
        self.check(create + ['--repo', 'github.com/example/elsewhere'], tier=3, code='forbidden')
        self.check(create + ['--repo', 'github.com/example/demo', '--repo', 'github.com/example/demo'], tier=3, code='unknown')

    def test_categories_come_from_the_command_not_from_its_free_text(self):
        base = SETUP + '- Max actions per hour: 1000\n'
        repo = ['--repo', 'github.com/example/demo']
        tag = (['gh', 'release', 'create', 'v1', '--notes', 'publish'] + repo, ['git', 'tag', '-a', 'v1', '-m', 'publish'],
               ['git', 'tag', '-a', 'v1', '-m', 'deploy'], ['gh', 'release', 'create', 'v1', '--title', 'deploy:uat'] + repo)
        publish = (['npm', 'publish', '--tag', 'next'], ['pnpm', 'publish', '--access', 'public'])
        local = (['git', 'commit', '-m', 'publish'], ['gh', 'pr', 'create', '--title', 'deploy', '--body', 'publish', '--head', 'topic',
                  '--repo', 'github.com/example/demo'], ['git', 'commit', '-m', 'deploy'])
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
        self.assertEqual(self.counts()['actions'], 2)
        self.assertEqual(self.counts()['runs'], 0)

    def test_the_judge_form_denies_any_other_site_flag_shape_or_copy(self):
        self.start(SETUP_AWAY)
        site = JUDGE.index('away-decision')
        other = str(ROOT / 'skills/checks/scripts/judge.py')
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
        self.assertEqual(self.counts()['actions'], 0)

    def test_the_advisor_form_is_tier_one_for_another_family_in_hosts(self):
        self.start_away()
        self.check_as(CODEX)
        self.check_as(CLAUDE, coordinator='codex')
        self.check_as(CLAUDE[:-2] + ['--effort', 'high', '--max-turns', '8', '--max-budget-usd', '2'] + CLAUDE[-2:],
                      coordinator='codex')
        self.assertEqual(self.counts()['actions'], 3)
        self.assertEqual(self.counts()['runs'], 0)  # the advisor's ledger start reserves its run, as today

    def test_the_antigravity_advisor_form_is_tier_one_in_plan_mode(self):
        self.start_away(SETUP_ALL)
        for coordinator in ('claude', 'codex'):
            self.check_as(AGY, coordinator=coordinator)
        self.check_as(AGY + ['--print-timeout', '30m'])
        mode = AGY.index('plan')
        for value in ('accept-edits', 'default', 'yolo'):
            self.check_as(AGY[:mode] + [value] + AGY[mode + 1:], tier=3, code='unknown')
        self.check_as(AGY, coordinator='antigravity', tier=3, code='unknown')
        self.assertEqual(self.counts()['actions'], 3)

    def test_the_zcode_advisor_form_denies_even_with_an_approved_program(self):
        ap = self.load()
        tail = ['--family', 'zcode', '--', '/opt/synthetic/zcode', '-p', BRIEF, '--model', 'glm-synthetic',
                '--mode', 'plan', '--output-format', 'json']
        applied = {'Hosts': 'Claude Code, ZCode'}
        # Antigravity's grammar would accept this shape; a zcode family must never reach it.
        with patch.object(ap, 'approved_program', return_value=1) as approved:
            self.assertEqual(ap.advisor_command(tail, applied, 'claude'), 'unknown')
        approved.assert_not_called()

    def test_the_advisor_program_is_the_owner_approved_executable(self):
        self.start_away()
        program = CODEX.index('codex', 6)
        recorded = self.paths['codex']
        def at(path):
            return CODEX[:program] + [str(path)] + CODEX[program + 1:]
        self.check_as(at(recorded), real=False)
        # A matching basename at another path, a PATH shadow (bare name), a relative name and a perl time cap deny.
        other = self.home / 'other'
        other.mkdir()
        (other / 'codex').write_bytes(b'\x7fsynthetic\n')
        (other / 'codex').chmod(0o700)
        for argv in (at(other / 'codex'), at('codex'), at('./codex'), at(recorded + '/'),
                     at(str(Path(recorded).parent) + '/../bin/codex'),
                     CODEX[:program] + ['perl', '-e', 'alarm 900; exec @ARGV', recorded] + CODEX[program + 1:],
                     CODEX[:program] + ['/usr/bin/perl', '-e', 'alarm 900; exec @ARGV', recorded] + CODEX[program + 1:]):
            with self.subTest(argv=argv[program:program + 4]):
                self.check_as(argv, tier=3, code='unknown', real=False)
        # A sibling directory in the same repository, with the coordinator in another folder of it.
        tools = self.repo / 'tools'
        tools.mkdir()
        (tools / 'codex').write_bytes(b'\x7fsynthetic\n')
        (tools / 'codex').chmod(0o700)
        (self.repo / 'src').mkdir()
        self.repo = self.cwd = self.repo / 'src'
        self.check_as(at(tools / 'codex'), tier=3, code='unknown', real=False)
        # A symlink outside the repository that leads to repository code.
        links = self.home / 'links'
        links.mkdir()
        (links / 'codex').symlink_to(tools / 'codex')
        self.check_as(at(links / 'codex'), tier=3, code='unknown', real=False)
        self.assertEqual(self.counts()['actions'], 1)

    def test_a_recorded_program_inside_a_repository_or_without_a_record_denies(self):
        tools = self.repo / 'tools'
        tools.mkdir()
        target = tools / 'codex'
        target.write_bytes(b'\x7fsynthetic\n')
        target.chmod(0o700)
        links = self.home / 'links'
        links.mkdir()
        (links / 'codex').symlink_to(target)
        # Even when setup recorded it: repository code, directly or through a link, is never an approved program.
        for path in (target, links / 'codex'):
            with self.subTest(path=path):
                self.setup_config(SETUP_AWAY + self.record_programs(programs={'codex': path}))
                self.assertEqual(self.invoke('stop')[0], 0)
                self.assertEqual(self.invoke('start')[0], 0)
                self.check_as(CODEX, tier=3, code='unknown')
        # No record, an unconfirmed record or the probe turned off: the advisor form is denied.
        record = self.record_programs()
        digest = re.search(r'- Resolved digest codex: [0-9a-f]+\n', record)[0]
        for text in ('', record.replace(digest, ''), record.replace('- Quota probe: on', '- Quota probe: off'),
                     record.replace('- Agents: claude, codex, agy', '- Agents: claude, agy')):
            with self.subTest(record=text[:40]):
                self.setup_config(SETUP_AWAY + text)
                self.assertEqual(self.invoke('stop')[0], 0)
                self.assertEqual(self.invoke('start')[0], 0)
                self.check_as(CODEX[:6] + [self.paths['codex']] + CODEX[7:], tier=3, code='unknown', real=False)

    def test_the_advisor_form_denies_writes_other_families_programs_and_shapes(self):
        self.start_away()
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
                (['python3'] + CODEX[2:], 'claude')):
            with self.subTest(argv=argv[3:9], coordinator=coordinator):
                self.check_as(argv, coordinator=coordinator, tier=3, code='unknown')
        # Another copy of the wrapper is not the form; inside this install's checkout it is also a protected path.
        self.check_as(['python3', '-I', str(ROOT / 'scripts/delegate_env.py')] + CODEX[3:], tier=3, code=None)
        self.assertEqual(self.counts()['actions'], 0)

    def test_the_brief_position_never_accepts_an_option(self):
        self.start_away(SETUP_ALL)
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
        self.assertEqual(self.counts()['actions'], 0)
        for form, coordinator in forms.values():
            self.check_as(form, coordinator=coordinator)

    def test_a_sensitive_assignment_split_across_lines_is_screened(self):
        module = self.load()
        for brief in ('session_cookie: "\n  synthetic-fixture-1234567890\n"', "password: '\n  demo\n'", 'password: |\n  demo',
                      'password:\n  - demo', 'password=$(cat x)', '"token" \n\n = \n "q"',
                      '{"session_cookie":\n  "synthetic-fixture-1234567890"}', '{"password":\n"demo"}',
                      'password =\n  demo', 'api_token\n  : abc', '{"password": "demo"}'):
            with self.subTest(brief=brief):
                self.assertFalse(module.brief_ok(brief))
                self.assertTrue(module.screened(brief))
        self.assertTrue(module.brief_ok('The password setting is described\nin the next section.'))

    def test_branch_deletion_bundled_with_a_merge_needs_its_own_category(self):
        module = self.load()
        # Bind the merge target to a fixed verified target, not to whatever Git config the runner's checkout holds.
        argv = ['gh', 'pr', 'merge', '215', '--merge', '--match-head-commit=' + 'a' * 40,
                '--repo', 'github.com/example/demo']
        applied = {**module.DEFAULTS, **{c: 'stop' for c in module.CATEGORIES}, 'Merge': 'yes',
                   module.CONSENT: 'no', module.TARGETS: [],
                   module.CONTEXT: module.Context('found', None, 'user', 'github.com/example/demo')}
        self.assertEqual(module.classify_argv(argv, applied), 'allowed')
        self.assertEqual(module.classify_argv(argv + ['--delete-branch'], applied), 'forbidden')
        applied['Recoverable deletion'] = 'decide'
        self.assertEqual(module.classify_argv(argv + ['--delete-branch'], applied), 'allowed')

    def test_the_advisor_brief_is_screened_like_the_judge_and_packet_paths(self):
        self.start_away()
        home = '/Us' + 'ers/synthetic'
        # A sensitive name with any assigned value, however short, and any machine path deny.
        for brief in ('Use db_password=fixture123 in the fixture.', 'Set API_TOKEN=ab and continue.',
                      'The test sets secret: x1 first.', "Config has auth_token = 'q'.", 'export PASSWORD=1',
                      'Read ' + home + '/notes.md first.', 'See ~/private/notes.', 'Look in /ho' + 'me/synthetic/x.',
                      'Open C:\\work\\x.txt.', BRIEF + '\nsession_cookie=abc'):
            with self.subTest(brief=brief):
                self.check_as(CODEX[:-1] + [brief], tier=3, code='unknown')
        self.assertEqual(self.counts()['actions'], 0)
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


PIN = ['--match-head-commit', 'a' * 40]
NO = SETUP.replace('- Merge: yes', '- Merge: no').replace('requests: yes', 'requests: no')


class ProjectScopeTest(AfkBase):
    """A repository's approved `autopilot` object in its settings file wins for five keys; user scope stays default."""

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location('project_store_tested', SCRIPT.parent / 'project_store.py')
        self.store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.store)

    def project(self, value):
        found, ident = self.store.identity(self.repo)
        self.store.write_setting(self.repo, 'autopilot', value, ident=ident)

    def settings_file(self):
        return self.repo / '.finolabs/vibecode/settings.json'

    def test_a_project_value_wins_over_the_user_value_for_merge_and_push(self):
        self.start(NO)
        self.project({'merge': 'yes', 'push-and-pull-requests': 'yes'})
        self.check(['gh', 'pr', 'merge', '7'] + PIN + ['--repo', 'github.com/example/demo'])
        self.check(['git', 'push', 'origin', 'HEAD:refs/heads/topic'])
        self.check(['gh', 'pr', 'create', '--head', 'topic', '--repo', 'github.com/example/demo'])
        self.project({'merge': 'no', 'push-and-pull-requests': 'no'})
        # check re-reads the project values on each call; the user-only lease hash is unchanged.
        self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')
        self.check(['git', 'push', 'origin', 'HEAD:refs/heads/topic'], tier=3, code='push-disabled')
        self.check(['git', 'status'])

    def other_repo(self, name):
        repo = self.home / name
        (repo / '.git/refs/remotes/origin').mkdir(parents=True)
        (repo / '.git/HEAD').write_text('ref: refs/heads/topic\n')
        (repo / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/main\n')
        (repo / '.git/config').write_text(ORIGIN_CONFIG)
        return repo

    def test_production_targets_are_tier_one_only_where_the_repository_listed_and_decides_them(self):
        targets = '- Non-production targets: npx wrangler deploy --env uat\n'
        self.start(SETUP + '- Max actions per hour: 1000\n' + targets)
        production = ['npx', 'wrangler', 'deploy', '--env', 'production']
        self.check(production, tier=3, code='forbidden')  # the user scope never decides production
        self.project({'production-targets': ['npx wrangler deploy --env production']})
        self.check(production, tier=3, code='forbidden')  # listed, but Production is not in this repository's decide
        self.project({'production-targets': ['npx wrangler deploy --env production'], 'decide': ['production']})
        self.check(production)
        self.check(['npx', 'wrangler', 'deploy', '--env', 'uat'])  # the user's non-production list is inherited
        # A token holding a space never matches two listed words, though the joined text is the same.
        for argv in (['npx', 'wrangler', 'deploy', '--env production'], ['npx', 'wrangler', 'deploy', '--env uat']):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code='forbidden')
        for argv in (production + ['--minify'], ['npx', 'wrangler', 'deploy', '--env', 'live'],
                     ['npx', 'wrangler', 'deploy', '--env', 'production-eu']):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code='forbidden')  # an unlisted production deploy parks
        # An explicit decide list replaces the user's answers: tags were not listed, so they stop here.
        self.check(['git', 'tag', 'v1.2.0'], tier=3, code='forbidden')
        # The same argv in another repository, where nothing lists it, parks.
        self.cwd = self.other_repo('second')
        self.check(production, tier=3, code='forbidden')

    def test_project_decide_and_target_lists_replace_the_user_values(self):
        self.start(SETUP + '- Max actions per hour: 1000\n- Tags and releases: decide\n'
                   '- Non-production targets: npx wrangler deploy --env uat\n')
        self.check(['git', 'tag', 'v1.2.0'])
        self.project({'decide': [], 'non-production-targets': ['npx wrangler deploy --env qa']})
        self.check(['git', 'tag', 'v1.2.0'], tier=3, code='forbidden')
        self.check(['npx', 'wrangler', 'deploy', '--env', 'uat'], tier=3, code='forbidden')
        self.check(['npx', 'wrangler', 'deploy', '--env', 'qa'])
        self.project({'decide': ['tags-and-releases']})
        self.check(['git', 'tag', 'v1.2.0'])
        self.check(['npx', 'wrangler', 'deploy', '--env', 'uat'])  # an omitted target list inherits the user's
        for bad in ({'decide': ['real-users-and-customer-data']}, {'decide': ['credentials']}, {'decide': 'production'},
                    {'decide': ['production', 'production']}, {'production-targets': []},
                    {'production-targets': ['npx wrangler deploy; rm -rf /']}, {'production-targets': ['a  b']},
                    {'non-production-targets': ['$(whoami) deploy']}, {'production-targets': ['x'] * 17}):
            with self.subTest(bad=bad):
                self.assertFalse(self.store.valid_autopilot(bad))

    def test_strict_and_no_repository_states_close_every_category_and_target(self):
        self.start(SETUP + '- Max actions per hour: 1000\n- Tags and releases: decide\n'
                   '- Non-production targets: npx wrangler deploy --env uat\n')
        outside = self.home / 'no-repository'
        outside.mkdir(exist_ok=True)
        self.cwd = outside
        for argv in (['git', 'tag', 'v1.2.0'], ['npx', 'wrangler', 'deploy', '--env', 'uat']):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code='forbidden')
        # The strict state: a repository whose ancestors cannot be read.
        locked = self.repo / 'locked'
        (locked / 'inner').mkdir(parents=True)
        locked.chmod(0o311)
        self.addCleanup(locked.chmod, 0o755)
        self.cwd = locked / 'inner'
        for argv in (['git', 'tag', 'v1.2.0'], ['npx', 'wrangler', 'deploy', '--env', 'uat']):
            with self.subTest(strict=argv):
                self.check(argv, tier=3, code='forbidden')

    def test_limits_are_counted_per_project(self):
        self.start(SETUP + '- Max actions per hour: 2\n')
        first, second = self.repo, self.other_repo('second')
        self.check(['git', 'status'])
        self.check(['git', 'status'])
        self.check(['git', 'status'], tier=3, code='limit')
        self.cwd = second
        self.check(['git', 'status'])
        self.check(['git', 'status'])
        self.check(['git', 'status'], tier=3, code='limit')
        self.cwd = first
        self.check(['git', 'status'], tier=3, code='limit')
        self.assertEqual(sorted(e['actions'] for e in self.lease()['counters'].values()), [2, 2])
        self.clock += 3601
        self.check(['git', 'status'])

    def test_spent_runs_in_one_project_leave_the_others_working(self):
        self.start(SETUP + '- Max runs: 1\n')
        ledger = ['python3', '-I', str(SCRIPT.parent / 'ledger.py'), 'start']
        self.check(ledger)
        self.check(['git', 'status'], tier=3, code='spent')
        self.cwd = self.other_repo('second')
        self.check(ledger)

    def test_a_project_limit_replaces_the_user_limit_both_ways(self):
        self.start(SETUP + '- Max actions per hour: 2\n')
        self.project({'max-actions-per-hour': 3})
        for _ in range(3):
            self.check(['git', 'status'])
        self.check(['git', 'status'], tier=3, code='limit')
        narrow = self.other_repo('narrow')
        found, ident = self.store.identity(narrow)
        self.store.write_setting(narrow, 'autopilot', {'max-actions-per-hour': 1}, ident=ident)
        self.cwd = narrow
        self.check(['git', 'status'])
        self.check(['git', 'status'], tier=3, code='limit')

    def test_unidentified_checks_share_one_unknown_entry(self):
        self.start(SETUP + '- Max actions per hour: 2\n')
        for name in ('plain-one', 'plain-two'):
            folder = self.home / name
            folder.mkdir()
            self.cwd = folder
            self.check(paths=['src/example.py'], tier=3, code='unknown')  # no identity: nothing is reserved
        self.assertEqual(self.lease()['counters'], {})
        ap = self.load()
        lease = dict(counters={})
        applied = {'Max runs': 20, 'Max runtime minutes': 480, 'Max actions per hour': 2, ap.CONTEXT: ap.UNKNOWN}
        self.assertEqual(ap.project_limit(lease, applied, self.clock)[1], 'unknown')
        absent = ap.Context('absent', None, 'no-repository', None)
        self.assertEqual(ap.project_key(absent), 'unknown')

    def test_a_full_project_table_answers_limit_and_keeps_its_entries(self):
        self.start(SETUP + '- Max actions per hour: 100\n')
        self.check(['git', 'status'])
        own = next(iter(self.lease()['counters']))
        fill = {('%064x' % n): dict(runs=0, actions=1, hour_actions=[self.clock], first=self.clock) for n in range(63)}
        self.change_lease(lambda v: v['counters'].update(fill))
        self.cwd = self.other_repo('sixty-fifth')
        self.check(['git', 'status'], tier=3, code='limit')
        table = self.lease()['counters']
        self.assertEqual(len(table), 64)
        self.assertIn(own, table)
        self.cwd = self.repo
        self.check(['git', 'status'])

    def test_limit_values_outside_their_range_are_refused(self):
        for value in ({'max-runs': 0}, {'max-runtime-minutes': 1441}, {'max-actions-per-hour': '5'},
                      {'max-runs': True}):
            with self.subTest(value=value):
                self.assertFalse(self.store.valid_autopilot(value))
        self.assertTrue(self.store.valid_autopilot({'max-runs': 5, 'max-runtime-minutes': 60}))

    def run_body(self, text, name='a' * 32):
        folder = self.root / 'state/review-posting' / ('post-' + name)
        folder.mkdir(parents=True, exist_ok=True)
        for part in (self.root / 'state', self.root / 'state/review-posting', folder):
            part.chmod(0o700)
        body = folder / 'body.md'
        body.write_text(text)
        body.chmod(0o600)
        return body

    def test_post_review_runs_with_its_own_run_body_and_the_comment_category(self):
        post = ['python3', '-I', str(ROOT / 'skills/review-gate/scripts/post_review.py')]
        marker = '<!-- fnl-review kind=code head=' + 'a' * 40 + ' verdict=APPROVE -->\n'
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.check(post + ['7'], tier=3, code='forbidden')  # Repository comments is stop
        self.invoke('stop')
        self.start(SETUP + '- Max actions per hour: 1000\n- Repository comments: decide\n')
        self.check(post + ['7'])
        body = self.run_body(marker + 'Reviewer: example\n\nNo findings.\n')
        self.check(post + ['7', '--body-file', str(body)])
        self.check(post + ['--body-file', str(body), '7'])
        for argv, code in ((post + ['07'], 'unknown'), (post + ['7', '8'], 'unknown'),
                           (post + ['7', '--repo', 'github.com/example/demo'], 'unknown')):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code=code)
        for text, code in (('Reviewer: no marker\n', 'unsafe'), (marker, 'unsafe'),
                           (marker + 'Reviewer: x\n<!-- fnl-review kind=security head=' + 'b' * 40
                            + ' verdict=APPROVE -->\n', 'forbidden'),
                           (marker + 'Reviewer: x\n' + 'AKIA' + 'ABCDEFGHIJKLMNOP\n', 'unsafe'),
                           (marker + 'Reviewer: x\n' + 'Fine words.\n' * 6000, 'unsafe')):  # over 64 KiB
            with self.subTest(text=text[:30]):
                body = self.run_body(text, 'b' * 32)
                self.check(post + ['7', '--body-file', str(body)], tier=3, code=code)
        self.check(post + ['1234567890'])
        (self.repo / '.git/config').write_text(ORIGIN_CONFIG.replace('github.com/example/demo', 'gitlab.com/example/demo'))
        self.check(post + ['7'], tier=3, code='unknown')  # no verified GitHub target
        (self.repo / '.git/config').write_text(ORIGIN_CONFIG)
        inside = self.repo / 'body.md'
        inside.write_text(marker + 'Reviewer: x\n')
        self.check(post + ['7', '--body-file', str(inside)], tier=3, code='unsafe')
        loose = self.run_body(marker + 'Reviewer: x\n', 'c' * 32)
        loose.chmod(0o644)
        self.check(post + ['7', '--body-file', str(loose)], tier=3, code='unsafe')

    def test_an_approved_skill_repository_edits_its_root_skill_and_references(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.check(paths=['SKILL.md'], tier=3, code='protected')
        self.project({'skill-repository': 'yes'})
        self.check(paths=['SKILL.md', 'references/guide.md', 'evals/case.json', 'scripts/tool.py'])
        for nested in ('references/nested/SKILL.md', 'scripts/SKILL.md', 'scripts/tool/SKILL.md', 'evals/SKILL.md'):
            with self.subTest(path=nested):
                self.check(paths=[nested], tier=3, code='protected')
        self.check(paths=['.github/workflows/ci.yml'], tier=3, code='protected')
        # The same paths as command operands: staging and removing them on the work branch.
        self.check(['git', 'add', 'SKILL.md', 'references/guide.md'])
        self.check(['git', 'rm', 'scripts/tool.py'])
        self.check(['git', 'add', 'references/nested/SKILL.md'], tier=3, code='protected')
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')  # the default branch stays protected
        self.check(paths=['SKILL.md'], tier=3, code='protected')
        self.check(['git', 'add', 'SKILL.md'], tier=3, code='protected')
        self.assertFalse(self.store.valid_autopilot({'skill-repository': 'no'}))

    def test_the_lease_hash_covers_the_user_section_only(self):
        self.start()
        before = self.lease()['settings_hash']
        self.project({'merge': 'no', 'roots': ['packages']})
        self.check(['git', 'status'])
        self.assertEqual(self.lease()['settings_hash'], before)
        self.setup_config(SETUP + '- Max runs: 5\n')
        self.check(['git', 'status'], tier=3, code='setup-changed')

    def test_an_unapproved_or_branch_supplied_file_sets_nothing(self):
        self.start(NO)
        self.settings_file().parent.mkdir(parents=True, mode=0o700)
        self.settings_file().write_text(json.dumps({'version': 1, 'autopilot': {'merge': 'yes', 'roots': ['packages']}}))
        self.settings_file().chmod(0o600)
        self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')
        (self.repo / 'packages').mkdir()
        self.check(paths=['packages/app.py'], tier=3, code='unknown')

    def test_a_broken_approved_file_falls_back_to_off_never_wider(self):
        self.start()
        self.project({'roots': ['packages']})
        self.check(['gh', 'pr', 'merge', '7'] + PIN + ['--repo', 'github.com/example/demo'])
        self.check(paths=['packages/app.py'])
        for change in (lambda f: f.write_bytes(f.read_bytes() + b' '), lambda f: f.unlink(),
                       lambda f: f.chmod(0o666)):
            with self.subTest(change=change):
                self.store.reset_settings(self.repo)
                self.project({'roots': ['packages']})
                change(self.settings_file())
                self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')
                self.check(['git', 'push', 'origin', 'HEAD:refs/heads/topic'], tier=3, code='push-disabled')
                self.check(['gh', 'pr', 'create'], tier=3, code='push-disabled')
                self.check(paths=['packages/app.py'], tier=3, code='unknown')
                self.check(['git', 'status'])
        # An unreadable project state (an error while resolving it) is off too.
        self.store.reset_settings(self.repo)
        ap = self.load()
        with patch.object(ap.store, 'autopilot_binding', side_effect=OSError('synthetic')):
            self.assertEqual(ap.effective(dict(ap.DEFAULTS, Merge='yes', Roots=[]), str(self.repo))['Merge'], 'no')

    def test_project_roots_join_the_built_in_roots_with_the_same_path_rules(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        (self.repo / 'packages/app').mkdir(parents=True)
        self.check(paths=['packages/app/main.ts'], tier=3, code='unknown')
        self.project({'roots': ['packages', 'services']})
        self.check(paths=['packages/app/main.ts', 'services/api.py', 'src/example.py'])
        self.check(['git', 'add', '--', 'packages/app/main.ts'])
        self.check(['git', 'diff', '--stat', 'services/api.py'])
        for path, code in (('packages/app/main.exe', 'unknown'), ('packages/../src/example.py', 'unknown'),
                           ('/packages/app/main.ts', 'unknown'), ('packages', 'unknown'), ('packages/app', 'unknown'),
                           ('packages/.env', 'protected'), ('packages/app/settings.json', 'protected'),
                           ('packages/hooks/pre-push.py', 'protected'), ('packages/CLAUDE.md', 'protected'),
                           ('packages/app/afk.py', 'protected'), ('tools/build.py', 'unknown')):
            with self.subTest(path=path):
                self.check(paths=[path], tier=3, code=code)
        target = self.home / 'synthetic'
        target.write_text('unread')
        (self.repo / 'packages/linked.py').symlink_to(target)
        self.check(paths=['packages/linked.py'], tier=3, code='protected')
        (self.repo / 'services').symlink_to(self.home, target_is_directory=True)
        self.check(paths=['services/api.py'], tier=3, code='protected')

    def test_top_level_documentation_files_are_known_paths(self):
        self.start()
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')  # CLAUDE.md is source on a work branch only
        self.check(paths=['README.md', 'CHANGELOG.md', 'CONTRIBUTING.md'])
        self.check(['git', 'add', 'README.md'])
        for path, code in (('LICENSE', 'unknown'), ('NOTES.md', 'unknown'), ('readme.txt', 'unknown'),
                           ('CLAUDE.md', 'protected'), ('AGENTS.md', 'protected'), ('./README.md', 'unknown')):
            with self.subTest(path=path):
                self.check(paths=[path], tier=3, code=code)
        (self.repo / 'README.md').symlink_to(self.home / 'missing')
        self.check(paths=['README.md'], tier=3, code='protected')

    def branch(self, name, packed=False):
        if packed:
            with open(self.repo / '.git/packed-refs', 'a') as stream:
                stream.write('a' * 40 + ' refs/heads/' + name + '\n')
        else:
            path = self.repo / '.git/refs/heads' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('a' * 40 + '\n')

    def test_a_local_branch_merge_into_a_work_branch_is_tier_one_when_merge_is_yes(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.branch('feature/one')
        self.branch('packed', packed=True)
        for argv in (['git', 'merge', '--no-ff', 'refs/heads/feature/one'], ['git', 'merge', 'feature/one'],
                     ['git', 'merge', '--no-ff', '--no-edit', 'refs/heads/feature/one'],
                     ['git', 'merge', '--no-ff', 'packed'], ['git', 'merge', 'origin/main']):
            with self.subTest(argv=argv):
                self.check(argv)
        for argv in (['git', 'merge', 'missing'], ['git', 'merge', 'refs/heads/missing'],
                     ['git', 'merge', 'refs/tags/v1'], ['git', 'merge', 'refs/remotes/origin/x'],
                     ['git', 'merge', '-s', 'ours', 'feature/one'], ['git', 'merge', '--squash', 'feature/one'],
                     ['git', 'merge', 'feature/one', 'packed'], ['git', 'merge', '--no-ff'],
                     ['git', 'merge', 'refs/heads/../feature/one'], ['git', 'merge', 'topic'],
                     ['git', 'merge', '-X', 'theirs', 'feature/one'], ['git', 'merge', '--no-ff=x', 'feature/one'],
                     ['git', 'merge', 'feature/one~1'], ['git', 'merge', '--abort']):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code='unknown')
        # A bare name that is also a tag (or another ref) is ambiguous: git would pick the tag first.
        (self.repo / '.git/refs/tags').mkdir(parents=True)
        (self.repo / '.git/refs/tags/shared').write_text('b' * 40 + '\n')
        self.branch('shared')
        self.check(['git', 'merge', 'shared'], tier=3, code='unknown')
        self.check(['git', 'merge', 'refs/heads/shared'])
        with open(self.repo / '.git/packed-refs', 'a') as stream:
            stream.write('c' * 40 + ' refs/tags/packed\n')
        self.check(['git', 'merge', 'packed'], tier=3, code='unknown')
        self.branch('abcdef1')
        self.check(['git', 'merge', 'abcdef1'], tier=3, code='unknown')  # could also read as a commit id
        self.check(['git', 'merge', 'refs/heads/abcdef1'])

    def test_a_local_merge_needs_merge_yes_and_never_targets_the_default_branch(self):
        self.start(NO)
        self.branch('feature')
        self.check(['git', 'merge', '--no-ff', 'refs/heads/feature'], tier=3, code='merge-disabled')
        self.project({'merge': 'yes'})
        self.check(['git', 'merge', '--no-ff', 'refs/heads/feature'])
        for head in ('main', 'stable'):
            with self.subTest(head=head):
                (self.repo / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/stable\n')
                (self.repo / '.git/HEAD').write_text('ref: refs/heads/' + head + '\n')
                self.check(['git', 'merge', '--no-ff', 'refs/heads/feature'], tier=3, code='forbidden')
        (self.repo / '.git/HEAD').write_text('a' * 40 + '\n')  # a detached head is not a work branch
        self.check(['git', 'merge', '--no-ff', 'refs/heads/feature'], tier=3, code='forbidden')
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/topic\n')
        (self.repo / '.git/refs/remotes/origin/HEAD').unlink()
        self.check(['git', 'merge', '--no-ff', 'refs/heads/feature'], tier=3, code='unknown')

    def test_delegated_runs_outside_the_wrapper_or_in_write_modes_stay_tier_three(self):
        self.start(SETUP.replace('Claude Code', 'Claude Code, Codex') + '- Max actions per hour: 1000\n')
        for argv in (['claude', '-p', '--model', 'm', '--output-format', 'json', '--', BRIEF],
                     ['claudework', '-p', BRIEF], ['/bin/zsh', '-ic', 'claudework "$@"', 'claudework', '-p', BRIEF],
                     ['codex', 'exec', '-m', 'm', '-s', 'workspace-write', '--', BRIEF],
                     ['perl', '-e', 'alarm 900; exec @ARGV', 'codex', 'exec', '--', BRIEF],
                     ENV + ['--family', 'claude', '--', '/bin/zsh', '-ic', 'claudework "$@"', 'claudework', '-p', BRIEF],
                     CODEX[:CODEX.index('read-only')] + ['workspace-write'] + CODEX[CODEX.index('read-only') + 1:],
                     CLAUDE[:CLAUDE.index('plan')] + ['acceptEdits'] + CLAUDE[CLAUDE.index('plan') + 1:]):
            with self.subTest(argv=argv[:6]):
                self.check(argv, tier=3, code='unknown')
        self.assertEqual(self.counts()['actions'], 0)


class SecurityRoundOneTest(AfkBase):
    """Repository identity, merge target binding, symbolic branches and hexadecimal names fail closed."""

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location('project_store_tested', SCRIPT.parent / 'project_store.py')
        self.store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.store)

    def project(self, value, repo=None):
        found, ident = self.store.identity(repo or self.repo)
        self.store.write_setting(repo or self.repo, 'autopilot', value, ident=ident)

    def test_a_deep_descendant_keeps_the_project_values(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.project({'merge': 'no', 'push-and-pull-requests': 'no'})
        self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')
        deep = self.repo.joinpath(*['level'] * 25)
        deep.mkdir(parents=True)
        self.cwd = deep
        self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')
        self.check(['git', 'push', 'origin', 'HEAD:refs/heads/topic'], tier=3, code='push-disabled')
        self.check(['gh', 'pr', 'create'], tier=3, code='push-disabled')

    def test_a_discovery_error_is_the_strict_state_not_the_user_values(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        locked = self.repo / 'locked'
        (locked / 'inner').mkdir(parents=True)
        locked.chmod(0o311)  # searchable, not listable: an ancestor that cannot be opened
        self.addCleanup(locked.chmod, 0o755)
        self.cwd = locked / 'inner'
        self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')
        self.check(['gh', 'pr', 'create'], tier=3, code='push-disabled')
        ap = self.load()
        for state in (('unknown', None),):
            with patch.object(ap.store, 'identity', return_value=state):
                result = ap.effective(dict(ap.DEFAULTS, Merge='yes', Roots=['x']), str(self.repo))
            self.assertEqual({k: result[k] for k in ap.OFF}, ap.OFF)
            self.assertEqual(ap.context_of(result).cwd, str(self.repo))  # never the process's own cwd

    def test_a_dot_git_link_is_not_skipped_for_a_parent_repository(self):
        self.start(NO)
        self.project({'merge': 'yes', 'push-and-pull-requests': 'yes'})
        nested = self.repo / 'nested'
        nested.mkdir()
        (nested / '.git').symlink_to(self.home / 'elsewhere')
        self.cwd = nested
        self.check(['gh', 'pr', 'merge', '7'] + PIN, tier=3, code='merge-disabled')

    def test_a_merge_or_pull_request_on_another_repository_is_tier_three(self):
        self.start(NO.replace('- Merge: no', '- Merge: yes').replace('requests: no', 'requests: yes')
                   + '- Max actions per hour: 1000\n')
        for flag in (['--repo', 'other/restricted'], ['--repo=other/restricted'], ['-R', 'other/restricted'],
                     ['-R=other/restricted'], ['-Rother/restricted'], ['--repo', 'other.example/example/demo'],
                     ['--repo', 'https://github.com/example/demo'], ['--repo', 'example/demo/extra'],
                     ['--repo', 'example/demo', '--repo', 'other/restricted'], [], ['--repo', 'example/demo'],
                     ['-R', 'EXAMPLE/Demo'], ['-R', 'github.com/example/demo']):
            for argv in (['gh', 'pr', 'merge', '7'] + PIN, ['gh', 'pr', 'create', '--head', 'topic'],
                         ['gh', 'pr', 'edit', '7']):
                with self.subTest(flag=flag, argv=argv[:3]):
                    status, output = self.invoke('check', '--argv-json', json.dumps(argv + flag))
                    self.assertEqual(json.loads(output)['tier'], 3, output)
        for flag in (['--repo', 'github.com/example/demo'], ['--repo=github.com/EXAMPLE/Demo']):
            with self.subTest(flag=flag):
                self.check(['gh', 'pr', 'merge', '7'] + PIN + flag)
                self.check(['gh', 'pr', 'create', '--head', 'topic'] + flag)
                self.check(['gh', 'pr', 'edit', '7'] + flag)

    def test_project_merge_never_authorizes_another_repository(self):
        self.start(NO + '- Max actions per hour: 1000\n')
        self.project({'merge': 'yes', 'push-and-pull-requests': 'yes'})
        self.check(['gh', 'pr', 'merge', '7'] + PIN + ['--repo', 'github.com/example/demo'])
        self.check(['gh', 'pr', 'merge', '7', '--repo', 'github.com/other/restricted'] + PIN, tier=3, code='forbidden')
        self.check(['gh', 'pr', 'create', '--head', 'topic', '--repo', 'github.com/other/restricted'],
                   tier=3, code='forbidden')

    def test_the_target_repository_must_be_read_safely_from_the_checkout(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        merge = ['gh', 'pr', 'merge', '7'] + PIN + ['--repo', 'github.com/example/demo']
        config = self.repo / '.git/config'
        for text in ('', ORIGIN_CONFIG + '[include]\n\tpath = extra\n',
                     ORIGIN_CONFIG + '[includeIf "gitdir:x"]\n\tpath = extra\n',
                     ORIGIN_CONFIG + '[url "https://github.com/other/"]\n\tinsteadOf = https://github.com/example/\n',
                     ORIGIN_CONFIG + '\turl = https://github.com/other/restricted.git\n',
                     '[remote "origin"]\n\turl = https://gitlab.example/example/demo.git\n',
                     '[remote "origin"]\n\turl = /srv/example/demo.git\n',
                     '[remote "origin"\n\turl = https://github.com/example/demo.git\n'):
            with self.subTest(text=text):
                config.write_text(text)
                self.check(merge, tier=3, code='unknown')
                self.check(['gh', 'pr', 'create', '--head', 'topic', '--repo', 'github.com/example/demo'],
                           tier=3, code='unknown')
        # An explicit --repo equal to origin binds the target even beside another remote.
        config.write_text(ORIGIN_CONFIG + '[remote "upstream"]\n\turl = https://github.com/other/restricted.git\n')
        self.check(merge)
        config.unlink()
        self.check(merge, tier=3, code='unknown')
        for url in ('git' '@github.com:example/demo.git', 'ssh://git' '@github.com/example/demo', 'https://github.com/example/demo'):
            with self.subTest(url=url):
                config.write_text('[remote "origin"]\n\turl = ' + url + '\n')
                self.check(merge)
        (self.repo / '.git/config.worktree').write_text('[remote "origin"]\n\turl = https://github.com/other/restricted\n')
        self.check(merge, tier=3, code='unknown')

    def test_a_symbolic_current_branch_to_the_default_branch_is_forbidden(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        heads = self.repo / '.git/refs/heads'
        heads.mkdir(parents=True)
        (heads / 'feature').write_text('a' * 40 + '\n')
        (heads / 'work').write_text('b' * 40 + '\n')
        merge = ['git', 'merge', 'refs/heads/feature']
        (heads / 'topic').write_text('ref: refs/heads/work\n')
        self.check(merge)  # a link to an ordinary work branch stays a work branch
        for target, code in (('refs/heads/main', 'forbidden'), ('refs/heads/stable', 'forbidden'),
                             ('refs/heads/trunk', 'forbidden'), ('refs/heads/loop', 'unknown'),
                             ('refs/tags/v1', 'unknown'), ('refs/remotes/origin/main', 'unknown')):
            with self.subTest(target=target):
                (self.repo / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/stable\n')
                (heads / 'topic').write_text('ref: ' + target + '\n')
                (heads / 'loop').write_text('ref: refs/heads/topic\n')
                self.assertIn(self.check_code(merge), {code, 'forbidden'})
                self.assertEqual(self.check_code(['git', 'merge', 'origin/main']), 'forbidden')
        (heads / 'loop').unlink()
        (heads / 'topic').write_text('ref: refs/heads/main\n')
        self.check(['git', 'push', 'origin', 'HEAD:HEAD'], tier=3, code='forbidden')

    def check_code(self, argv):
        status, output = self.invoke('check', '--argv-json', json.dumps(argv))
        result = json.loads(output)
        self.assertEqual(result['tier'] == 1, result['code'] == 'allowed', output)
        return result['code']

    def git_repo(self, name):
        import shutil
        import subprocess
        if not shutil.which('git', path=os.defpath + ':/usr/local/bin:/opt/homebrew/bin'):
            self.skipTest('git is not installed')
        repo = self.home / name
        repo.mkdir()
        env = {'HOME': str(self.home), 'PATH': os.defpath + ':/usr/local/bin:/opt/homebrew/bin',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}

        def git(*argv, cwd=repo):
            return subprocess.run(['git', *argv], cwd=cwd, env=env, capture_output=True, check=True,
                                  text=True).stdout.strip()
        git('init', '-q', '-b', 'main')
        git('remote', 'add', 'origin', 'https://github.com/example/demo.git')
        for message in ('First', 'Second'):
            git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com', 'commit', '-q',
                '--allow-empty', '-m', message)
        git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        git('branch', 'feature')
        return repo, git

    def test_real_git_symbolic_head_to_main_in_ordinary_and_linked_worktrees(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        repo, git = self.git_repo('real')
        git('branch', 'work')
        git('symbolic-ref', 'refs/heads/topic', 'refs/heads/work')
        git('symbolic-ref', 'HEAD', 'refs/heads/topic')
        self.cwd = repo
        self.assertEqual(self.check_code(['git', 'merge', 'refs/heads/feature']), 'allowed')
        git('symbolic-ref', 'refs/heads/topic', 'refs/heads/main')
        self.assertEqual((repo / '.git/HEAD').read_text(), 'ref: refs/heads/topic\n')
        self.assertEqual(git('rev-parse', '--symbolic-full-name', 'HEAD'), 'refs/heads/main')
        self.check(['git', 'merge', 'refs/heads/feature'], tier=3, code='forbidden')
        self.check(['git', 'merge', 'origin/main'], tier=3, code='forbidden')
        self.check(['git', 'push', 'origin', 'HEAD:HEAD'], tier=3, code='forbidden')
        linked = self.home / 'linked'
        git('worktree', 'add', '-q', str(linked), '-b', 'side')
        git('symbolic-ref', 'refs/heads/alias', 'refs/heads/main')
        git('symbolic-ref', 'HEAD', 'refs/heads/alias', cwd=linked)
        self.cwd = linked
        self.check(['git', 'merge', 'refs/heads/feature'], tier=3, code='forbidden')
        git('symbolic-ref', 'HEAD', 'refs/heads/side', cwd=linked)
        self.check(['git', 'merge', 'refs/heads/feature'])

    def test_real_git_hexadecimal_branch_names_in_any_case_are_ambiguous(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        repo, git = self.git_repo('hex')
        git('checkout', '-q', '-b', 'topic')
        first, second = git('rev-parse', 'HEAD~1'), git('rev-parse', 'HEAD')
        self.cwd = repo
        for name in (first.upper(), first[:7].upper(), 'AbCdEf1', 'ABCD', 'f' * 64, 'deadBEEF' * 8):
            with self.subTest(name=name):
                git('branch', name, second)
                if name == first.upper():
                    # Git itself reads the bare name as the first commit, not the branch the classifier validated.
                    self.assertEqual(git('rev-parse', name), first)
                    self.assertEqual(git('rev-parse', 'refs/heads/' + name), second)
                self.check(['git', 'merge', name], tier=3, code='unknown')
                self.check(['git', 'merge', 'refs/heads/' + name])
                git('branch', '-q', '-D', name)
        git('branch', 'shared')
        git('tag', 'shared')
        self.check(['git', 'merge', 'shared'], tier=3, code='unknown')
        self.check(['git', 'merge', 'feature'])


MANY = '- Max actions per hour: 1000\n'
REPO = ['--repo', 'github.com/example/demo']
MERGE = ['gh', 'pr', 'merge', '7'] + PIN + REPO
CREATE = ['gh', 'pr', 'create', '--head', 'topic'] + REPO
EDIT = ['gh', 'pr', 'edit', '7', '--title', 'Reviewed'] + REPO
PUSH = ['git', 'push', 'origin', 'HEAD:refs/heads/topic']
STRICT = {'Task choice': 'listed', 'Push and pull requests': 'no', 'Merge': 'no', 'Trusted authors': 'own', 'Roots': []}


class PolicyContextTest(AfkBase):
    """One identity-bound policy context decides the five project-scoped values, through the full check entry point."""

    def setUp(self):
        super().setUp()
        spec = importlib.util.spec_from_file_location('project_store_policy', SCRIPT.parent / 'project_store.py')
        self.store = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.store)

    def ident(self, root=None):
        found, ident = self.store.identity(root or self.repo)
        self.assertEqual(found, 'found')
        return ident

    def project(self, value, root=None):
        ident = self.ident(root)
        self.store.write_setting(ident.checkout, 'autopilot', value, ident=ident)

    def approval(self, root=None):
        return self.root / 'state/settings-approved' / (self.store.code_of(root or self.repo) + '.json')

    def settings_file(self, root=None):
        return (root or self.repo) / '.finolabs/vibecode/settings.json'

    def effective(self):
        status, output = self.invoke('effective')
        self.assertEqual(status, 0, output)
        return json.loads(output)

    def check_code(self, argv):
        status, output = self.invoke('check', '--argv-json', json.dumps(argv))
        result = json.loads(output)
        self.assertEqual(result['tier'] == 1, result['code'] == 'allowed', output)
        return result['code']

    def codes(self):
        """Every bound mutation's code, and proof that the effective view agrees with check."""
        found = {name: self.check_code(argv) for name, argv in
                 (('merge', MERGE), ('create', CREATE), ('edit', EDIT), ('push', PUSH))}
        values = self.effective()['values']
        self.assertEqual(found['merge'] == 'allowed', values['Merge'] == 'yes', (found, values))
        for name in ('create', 'edit', 'push'):
            self.assertEqual(found[name] == 'allowed', values['Push and pull requests'] == 'yes', (found, values))
        return found

    def git_repo(self, name, origin='https://github.com/example/demo.git'):
        import shutil
        import subprocess
        if not shutil.which('git', path=os.defpath + ':/usr/local/bin:/opt/homebrew/bin'):
            self.skipTest('git is not installed')
        repo = self.home / name
        repo.mkdir(parents=True)
        env = {'HOME': str(self.home), 'PATH': os.defpath + ':/usr/local/bin:/opt/homebrew/bin',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}

        def git(*argv, cwd=repo):
            return subprocess.run(['git', *argv], cwd=cwd, env=env, capture_output=True, check=True,
                                  text=True).stdout.strip()
        git('init', '-q', '-b', 'main')
        if origin:
            git('remote', 'add', 'origin', origin)
        git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com', 'commit', '-q',
            '--allow-empty', '-m', 'First')
        git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        git('checkout', '-q', '-b', 'topic')
        git('branch', 'feature')
        return repo, git

    # Part 2: the permission matrix

    def test_both_override_directions_and_omitted_keys_inherit(self):
        self.start(NO + MANY)
        self.assertEqual(self.effective()['values'], dict(STRICT, **{'Task choice': 'choose'}))
        self.assertEqual(self.codes(), {'merge': 'merge-disabled', 'create': 'push-disabled',
                                        'edit': 'push-disabled', 'push': 'push-disabled'})
        # user no -> project yes
        self.project({'merge': 'yes', 'push-and-pull-requests': 'yes'})
        self.assertEqual(set(self.codes().values()), {'allowed'})
        self.assertEqual(self.effective()['values']['Task choice'], 'choose')  # omitted, so inherited
        # user yes -> project no, with push omitted and so inherited
        self.assertEqual(self.invoke('stop')[0], 0)
        self.start(SETUP + MANY)
        self.project({'merge': 'no'})
        self.assertEqual(self.codes(), {'merge': 'merge-disabled', 'create': 'allowed', 'edit': 'allowed',
                                        'push': 'allowed'})
        # A new object replaces the whole old one: merge is no longer set, so the user's yes applies again.
        self.project({'task-choice': 'listed', 'roots': ['packages']})
        self.assertEqual(set(self.codes().values()), {'allowed'})
        self.assertEqual(self.effective()['values'], {'Task choice': 'listed', 'Push and pull requests': 'yes',
                                                      'Merge': 'yes', 'Trusted authors': 'own',
                                                      'Roots': ['packages']})
        self.assertEqual(self.effective()['repository'], 'found')

    def test_every_strict_state_gives_the_whole_strict_vector(self):
        self.start(SETUP + MANY)
        config = self.repo / '.git/config'
        wide = {'merge': 'yes', 'push-and-pull-requests': 'yes', 'task-choice': 'choose', 'roots': ['packages']}

        def invalid():
            raw = (json.dumps({'version': 1, 'autopilot': {'merge': 'yes', 'hosts': 'Codex'}}) + '\n').encode()
            self.settings_file().write_bytes(raw)
            record = json.loads(self.approval().read_text())
            record['sha256'] = hashlib.sha256(raw).hexdigest()
            self.approval().write_text(json.dumps(record))

        def untargeted():
            record = json.loads(self.approval().read_text())
            record.pop('target')
            self.approval().write_text(json.dumps(record))
        for name, inject in (('digest mismatch', lambda: self.settings_file().write_bytes(
                                  self.settings_file().read_bytes() + b' ')),
                             ('missing file', lambda: self.settings_file().unlink()),
                             ('unsafe file', lambda: self.settings_file().chmod(0o666)),
                             ('unreadable approval', lambda: self.approval().write_text('{')),
                             ('approval without a target', untargeted),
                             ('invalid approved settings', invalid),
                             ('origin changed after approval', lambda: config.write_text(
                                 ORIGIN_CONFIG.replace('example/demo', 'other/restricted')))):
            with self.subTest(state=name):
                config.write_text(ORIGIN_CONFIG)
                self.store.reset_settings(self.repo)
                self.project(wide)
                self.assertEqual(self.effective()['values']['Merge'], 'yes')
                inject()
                self.assertEqual(self.effective()['values'], STRICT)
                self.assertEqual(self.codes(), {'merge': 'merge-disabled', 'create': 'push-disabled',
                                                'edit': 'push-disabled', 'push': 'push-disabled'})
                (self.repo / 'packages').mkdir(exist_ok=True)
                self.check(paths=['packages/app.py'], tier=3, code='unknown')
        # Unknown identity: a discovery error and a .git link are strict too, never the user values.
        config.write_text(ORIGIN_CONFIG)
        locked = self.repo / 'locked'
        (locked / 'inner').mkdir(parents=True)
        locked.chmod(0o311)
        self.addCleanup(locked.chmod, 0o755)
        nested = self.repo / 'nested'
        nested.mkdir()
        (nested / '.git').symlink_to(self.home / 'elsewhere')
        for cwd in (locked / 'inner', nested):
            with self.subTest(cwd=cwd.name):
                self.cwd = cwd
                view = self.effective()
                self.assertEqual((view['repository'], view['values']), ('unknown', STRICT))
                self.assertEqual(self.check_code(MERGE), 'merge-disabled')
                self.assertEqual(self.check_code(['git', 'merge', 'origin/main']), 'unknown')

    def test_no_repository_lets_no_repository_mutation_qualify(self):
        self.start(SETUP + MANY)
        outside = self.home / 'outside'
        outside.mkdir()
        self.cwd = outside
        view = self.effective()
        self.assertEqual(view['repository'], 'absent')
        self.assertEqual(view['values']['Merge'], 'yes')  # the user value, with no extra roots
        for argv in (MERGE, CREATE, EDIT, PUSH, ['git', 'merge', 'origin/main'], ['git', 'merge', 'refs/heads/feature']):
            with self.subTest(argv=argv[:3]):
                self.assertNotEqual(self.check_code(argv), 'allowed')

    # Part 1: identity agreement

    def test_a_rejected_linked_worktree_never_regains_the_user_permissions(self):
        self.start(SETUP + MANY)
        main, git = self.git_repo('main')
        linked = self.home / 'linked'
        git('worktree', 'add', '-q', str(linked), '-b', 'side')
        self.project({'merge': 'no', 'push-and-pull-requests': 'no'}, root=main)
        self.cwd = linked
        self.assertEqual(self.ident(linked).main, main)
        self.assertEqual(self.codes(), {'merge': 'merge-disabled', 'create': 'push-disabled',
                                        'edit': 'push-disabled', 'push': 'push-disabled'})
        back = main / '.git/worktrees/linked/gitdir'
        good = back.read_text()
        for name, change in (('missing', back.unlink),
                             ('mismatched', lambda: back.write_text(str(self.home / 'elsewhere/.git') + '\n')),
                             ('unsafe', lambda: back.chmod(0o666))):
            with self.subTest(back_pointer=name):
                if back.exists():
                    back.unlink()
                back.write_text(good)
                back.chmod(0o644)
                change()
                view = self.effective()
                self.assertEqual((view['repository'], view['values']), ('unknown', STRICT))
                # With no identity the push has no branch context to read, so it is unknown before its permission.
                self.assertEqual(self.codes(), {'merge': 'merge-disabled', 'create': 'push-disabled',
                                                'edit': 'push-disabled', 'push': 'unknown'})
                for argv in (['git', 'merge', 'refs/heads/feature'], ['git', 'merge', 'origin/main']):
                    self.assertNotEqual(self.check_code(argv), 'allowed')
        back.write_text(good)
        back.chmod(0o644)
        self.assertEqual(self.effective()['repository'], 'found')

    def test_deep_descendants_and_nested_repositories_use_their_own_identity(self):
        self.start(SETUP + MANY)
        self.project({'merge': 'no'})
        deep = self.repo.joinpath(*['level'] * 30)
        deep.mkdir(parents=True)
        self.cwd = deep
        self.assertEqual(self.check_code(MERGE), 'merge-disabled')
        self.assertEqual(self.effective()['values']['Merge'], 'no')
        # A nested repository has its own identity and settings: no approval there, and no origin to bind.
        nested, _ = self.git_repo('checkout/vendor/inner', origin=None)
        self.cwd = nested
        view = self.effective()
        self.assertEqual((view['repository'], view['values']['Merge']), ('found', 'yes'))
        self.assertEqual(self.check_code(MERGE), 'unknown')  # the outer repository's target is not this one's

    # Part 3: target agreement

    def test_gh_mutations_need_one_explicit_full_host_repository_equal_to_the_verified_target(self):
        self.start(SETUP + MANY)
        for argv in (MERGE, CREATE, EDIT, ['gh', 'pr', 'merge', '7'] + PIN + ['--repo=github.com/EXAMPLE/Demo']):
            with self.subTest(argv=argv):
                self.check(argv)
        bases = (['gh', 'pr', 'merge', '7'] + PIN, ['gh', 'pr', 'create', '--head', 'topic'], ['gh', 'pr', 'edit', '7'])
        for selector, code in (([], 'unknown'), (['--repo', 'example/demo'], 'unknown'),
                               (['-R', 'github.com/example/demo'], 'unknown'),
                               (['--repo', 'https://github.com/example/demo'], 'unknown'),
                               (['--repo', 'github.com/example/demo.git'], 'unknown'),
                               (['--repo', 'other.example/example/demo'], 'unknown'),
                               (REPO + REPO, 'unknown'), (REPO + ['--repo', 'github.com/other/restricted'], 'unknown'),
                               (['--repo', 'github.com/other/restricted'], 'forbidden')):
            for base in bases:
                with self.subTest(selector=selector, argv=base[:3]):
                    self.assertEqual(self.check_code(base + selector), code)
        # gh's own implicit choices never matter: an explicit --repo wins over gh-resolved and GH_REPO.
        config = self.repo / '.git/config'
        config.write_text(ORIGIN_CONFIG + '\tgh-resolved = other/restricted\n')
        self.check(MERGE)
        self.assertEqual(self.check_code(['gh', 'pr', 'edit', '7']), 'unknown')
        config.write_text(ORIGIN_CONFIG)
        with patch.dict(os.environ, {'GH_REPO': 'other/restricted'}):
            self.check(EDIT)
            self.assertEqual(self.check_code(['gh', 'pr', 'edit', '7']), 'unknown')

    def test_pull_request_creation_needs_an_explicit_validated_head(self):
        self.start(SETUP + MANY)
        create = ['gh', 'pr', 'create', '--title', 'Example']
        self.check(create + ['--head', 'topic'] + REPO)
        self.check(create + ['--head=feature/one'] + REPO)
        for head, code in (([], 'unknown'), (['--head', 'main'], 'forbidden'), (['--head', 'MAIN'], 'forbidden'),
                           (['--head', 'HEAD'], 'unknown'), (['--head', 'other:topic'], 'unknown'),
                           (['--head', 'refs/heads/topic'], 'unknown'), (['-H', 'topic'], 'unknown'),
                           (['--head', 'topic', '--head', 'side'], 'unknown'), (['--head', 'a/../b'], 'unknown')):
            with self.subTest(head=head):
                self.assertEqual(self.check_code(create + head + REPO), code)

    def test_a_push_qualifies_only_when_its_effective_destination_is_bound(self):
        self.start(SETUP + MANY)
        config = self.repo / '.git/config'
        same, other = 'https://github.com/example/demo.git', 'https://github.com/other/restricted.git'
        for extra, code in (('', 'allowed'), ('\tpushurl = ' + same + '\n', 'allowed'),
                            ('\tpushurl = ' + other + '\n', 'unknown'),
                            ('\tpushurl = ' + same + '\n\tpushurl = ' + other + '\n', 'unknown'),
                            ('\tmirror = true\n', 'unknown'), ('\treceivepack = other\n', 'unknown'),
                            ('[url "https://github.com/other/"]\n\tpushInsteadOf = https://github.com/example/\n',
                             'unknown')):
            with self.subTest(extra=extra):
                config.write_text(ORIGIN_CONFIG + extra)
                self.assertEqual(self.check_code(PUSH), code)
        # An approved project binds its target: changing origin afterwards invalidates the approval.
        config.write_text(ORIGIN_CONFIG)
        self.project({'push-and-pull-requests': 'yes'})
        self.assertEqual(json.loads(self.approval().read_text())['target'], 'github.com/example/demo')
        self.check(PUSH)
        config.write_text(ORIGIN_CONFIG.replace('example/demo', 'other/restricted'))
        self.assertEqual(self.check_code(PUSH), 'push-disabled')
        self.assertEqual(self.check_code(['gh', 'pr', 'edit', '7', '--repo', 'github.com/other/restricted']),
                         'push-disabled')

    # Part 4: setup transitions

    def setup_cli(self, *argv):
        spec = importlib.util.spec_from_file_location('project_progress_policy',
                                                      ROOT / 'skills/setup/scripts/project_progress.py')
        pp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pp)
        out = io.StringIO()
        with patch('os.getcwd', return_value=str(self.repo)), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            status = pp.main(['settings', *argv])
        return status, out.getvalue()

    def preview(self, *argv):
        status, output = self.setup_cli(*argv, '--dry-run')
        self.assertEqual(status, 0, output)
        return json.loads(output)

    def apply(self, *argv):
        token = self.preview(*argv)['token']
        status, output = self.setup_cli(*argv, '--expect', token)
        self.assertEqual(status, 0, output)

    def test_setup_replaces_or_clears_the_whole_object_and_check_follows(self):
        self.start(NO + MANY)
        allow = ('--set', 'autopilot=' + json.dumps({'merge': 'yes', 'push-and-pull-requests': 'yes'}))
        shown = self.preview(*allow)
        self.assertEqual(shown['action'], 'replace')
        self.assertEqual(shown['target'], 'github.com/example/demo')
        self.assertEqual(shown['effective']['Merge'], 'yes (repository)')
        self.assertEqual(shown['effective']['Task choice'], 'choose (user)')
        self.assertFalse(self.settings_file().exists())  # a preview writes nothing
        self.apply(*allow)
        self.assertEqual(self.check_code(MERGE), 'allowed')
        # approved merge=yes -> every answer inherits -> the user's merge=no applies again
        cleared = self.preview('--clear', 'autopilot')
        self.assertEqual((cleared['action'], cleared['autopilot'], cleared['effective']['Merge']),
                         ('remove', None, 'no (user)'))
        self.apply('--clear', 'autopilot')
        self.assertEqual(self.check_code(MERGE), 'merge-disabled')
        self.assertEqual(self.preview('--clear', 'autopilot')['action'], 'none')
        # The reverse: user yes, approved project no, then all inherit.
        self.assertEqual(self.invoke('stop')[0], 0)
        self.start(SETUP + MANY)
        self.apply('--set', 'autopilot={"merge": "no"}')
        self.assertEqual(self.check_code(MERGE), 'merge-disabled')
        self.store.write_setting(self.repo, 'parallel', '4')  # an unrelated setting stays when the object goes
        self.apply('--clear', 'autopilot')
        self.assertEqual(self.check_code(MERGE), 'allowed')
        self.assertEqual(json.loads(self.settings_file().read_text()), {'version': 1, 'parallel': '4'})

    def test_apply_binds_to_the_previewed_identity_and_prior_settings(self):
        self.start(SETUP + MANY)
        change = ('--set', 'autopilot={"merge": "no"}')
        # No preview token, a wrong token, or a token from before a concurrent change: nothing is written.
        self.assertEqual(self.setup_cli(*change)[0], 1)
        self.assertEqual(self.setup_cli(*change, '--expect', '0' * 64)[0], 1)
        token = self.preview(*change)['token']
        self.store.write_setting(self.repo, 'parallel', '4')
        self.assertEqual(self.setup_cli(*change, '--expect', token)[0], 1)
        self.assertNotIn('autopilot', json.loads(self.settings_file().read_text()))
        token = self.preview(*change)['token']
        (self.repo / '.git/config').write_text(ORIGIN_CONFIG.replace('example/demo', 'example/renamed'))
        self.assertEqual(self.setup_cli(*change, '--expect', token)[0], 1)
        (self.repo / '.git/config').write_text(ORIGIN_CONFIG)
        # Cancelling (no apply after the preview) keeps the current settings.
        self.preview('--clear', 'autopilot')
        self.assertEqual(self.check_code(MERGE), 'allowed')
        self.apply(*change)
        self.assertEqual(self.check_code(MERGE), 'merge-disabled')

    def test_an_interrupted_settings_and_approval_pair_reads_strict(self):
        self.start(SETUP + MANY)
        for before, after in (({'merge': 'yes'}, {'merge': 'no'}), ({'merge': 'no'}, {'merge': 'yes'})):
            with self.subTest(before=before, after=after):
                self.store.reset_settings(self.repo)
                self.project(before)
                with patch.object(self.store, '_write_approval', side_effect=OSError('interrupted')):
                    with self.assertRaises(OSError):
                        self.project(after)
                self.assertEqual(self.effective()['values'], STRICT)
                self.assertEqual(self.check_code(MERGE), 'merge-disabled')

    # Part 5: one identity and one base for every grant

    def local_repo(self, path):
        """A checkout with local Git metadata, a work branch, a feature branch and no origin."""
        (path / '.git/refs/heads').mkdir(parents=True)
        (path / '.git/refs/remotes/origin').mkdir(parents=True)
        (path / '.git/HEAD').write_text('ref: refs/heads/topic\n')
        (path / '.git/refs/heads/feature').write_text('a' * 40 + '\n')
        (path / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/main\n')
        (path / '.git/config').write_text('[core]\n\trepositoryformatversion = 0\n\tbare = false\n')
        return path

    def colliding_pair(self):
        """Two distinct synthetic checkout paths whose eight-character repository codes are equal."""
        seen = {}
        for index in range(1 << 22):
            path = str(self.home / ('collision-%d' % index))
            code = self.store.code_of(path)
            if code in seen:
                return Path(seen[code]), Path(path)
            seen[code] = path
        self.fail('no colliding pair')

    def test_a_colliding_repository_code_never_borrows_another_checkouts_approval(self):
        self.start(NO + MANY)
        first, second = map(self.local_repo, self.colliding_pair())
        self.assertNotEqual(first, second)
        self.assertEqual(self.store.code_of(first), self.store.code_of(second))
        local = ['git', 'merge', 'refs/heads/feature']
        self.cwd = second
        self.assertEqual(self.check_code(local), 'merge-disabled')
        self.project({'merge': 'yes', 'roots': ['packages']}, root=first)
        self.cwd = first
        self.assertEqual(self.effective()['state'], 'project')
        self.assertEqual(self.check_code(local), 'allowed')
        # Only the settings bytes are copied: no approval was issued for the second checkout.
        copied = self.settings_file(second)
        copied.parent.mkdir(parents=True, mode=0o700)
        copied.write_bytes(self.settings_file(first).read_bytes())
        copied.chmod(0o600)
        (second / 'packages').mkdir()
        self.cwd = second
        view = self.effective()
        self.assertNotEqual(view['state'], 'project')
        self.assertEqual((view['values']['Merge'], view['values']['Roots']), ('no', []))
        self.assertEqual(self.check_code(local), 'merge-disabled')
        self.check(paths=['packages/app.py'], tier=3, code='unknown')

    def test_an_approval_without_this_checkouts_full_identity_grants_nothing(self):
        self.start(NO + MANY)
        wide = {'merge': 'yes', 'push-and-pull-requests': 'yes'}
        self.project(wide)
        self.assertEqual(json.loads(self.approval().read_text())['identity'],
                         hashlib.sha256(str(self.repo).encode()).hexdigest())
        for name, change in (('missing', lambda record: record.pop('identity')),
                             ('another checkout', lambda record: record.update(identity='0' * 64))):
            with self.subTest(binding=name):
                self.store.reset_settings(self.repo)
                self.project(wide)
                self.assertEqual(set(self.codes().values()), {'allowed'})
                record = json.loads(self.approval().read_text())
                change(record)
                self.approval().write_text(json.dumps(record))
                self.assertEqual(self.effective()['values'], STRICT)
                self.assertEqual(self.codes(), {'merge': 'merge-disabled', 'create': 'push-disabled',
                                                'edit': 'push-disabled', 'push': 'push-disabled'})
        # Approving again binds the record to this checkout, even when the value is unchanged.
        self.store.reset_settings(self.repo)
        self.project(wide)
        record = json.loads(self.approval().read_text())
        record.pop('identity')
        self.approval().write_text(json.dumps(record))
        self.project(wide)
        self.assertEqual(set(self.codes().values()), {'allowed'})

    def test_paths_are_judged_from_the_repository_root_never_from_cwd(self):
        self.start(SETUP + MANY)
        self.project({'roots': ['packages']})
        for folder in ('restricted/packages', '.github/packages', 'packages', 'src/inner'):
            (self.repo / folder).mkdir(parents=True, exist_ok=True)
        for cwd, operand, code in (('.', 'restricted/packages/app.py', 'unknown'),
                                   ('restricted', 'packages/app.py', 'unknown'),
                                   ('restricted', 'README.md', 'unknown'),
                                   ('.', '.github/packages/app.py', 'protected'),
                                   ('.github', 'packages/app.py', 'protected'),
                                   ('.github', 'README.md', 'protected'),
                                   ('.github', 'scripts/build.py', 'protected'),
                                   ('packages', 'app.py', 'allowed'),
                                   ('src', 'inner/example.py', 'allowed')):
            with self.subTest(cwd=cwd, operand=operand):
                self.cwd = self.repo / cwd
                self.check(paths=[operand], tier=1 if code == 'allowed' else 3, code=code)
                self.assertEqual(self.check_code(['git', 'add', '--', operand]), code)
                self.assertEqual(self.check_code(['git', 'diff', '--stat', operand]) == 'allowed', code == 'allowed')

    def test_an_away_evidence_file_is_judged_from_the_repository_root(self):
        self.start(SETUP_AWAY)
        (self.repo / '.github/.finolabs/briefs').mkdir(parents=True)
        (self.repo / '.finolabs/briefs').mkdir(parents=True)
        self.check(JUDGE)
        self.cwd = self.repo / '.github'
        self.assertEqual(self.check_code(JUDGE), 'unknown')
        evidence = JUDGE[:-1] + ['docs/notes.md']
        self.assertEqual(self.check_code(evidence), 'unknown')


SOURCE_PATHS = ('skills/example/SKILL.md', 'skills/example/references/hooks.md', 'skills/delegate/scripts/afk.py',
                'skills/review-gate/scripts/merge_check.py', 'scripts/hooks.py', 'CLAUDE.md', 'AGENTS.md',
                '.claude-plugin/hooks.json', '.codex-plugin/plugin.json')
LIVE_PATHS = ('.github/workflows/x.yml', '.claude/settings.json', '.claude/hooks/check.py', '.git/hooks/pre-push',
              'skills/example/.env', 'scripts/credentials.json', 'skills/example/CLAUDE.md', 'GEMINI.md',
              'CLAUDE.local.md', 'hooks/check.py', 'src/settings.json', 'host.md', 'state/autopilot/lease.json')
INSTALL_PATHS = ('skills/delegate/scripts/afk.py', 'skills/review-gate/scripts/merge_check.py',
                 'skills/delegate/scripts/helper.py', 'scripts/session_start.py', 'scripts/away_gate_hook.py',
                 '.claude-plugin/hooks.json', 'skills/afk/SKILL.md', 'skills/example/SKILL.md')


class AwayFlowTest(AfkBase):
    """The own-branch flow an away mandate authorizes: worktrees, PR text, limits, exit status, cleanup and source."""

    def git_repo(self, name):
        import shutil
        import subprocess
        if not shutil.which('git', path=os.defpath + ':/usr/local/bin:/opt/homebrew/bin'):
            self.skipTest('git is not installed')
        repo = self.home / name
        repo.mkdir()
        env = {'HOME': str(self.home), 'PATH': os.defpath + ':/usr/local/bin:/opt/homebrew/bin',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}

        def git(*argv, cwd=repo):
            return subprocess.run(['git', *argv], cwd=cwd, env=env, capture_output=True, check=True,
                                  text=True).stdout.strip()
        git('init', '-q', '-b', 'main')
        git('remote', 'add', 'origin', 'https://github.com/example/demo.git')
        git('-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.com', 'commit', '-q',
            '--allow-empty', '-m', 'First')
        git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        return repo, git

    def merged(self, pr, head):
        """An allowed `gh pr merge` check pins the number and head, then the merge entry records them."""
        self.check(['gh', 'pr', 'merge', pr, '--merge', '--match-head-commit', head, '--repo', 'github.com/example/demo'])
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', pr, '--head', head)[0], 0)

    def test_a_merge_entry_needs_an_allowed_merge_check_of_this_lease(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.cwd, _ = self.git_repo('pinned')
        head, other = 'c' * 40, 'd' * 40
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 3)  # no check yet
        for number in ('\u0667', '07', '0'):  # an Arabic-Indic seven, a leading zero, zero
            with self.subTest(number=number):
                self.check(['gh', 'pr', 'merge', number, '--match-head-commit', head, '--repo', 'github.com/example/demo'],
                           tier=3, code='unknown')
        self.check(['gh', 'pr', 'merge', '7', '--match-head-commit', other, '--repo', 'github.com/example/elsewhere'],
                   tier=3, code='forbidden')  # a denied check pins nothing
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', other)[0], 3)
        self.check(['gh', 'pr', 'merge', '7', '--squash', '--match-head-commit=' + head, '--repo', 'github.com/example/demo'])
        for pr, sha in (('8', head), ('7', other)):
            with self.subTest(pr=pr, sha=sha):
                self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', pr, '--head', sha)[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 0)
        self.invoke('stop')
        self.clock += 60
        self.start(SETUP + '- Max actions per hour: 1000\n')  # a new lease does not inherit the old pin
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 3)

    def worktree(self):
        """A main checkout on main and a registered linked worktree under its .claude/worktrees on branch work."""
        repo, git = self.git_repo('flow')
        tree = repo / '.claude/worktrees/wt'
        git('worktree', 'add', '-q', str(tree), '-b', 'work')
        return repo, tree, git

    def test_a_worktree_path_is_judged_from_inside_that_worktree(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        repo, tree, _ = self.worktree()
        ledger = ['python3', '-I', str(SCRIPT.parent / 'ledger.py'), 'start', '--checkout']
        self.cwd = repo
        self.check(ledger + [str(tree)])
        self.check(ledger + ['.claude/worktrees/wt'])
        self.check(['git', '-C', str(tree), 'status'])
        self.check(['git', '-C', '.claude/worktrees/wt', 'status', '--short'])
        self.check(['git', '-C', str(tree), 'add', '--', 'src/example.py'])
        self.cwd = tree  # the same commands from inside the worktree
        self.check(['git', 'status'])
        self.check(['git', 'add', '--', 'src/example.py'])
        # Inside the worktree its own live paths stay protected, through -C as from inside.
        self.check(['git', 'add', '--', '.claude/settings.json'], tier=3, code='protected')
        self.cwd = repo
        for path in ('.github/workflows/x.yml', '.claude/settings.json', '.git/hooks/pre-push'):
            with self.subTest(path=path):
                self.check(['git', '-C', str(tree), 'add', '--', path], tier=3, code='protected')
                self.check(ledger + [str(tree / path)], tier=3, code='protected')
        # Anything else under .claude stays protected: a folder that is not a registered worktree, the settings.
        (repo / '.claude/worktrees/stray').mkdir(parents=True)
        self.check(ledger + [str(repo / '.claude/worktrees/stray')], tier=3, code='protected')
        self.check(ledger + ['.claude/worktrees/stray'], tier=3, code='protected')
        self.check(['git', '-C', str(repo / '.claude/worktrees/stray'), 'status'], tier=3, code='unknown')
        self.check(['git', '-C', str(repo / '.claude'), 'status'], tier=3, code='unknown')
        self.check(paths=['.claude/settings.json'], tier=3, code='protected')
        # A worktree of another repository is never judged relatively.
        other, git = self.git_repo('other')
        foreign = other / '.claude/worktrees/x'
        git('worktree', 'add', '-q', str(foreign), '-b', 'x')
        self.check(ledger + [str(foreign)], tier=3, code='protected')
        self.check(['git', '-C', str(foreign), 'status'], tier=3, code='unknown')
        self.assertEqual(self.counts()['actions'], 7)

    def test_pull_request_text_is_data_and_a_body_file_is_screened(self):
        self.start(SETUP + '- Max actions per hour: 1000\n- Repository comments: decide\n')
        repo = '--repo', 'github.com/example/demo'
        create = ['gh', 'pr', 'create', '--head', 'topic', *repo]
        body = '## Summary\n\n- Fix the afk check for hooks, settings and SKILL.md ($5, 100%).\n\tIndented line.'
        for argv in (create + ['--title', 'Fix check', '--body', body],
                     create + ['--title', '-leading dash', '--body', '--repo github.com/other/restricted'],
                     create + ['--body=' + body],
                     ['gh', 'pr', 'edit', '7', '--body', body, *repo]):
            with self.subTest(argv=argv):
                self.check(argv)
        for argv, code in ((create + ['--body', 'Run $(id) first'], 'unknown'),
                           (create + ['--body', 'bell\x07'], 'unknown'),
                           (create + ['--body', 'Token ghp_' + 'x' * 30], 'unsafe'),
                           (create + ['--body', 'See /Us' + 'ers/synthetic/notes'], 'unsafe'),
                           (create + ['--body', 'x', '--body-file', 'body.md'], 'unknown'),
                           (['gh', 'pr', 'create', '--head', 'topic', '--body', '--repo=github.com/example/demo'], 'unknown'),
                           (['git', 'commit', '-m', 'Fix $(x)'], 'unknown'),
                           (['git', 'commit', '-m', 'Key ghp_' + 'x' * 30], 'unsafe')):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code=code)
        folder = self.repo / '.finolabs'  # the checkout's own git-ignored folder
        folder.mkdir()
        good = folder / 'body.md'
        good.write_text(body + '\nRun `afk.py check` or $(id) in a shell example.\r\n')
        for argv in (create + ['--body-file', str(good)], create + ['-F', str(good)],
                     ['gh', 'pr', 'edit', '7', '--body-file=' + str(good), *repo],
                     ['gh', 'pr', 'comment', '7', '--body-file', str(good), *repo],
                     ['gh', 'pr', 'comment', '7', '--body', body, *repo]):
            with self.subTest(argv=argv):
                self.check(argv)
        secret = folder / 'leaky.md'
        secret.write_text('Review notes\nghp_' + 'x' * 30 + '\n')
        link = folder / 'link.md'
        link.symlink_to(good)
        large = folder / 'large.md'
        large.write_text('x' * 70000)
        for name in (secret, link, large, folder / 'missing.md', folder, self.home):
            with self.subTest(name=name):
                self.check(create + ['--body-file', str(name)], tier=3, code='unsafe')
        self.check(create + ['--body-file', '-'], tier=3, code='unknown')
        self.check(['gh', 'pr', 'comment', '7', '--body-file', str(good)], tier=3, code='unknown')
        self.check(['gh', 'pr', 'comment', '7', *repo], tier=3, code='unknown')
        self.invoke('stop')  # without the category's decide answer a comment is Tier 3
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.check(['gh', 'pr', 'comment', '7', '--body-file', str(good), *repo], tier=3, code='forbidden')

    def test_only_a_tier_one_answer_reserves_an_action_or_a_run(self):
        self.start(SETUP + '- Max actions per hour: 2\n')
        ledger = ['python3', '-I', str(SCRIPT.parent / 'ledger.py'), 'start']
        for _ in range(5):
            self.check(ledger + ['--checkout', '.claude/settings.json'], tier=3, code='protected')
            self.check(['git', 'push', 'origin', 'main'], tier=3, code='forbidden')
        self.assertEqual(self.lease()['counters'], {})
        self.check(ledger)
        self.check(['git', 'status'])
        self.assertEqual((self.counts()['runs'], self.counts()['actions']), (1, 2))
        self.check(['git', 'status'], tier=3, code='limit')

    def test_a_commit_message_is_data(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        for argv in (['git', 'commit', '-m', 'Fix x for $5 cases'],
                     ['git', 'commit', '-q', '-m', 'Update hooks.json and SKILL.md', '-m', 'Body line one\nline two'],
                     ['git', 'commit', '--message=Rename settings and setup text']):
            with self.subTest(argv=argv):
                self.check(argv)

    def text_forms(self):
        """The pull request create form, its --repo pair and the checkout's own git-ignored .finolabs folder."""
        repo = ('--repo', 'github.com/example/demo')
        folder = self.repo / '.finolabs'
        folder.mkdir(exist_ok=True)
        return ['gh', 'pr', 'create', '--head', 'topic', *repo], repo, folder

    def test_a_review_marker_in_pull_request_or_commit_text_is_forbidden(self):
        self.start(SETUP + '- Max actions per hour: 1000\n- Repository comments: decide\n')
        create, repo, folder = self.text_forms()
        for marker in ('<!-- fnl-code-review head -->', '<!--fnl-security-review-->', '<!--\n  FNL-Code-Review -->'):
            text = 'Looks good.\n\n' + marker
            file = folder / 'review.md'
            file.write_text(text + '\n')
            for argv in (create + ['--body', text], create + ['--title', marker], create + ['--body=' + text],
                         create + ['-b=' + text], create + ['--body-file', str(file)], create + ['-F', str(file)],
                         ['gh', 'pr', 'edit', '7', '--body', text, *repo],
                         ['gh', 'pr', 'edit', '7', '--body-file', str(file), *repo],
                         ['gh', 'pr', 'comment', '7', '--body', text, *repo],
                         ['gh', 'pr', 'comment', '7', '--body-file', str(file), *repo],
                         ['git', 'commit', '-m', text], ['git', 'commit', '-m=' + text],
                         ['git', 'commit', '--message=' + text], ['git', 'commit', '-F', str(file)]):
                with self.subTest(marker=marker, argv=argv[:4]):
                    self.check(argv, tier=3, code='forbidden')
        self.check(create + ['--body', 'An HTML comment <!-- note --> and the fnl- prefix are data.'])

    def test_one_exact_router_line_in_a_pull_request_body_is_data(self):
        # merge_check requires the router line on every pull request, so an away flow must be able to write it.
        self.start(SETUP + '- Max actions per hour: 1000\n')
        create, repo, folder = self.text_forms()
        file = folder / 'pr.md'
        router = '<!-- fnl-router depth=MIN trigger=none -->'
        file.write_text(router + '\n\nWhat changed.\n')
        self.check(create + ['--body-file', str(file)])
        self.check(['gh', 'pr', 'edit', '7', '--body-file', str(file), *repo])
        for text in (router + '\n' + router, router + ' tail', '<!-- fnl-router depth=HUGE trigger=none -->',
                     router + '\n<!-- fnl-review kind=code head=x verdict=APPROVE -->'):
            file.write_text(text + '\n')
            with self.subTest(text=text):
                self.check(create + ['--body-file', str(file)], tier=3, code='forbidden')

    def test_inline_text_is_shell_safe_and_file_text_may_hold_shell_examples(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        create, _, folder = self.text_forms()
        file = folder / 'body.md'
        for text in ('Fix `check`', 'Uses $NAME', 'Uses ${NAME}', 'Uses $_x', 'Run $(id) first'):
            file.write_text(text + '\n')
            for argv in (create + ['--body', text], create + ['--title', text], ['git', 'commit', '-m', text]):
                with self.subTest(argv=argv[-2:]):
                    self.check(argv, tier=3, code='unknown')
            for argv in (create + ['--body-file', str(file)], ['git', 'commit', '-F', str(file)],
                         ['git', 'commit', '-q', '-F', '.finolabs/body.md']):
                with self.subTest(argv=argv[-2:], text=text):
                    self.check(argv)
        self.check(['git', 'commit', '-m', 'Costs $5, 100% of cases'])
        for argv in (['git', 'commit', '-F', str(file), '-m', 'Extra'], ['git', 'commit', '-F', str(file), '-F', str(file)],
                     ['git', 'commit', '-F=' + str(file)], ['git', 'commit', '-F' + str(file)], ['git', 'commit', '-F', '-']):
            with self.subTest(argv=argv[2:]):
                self.check(argv, tier=3, code='unknown')

    def test_a_body_file_must_lie_inside_the_checks_own_checkout(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        create, _, folder = self.text_forms()
        body = 'A clean description.\n'
        other = self.home / 'other'  # another repository
        (other / '.git').mkdir(parents=True)
        outside = (self.home / 'body.md', self.root / 'body.md', other / 'body.md')
        for path in (*outside, folder / 'body.md'):
            path.write_text(body)
        for path in outside:
            with self.subTest(path=path):
                self.check(create + ['--body-file', str(path)], tier=3, code='unsafe')
                self.check(['git', 'commit', '-F', str(path)], tier=3, code='unsafe')
        self.check(create + ['--body-file', str(folder / 'body.md')])
        self.check(create + ['--body-file', '.finolabs/body.md'])
        self.check(['git', 'commit', '-F', str(folder / 'body.md')])
        # A link on the way out of the checkout, or a `..` step, is refused.
        (self.repo / 'linked').symlink_to(self.home, target_is_directory=True)
        for name in ('linked/body.md', '.finolabs/../.finolabs/body.md'):
            with self.subTest(name=name):
                self.check(create + ['--body-file', name], tier=3, code='unsafe')

    def test_check_exits_three_on_tier_three_and_zero_on_tier_one(self):
        self.start()
        for argv, status, tier in ((['git', 'status'], 0, 1), (['git', 'push', 'origin', 'main'], 3, 3),
                                   (['git', 'show', 'HEAD:.env'], 3, 3), (['echo', 'safe'], 3, 3)):
            with self.subTest(argv=argv):
                result = self.invoke('check', '--argv-json', json.dumps(argv))
                self.assertEqual(result[0], status, result)
                self.assertEqual(json.loads(result[1])['tier'], tier)
        self.assertEqual(self.invoke('check', '--paths', '.github/workflows/x.yml')[0], 3)
        self.invoke('stop')
        self.assertEqual(self.invoke('check', '--argv-json', '["git", "status"]')[0], 3)  # no lease

    def test_merged_worktree_and_branch_cleanup_and_tracked_removal(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        repo, tree, git = self.worktree()
        git('branch', 'done')
        self.cwd = repo
        # Only the worktree of a pull request this lease merged: its HEAD is a head a merge entry recorded.
        self.check(['git', 'worktree', 'remove', str(tree)], tier=3, code='unknown')
        self.merged('7', 'b' * 40)
        self.check(['git', 'worktree', 'remove', str(tree)], tier=3, code='unknown')
        head = git('rev-parse', 'HEAD', cwd=tree)
        for flags in (('--kind', 'merge', '--head', head.upper()), ('--kind', 'merge', '--head', head[:12]),
                      ('--kind', 'action', '--head', head), ('--kind', 'merge', '--head', head)):
            with self.subTest(flags=flags):
                self.assertEqual(self.invoke('log', *flags)[0], 3)
        self.check(['git', 'worktree', 'remove', str(tree)], tier=3, code='unknown')
        self.merged('7', head)
        for argv in (['git', 'worktree', 'remove', str(tree)], ['git', 'worktree', 'remove', '--', str(tree)],
                     ['git', 'worktree', 'remove', '.claude/worktrees/wt'],
                     ['git', 'branch', '-d', 'done'], ['git', 'branch', '-d', '--', 'done']):
            with self.subTest(argv=argv):
                self.check(argv)
        for argv, code in ((['git', 'worktree', 'remove', '--force', str(tree)], 'forbidden'),
                           (['git', 'worktree', 'remove', '-f', str(tree)], 'forbidden'),
                           (['git', 'worktree', 'remove', str(repo)], 'forbidden'),
                           (['git', 'worktree', 'remove', '.'], 'forbidden'),
                           (['git', 'worktree', 'add', str(tree)], 'unknown'),
                           (['git', 'branch', '-D', 'done'], 'unknown'),
                           (['git', 'branch', '-d', 'main'], 'forbidden'),
                           (['git', 'branch', '-d', 'missing'], 'unknown'),
                           (['git', 'branch', '-d', 'done', 'work'], 'unknown')):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code=code)
        self.cwd = tree  # the current checkout and its own branch stay
        self.check(['git', 'worktree', 'remove', str(tree)], tier=3, code='unknown')
        self.check(['git', 'branch', '-d', 'work'], tier=3, code='unknown')
        # git rm of tracked files on the work branch classifies each path like a change.
        for argv in (['git', 'rm', 'src/old.py'], ['git', 'rm', '-q', '--', 'src/old.py', 'docs/old.md'],
                     ['git', 'rm', '-r', 'skills/example/SKILL.md']):
            with self.subTest(argv=argv):
                self.check(argv)
        for argv, code in ((['git', 'rm', '-f', 'src/old.py'], 'unknown'), (['git', 'rm', '--cached', 'src/old.py'], 'unknown'),
                           (['git', 'rm', '--', '.github/workflows/x.yml'], 'protected'),
                           (['git', 'rm', 'unknown/file.py'], 'unknown')):
            with self.subTest(argv=argv):
                self.check(argv, tier=3, code=code)
        self.cwd = repo  # on the default branch
        self.check(['git', 'rm', 'src/old.py'], tier=3, code='forbidden')
        self.invoke('stop')
        self.start(SETUP.replace('- Merge: yes', '- Merge: no'))
        self.check(['git', 'worktree', 'remove', str(tree)], tier=3, code='merge-disabled')
        self.check(['git', 'branch', '-d', 'done'], tier=3, code='merge-disabled')

    def test_plugin_source_is_known_on_a_work_branch_and_live_config_stays_protected(self):
        self.start(SETUP + '- Max actions per hour: 1000\n')
        self.assertEqual((self.repo / '.git/HEAD').read_text(), 'ref: refs/heads/topic\n')
        for path in SOURCE_PATHS:
            with self.subTest(path=path):
                self.check(paths=[path])
                self.check(['git', 'add', '--', path])
        self.check(paths=list(SOURCE_PATHS))
        for path in LIVE_PATHS:
            with self.subTest(path=path):
                self.check(paths=[path], tier=3, code='protected')
                self.check(['git', 'add', '--', path], tier=3, code='protected')
        for path in ('/' + 'tmp/settings.json', str(self.home / '.claude/settings.json'), str(self.root / 'host.md')):
            with self.subTest(path=path):
                self.check(paths=[path], tier=3, code='protected')
        # The default branch keeps every source path protected.
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')
        for path in SOURCE_PATHS:
            with self.subTest(path=path, branch='main'):
                # A manifest with no protected name is outside the built-in roots there.
                self.check(paths=[path], tier=3, code='unknown' if path == '.codex-plugin/plugin.json' else 'protected')
                self.check(['git', 'add', '--', path], tier=3,
                           code='unknown' if path == '.codex-plugin/plugin.json' else 'protected')
        # Without Push and pull requests and Merge, a work branch is not enough.
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/topic\n')
        off = SETUP.replace('- Merge: yes', '- Merge: no').replace('requests: yes', 'requests: no')
        self.invoke('stop')
        self.start(off)
        self.check(paths=['skills/example/SKILL.md'], tier=3, code='protected')

    def install_into(self, folder):
        """Copy this plugin's scripts into `folder`, which then is the running install's plugin root."""
        import shutil
        for skill in ('delegate', 'review-gate'):
            shutil.copytree(ROOT / 'skills' / skill / 'scripts', folder / 'skills' / skill / 'scripts')
        return folder / 'skills/delegate/scripts/afk.py'

    def test_this_installs_own_scripts_stay_protected_on_a_work_branch(self):
        # A real repository that is itself this install: every path in its checkout stays protected on every branch.
        install, git = self.git_repo('install')
        tree = install / '.claude/worktrees/wt'
        git('worktree', 'add', '-q', str(tree), '-b', 'work')
        global SCRIPT
        saved, SCRIPT = SCRIPT, self.install_into(install)
        try:
            self.start(SETUP + '- Max actions per hour: 1000\n')
            self.cwd = install
            for branch in ('topic', 'main'):
                git('symbolic-ref', 'HEAD', 'refs/heads/' + branch)
                for path in INSTALL_PATHS:
                    with self.subTest(path=path, branch=branch):
                        self.check(paths=[path], tier=3, code='protected')
                        self.check(['git', 'add', '--', path], tier=3, code='protected')
                        self.check(paths=[str(install / path)], tier=3, code='protected')
            # An absolute operand from another checkout reaches the install too.
            self.cwd = self.repo
            self.check(['git', 'add', '--', str(install / 'scripts/session_start.py')], tier=3, code='protected')
            # A linked worktree of the install's repository, under its .claude/worktrees, stays editable.
            self.cwd = tree
            for path in ('skills/example/SKILL.md', 'skills/afk/SKILL.md', 'scripts/session_start.py',
                         'scripts/away_gate_hook.py', '.claude-plugin/hooks.json', 'src/example.py'):
                with self.subTest(path=path, checkout='worktree'):
                    self.check(paths=[path])
                    self.check(['git', 'add', '--', path])
            self.cwd = install
            self.check(['git', '-C', str(tree), 'add', '--', 'skills/example/SKILL.md'])
            # A git command that changes the install's work tree without naming a path stays protected too.
            git('symbolic-ref', 'HEAD', 'refs/heads/topic')
            for argv in (['git', 'merge', '--no-ff', '--no-edit', 'refs/heads/main'], ['git', 'merge', 'origin/main'],
                         ['git', 'commit', '-m', 'Example'], ['git', 'pull']):
                with self.subTest(argv=argv, checkout='install'):
                    self.check(argv, tier=3, code='protected')
            self.cwd = tree  # from a linked worktree of the install's own repository, -C reaches the install
            for argv in (['git', '-C', str(install), 'merge', '--no-ff', '--no-edit', 'refs/heads/main'],
                         ['git', '-C', str(install), 'commit', '-m', 'Example']):
                with self.subTest(argv=argv, checkout='-C install'):
                    self.check(argv, tier=3, code='protected')
        finally:
            SCRIPT = saved

    def test_an_install_that_is_the_main_checkout_cleans_up_a_merged_worktree(self):
        # A dev install read from the main checkout runs the merge gate's cleanup from there: removing another,
        # merged linked worktree changes neither the install's work tree, its index nor its HEAD.
        repo, tree, git = self.worktree()
        global SCRIPT
        saved, SCRIPT = SCRIPT, self.install_into(repo)
        try:
            self.start(SETUP + '- Max actions per hour: 1000\n')
            self.cwd = repo
            self.merged('7', git('rev-parse', 'HEAD', cwd=tree))
            for argv in (['git', 'worktree', 'remove', str(tree)], ['git', 'worktree', 'remove', '--', '.claude/worktrees/wt']):
                with self.subTest(argv=argv):
                    self.check(argv)
            for argv, code in ((['git', 'worktree', 'remove', '--force', str(tree)], 'forbidden'),
                               (['git', 'worktree', 'remove', '.'], 'protected'),
                               (['git', 'worktree', 'add', str(repo / 'new')], 'protected'),
                               (['git', 'worktree', 'prune'], 'unknown'),
                               (['git', 'commit', '-m', 'Example'], 'protected'),
                               (['git', 'stash'], 'protected'),
                               (['git', 'reset', '--hard'], 'protected'),
                               (['git', '-C', 'skills', 'commit', '-m', 'Example'], 'protected'),
                               (['git', '-C', str(repo / 'skills'), 'restore', '.'], 'protected')):
                with self.subTest(argv=argv):
                    self.check(argv, tier=3, code=code)
            self.cwd = repo / 'skills/delegate'  # a subfolder of the install changes the install's own work tree too
            for argv in (['git', 'commit', '-m', 'Example'], ['git', 'stash']):
                with self.subTest(argv=argv, cwd='subfolder'):
                    self.check(argv, tier=3, code='protected')
        finally:
            SCRIPT = saved

    def test_the_worktree_holding_this_install_is_never_removed(self):
        repo, tree, git = self.worktree()
        global SCRIPT
        saved, SCRIPT = SCRIPT, self.install_into(tree)
        try:
            self.start(SETUP + '- Max actions per hour: 1000\n')
            self.cwd = repo
            self.merged('7', git('rev-parse', 'HEAD', cwd=tree))
            for operand in (str(tree), '.claude/worktrees/wt'):
                with self.subTest(operand=operand):
                    self.check(['git', 'worktree', 'remove', operand], tier=3, code='protected')
        finally:
            SCRIPT = saved


if __name__ == '__main__':
    unittest.main()
