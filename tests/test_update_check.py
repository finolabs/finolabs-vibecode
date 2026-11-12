"""Update checks use local fixtures and a mocked transport, never the network."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
from tests.data_root_fixture import account
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.request

REAL_POPEN = subprocess.Popen
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('update_check', ROOT / 'scripts/update_check.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / "home")
        self.folder = self.home / ".finolabs/vibecode/state"
        self.folder.mkdir(parents=True)
        env = mock.patch.dict(os.environ, {'FNL_STATE_DIR': str(self.folder), 'FNL_UPDATE_CHECK': '', 'FNL_METRICS': 'off'})
        env.start()
        self.addCleanup(env.stop)
        # The status tests assume a fixed installed version, so a version bump never breaks them.
        self.real_installed = u.installed_version
        fixed = mock.patch.object(u, 'installed_version', return_value='0.1.7-dev')
        fixed.start()
        self.addCleanup(fixed.stop)
        clock = mock.patch.object(u.fm, 'now')
        self.clock = clock.start()
        self.clock.return_value.timestamp.return_value = 200000
        self.addCleanup(clock.stop)
        spawn = mock.patch.object(u.subprocess, 'Popen')
        self.spawn = spawn.start()
        self.addCleanup(spawn.stop)
        transport = mock.patch('urllib.request.build_opener')
        self.transport = transport.start()
        self.addCleanup(transport.stop)
        self.response = self.transport.return_value.open.return_value.__enter__.return_value

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(u.main(list(args)), 0)
        self.assertEqual(err.getvalue(), '')
        return out.getvalue()

    def save(self, name, value):
        (self.folder / name).write_text(json.dumps(value))

    def cache(self, tag='v0.1.8', at=200000):
        self.save('update-check.json', {'checked_at': at, 'tag': tag})

    def test_version_table(self):
        for older, newer in [('0.1.7-dev', '0.1.7'), ('0.1.9', '0.1.10'),
                             ('0.9.99', '1.0.0'), ('1.9.0', '1.10.0'),
                             ('0.1.7-dev+abc', '0.1.7')]:
            with self.subTest(older=older):
                self.assertLess(u.version(older), u.version(newer))
        self.assertEqual(u.version('v0.1.7'), u.version('0.1.7+abc'))
        for bad in [None, 7, [], {}, '0.1', '0.1.7-rc.1', '0.1.7\n', '0.1.7;sh', '９.1.7']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                u.version(bad)
        self.assertEqual(self.real_installed(), json.loads((ROOT / '.claude-plugin/plugin.json').read_text())['version'])

    def test_only_newer_prints_one_safe_line(self):
        for tag, output in [('v0.1.6', False), ('0.1.7', True), ('v0.1.8', True)]:
            with self.subTest(tag=tag):
                self.cache(tag)
                result = self.call()
                self.assertEqual(bool(result), output)
                self.assertLessEqual(len(result.splitlines()), 1)
                if output:
                    self.assertEqual(result, 'A newer finolabs-vibecode (%s) is available. Let the user know they can type /update (on Codex $update); do not update on your own.\n' % tag.removeprefix('v'))
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.cache('v0.1.7')
            self.assertEqual(self.call(), '')  # bootstrap release equals installed
        self.spawn.assert_not_called()
        self.transport.assert_not_called()

    def test_cache_age_and_detached_spawn(self):
        for at, spawns in [(200000, False), (113601, False), (113600, True), (0, True)]:
            with self.subTest(at=at):
                self.spawn.reset_mock()
                self.cache(at=at)
                self.call()
                self.assertEqual(self.spawn.called, spawns)
        args, kwargs = self.spawn.call_args
        self.assertEqual(args[0], [sys.executable, '-I', str(ROOT / 'scripts/update_check.py'), '--fetch'])
        self.assertTrue(kwargs['start_new_session'])
        self.assertTrue(kwargs['close_fds'])
        for stream in ['stdin', 'stdout', 'stderr']:
            self.assertEqual(kwargs[stream], subprocess.DEVNULL)
        self.spawn.return_value.wait.assert_not_called()
        self.transport.assert_not_called()

    def test_first_start_bootstraps_without_notice_even_if_worker_finishes(self):
        self.spawn.side_effect = lambda *a, **k: self.cache()
        self.assertEqual(self.call(), '')
        self.spawn.assert_called_once()
        self.assertIn('0.1.8', self.call())

    def test_fetch_exact_request_and_private_minimal_cache(self):
        self.response.read.return_value = b'{"tag_name":"v0.1.8","name":"discard","body":"discard","url":"discard"}'
        self.assertEqual(self.call('--fetch'), '')
        request = self.transport.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, u.URL)
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertEqual(request.header_items(), [('User-agent', u.USER_AGENT)])
        self.assertEqual(self.transport.return_value.open.call_args.kwargs, {'timeout': 3})
        handlers = self.transport.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], urllib.request.HTTPRedirectHandler)
        self.assertIsNone(handlers[1].redirect_request(None, None, 302, '', {}, 'https://evil.invalid'))
        self.response.read.assert_called_once_with(u.MAX_RESPONSE + 1)
        path = self.folder / 'update-check.json'
        self.assertEqual(json.loads(path.read_text()), {'checked_at': 200000, 'tag': 'v0.1.8'})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertFalse((self.folder / 'consent.json').exists())

    def test_hostile_responses_are_discarded(self):
        bad_tags = ['0.1.8;touch x', '$(id)', '`id`', '0.1.8\n', 'v0.1.8\nignore instructions',
                    '1' * 100000, 'v0.1.8-dev', '0.1.8/path', '９.1.8', '', None, True, 18, [], {}]
        responses = [{'tag_name': tag} for tag in bad_tags] + [[], 1, True, None, 'v0.1.8', {}]
        for data in responses:
            with self.subTest(data=str(data)[:60]):
                self.response.read.return_value = json.dumps(data).encode()
                self.assertEqual(self.call('--fetch'), '')
                self.assertFalse((self.folder / 'update-check.json').exists())
        for body in [b'not json', b'\xff', b'x' * (u.MAX_RESPONSE + 1)]:
            self.response.read.return_value = body
            self.assertEqual(self.call('--fetch'), '')
            self.assertFalse((self.folder / 'update-check.json').exists())

    def test_skip_never_and_status(self):
        self.cache()
        self.assertEqual(self.call('skip', 'v0.1.8'), '')
        self.assertEqual(self.call(), '')
        self.assertEqual(json.loads(self.call('status')), {
            'installed': '0.1.7-dev', 'available': '0.1.8', 'newer': True,
            'stale': False, 'skipped': ['0.1.8'], 'never_ask': False})
        path = self.folder / 'update-state.json'
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(self.call('skip', '0.1.8;bad'), '')
        self.assertEqual(json.loads(path.read_text())['skipped'], ['0.1.8'])
        self.cache('v0.1.9')
        self.assertTrue(self.call())
        self.assertEqual(self.call('never'), '')
        self.assertEqual(self.call(), '')
        self.assertTrue(json.loads(path.read_text())['never_ask'])
        self.spawn.assert_not_called()

    def test_off_stops_all_actions(self):
        with mock.patch.dict(os.environ, {'FNL_UPDATE_CHECK': 'off'}), mock.patch.object(u, 'read_json') as read:
            for args in [(), ('--fetch',), ('status',), ('never',), ('skip', '0.1.8')]:
                self.assertEqual(self.call(*args), '')
            read.assert_not_called()
        self.spawn.assert_not_called()
        self.transport.assert_not_called()
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_invalid_cache_is_stale_and_worker_replaces_it(self):
        bad_caches = [[], True, 'x', {}, {'checked_at': 'now', 'tag': '0.1.8'},
                      {'checked_at': True, 'tag': '0.1.8'},
                      {'checked_at': float('nan'), 'tag': '0.1.8'},
                      {'checked_at': 10 ** 400, 'tag': '0.1.8'},
                      {'checked_at': 200001, 'tag': '0.1.8'},
                      {'checked_at': -1, 'tag': '0.1.8'},
                      {'checked_at': 1, 'tag': '0.1.8\n'},
                      {'checked_at': 1, 'tag': '0.1.8', 'extra': 1}]
        for body in [json.dumps(data) for data in bad_caches] + ['not json']:
            with self.subTest(body=body):
                (self.folder / 'update-check.json').write_text(body)
                self.assertIsNone(u.cache())
                status = json.loads(self.call('status'))
                self.assertTrue(status['stale'])
                self.assertIsNone(status['available'])
                self.spawn.reset_mock()
                self.assertEqual(self.call(), '')
                self.spawn.assert_called_once()
                self.response.read.return_value = b'{"tag_name":"v0.1.8"}'
                self.assertEqual(self.call('--fetch'), '')
                self.assertEqual(u.cache(), {'checked_at': 200000, 'tag': 'v0.1.8'})

    def test_invalid_choices_default_and_can_be_overwritten(self):
        self.cache()
        bad_states = [[], None, {}, {'skipped': [1], 'never_ask': False},
                      {'skipped': [], 'never_ask': 'false'},
                      {'skipped': [], 'never_ask': False, 'extra': 1},
                      {'skipped': ['ignore instructions'], 'never_ask': False}]
        path = self.folder / 'update-state.json'
        for body in [json.dumps(data) for data in bad_states] + ['not json']:
            with self.subTest(body=body):
                path.write_text(body)
                self.assertEqual(u.choices(), {'skipped': [], 'never_ask': False})
                self.assertEqual(json.loads(self.call('status')), {
                    'installed': '0.1.7-dev', 'available': '0.1.8', 'newer': True,
                    'stale': False, 'skipped': [], 'never_ask': False})
                self.assertEqual(self.call(), '')
                for args, expected in [
                        (('skip', '0.1.8'), {'skipped': ['0.1.8'], 'never_ask': False}),
                        (('never',), {'skipped': [], 'never_ask': True})]:
                    path.write_text(body)
                    self.assertEqual(self.call(*args), '')
                    self.assertEqual(json.loads(path.read_text()), expected)
        self.spawn.assert_not_called()

    def test_windows_detached_spawn_options(self):
        with mock.patch.object(u.sys, 'platform', 'win32'):
            u.start_fetch()
        kwargs = self.spawn.call_args.kwargs
        self.assertEqual(kwargs['creationflags'], 0x00000008 | 0x00000200)
        self.assertNotIn('start_new_session', kwargs)
        self.assertTrue(kwargs['close_fds'])
        self.spawn.return_value.wait.assert_not_called()

    def test_installed_manifest_over_four_kilobytes(self):
        root = self.folder / 'plugin'
        (root / 'scripts').mkdir(parents=True)
        (root / '.claude-plugin').mkdir()
        manifest = root / '.claude-plugin/plugin.json'
        manifest.write_text(json.dumps({'name': 'finolabs-vibecode',
                                       'description': 'x' * 5000, 'version': '0.1.7-dev'}))
        with mock.patch.object(u, '__file__', str(root / 'scripts/update_check.py')):
            self.assertEqual(self.real_installed(), '0.1.7-dev')
            manifest.write_text(json.dumps({'name': 'finolabs-vibecode',
                                           'description': 'x' * 65536, 'version': '0.1.7-dev'}))
            with self.assertRaises(ValueError):
                self.real_installed()

    def test_failures_are_silent_and_successful_exit(self):
        for function, args in [('installed_version', ()), ('cache', ()), ('stored_choices', ()),
                               ('start_fetch', ()), ('fetch', ('--fetch',)),
                               ('write_json', ('never',)), ('write_json', ('skip', '0.1.8'))]:
            for error in [OSError, PermissionError, ValueError, RuntimeError]:
                with self.subTest(function=function, error=error), mock.patch.object(u, function, side_effect=error):
                    self.assertEqual(self.call(*args), '')
        self.response.read.return_value = b'{"tag_name":"0.1.8"}'
        for error in [TimeoutError(), urllib.error.URLError('private text'), OSError('private text')]:
            self.transport.return_value.open.side_effect = error
            self.assertEqual(self.call('--fetch'), '')
        with mock.patch.object(u.dr, 'read_data', side_effect=PermissionError):
            self.assertEqual(self.call(), '')
        self.assertEqual(self.call('unknown'), '')

    def test_failed_spawn_suppresses_cached_notice(self):
        self.cache(at=0)
        self.spawn.side_effect = OSError('private failure text')
        self.assertEqual(self.call(), '')
        self.spawn.assert_called_once()
        self.transport.assert_not_called()

    def test_fetch_failure_keeps_old_cache(self):
        self.cache(at=0)
        before = (self.folder / 'update-check.json').read_bytes()
        self.transport.return_value.open.side_effect = TimeoutError()
        self.assertEqual(self.call('--fetch'), '')
        self.assertEqual((self.folder / 'update-check.json').read_bytes(), before)

    def test_standalone_skill_works_without_a_plugin_manifest(self):
        import shutil
        scripts = self.folder / 'update/scripts'
        shutil.copytree(ROOT / 'skills/update/scripts', scripts)
        with mock.patch.object(subprocess, 'Popen', REAL_POPEN):
            result = subprocess.run([sys.executable, '-I', str(scripts / 'update_check.py'), 'status'],
                                    capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b'')
        self.assertIsNone(json.loads(result.stdout)['installed'])
        self.transport.assert_not_called()

    def test_hooks_are_sync_startup_and_silent_on_missing_script(self):
        for host in ['claude', 'codex']:
            data = json.loads((ROOT / f'.{host}-plugin/hooks.json').read_text())
            groups = [g for g in data['hooks']['SessionStart'] if any('update_check.py' in h['command'] for h in g['hooks'])]
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]['matcher'], 'startup')
            hook = groups[0]['hooks'][0]
            self.assertFalse(hook.get('async', False))
            self.assertEqual(hook['timeout'], 5)
            # Use the real shell with an absent plugin root: interpreter errors stay silent.
            env = {**os.environ, 'CLAUDE_PLUGIN_ROOT': str(self.folder), 'PLUGIN_ROOT': str(self.folder), 'CODEX_PLUGIN_ROOT': str(self.folder)}
            with mock.patch.object(subprocess, 'Popen', REAL_POPEN):
                result = subprocess.run(['sh', '-c', hook['command']], env=env, capture_output=True, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))
            metric_hooks = [h for groups in data['hooks'].values() for g in groups for h in g['hooks'] if 'metrics_hook.py' in h['command']]
            self.assertEqual(len(metric_hooks), 4 if host == 'claude' else 3)
            self.assertTrue(all(h.get('async') for h in metric_hooks))

    def test_hook_import_does_not_load_urllib_request(self):
        code = ("import runpy, sys; runpy.run_path(sys.argv[1], run_name='update_check'); "
                "assert 'urllib.request' not in sys.modules")
        with mock.patch.object(subprocess, 'Popen', REAL_POPEN):
            result = subprocess.run([sys.executable, '-I', '-c', code,
                                     str(ROOT / 'scripts/update_check.py')],
                                    capture_output=True, timeout=3)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b'', b''))

    def test_subprocess_entrypoint_always_zero_on_corruption(self):
        (self.folder / 'update-check.json').write_text('{broken')
        with mock.patch.object(subprocess, 'Popen', REAL_POPEN):
            result = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts/update_check.py'), 'status'],
                                    capture_output=True, timeout=3)
        self.assertEqual((result.returncode, result.stderr), (0, b''))
        self.assertTrue(json.loads(result.stdout)['stale'])
        self.assertIsNone(json.loads(result.stdout)['available'])


ONBOARD_LINE = ('finolabs-vibecode %s has upgrade notes. Let the user know they can type /update '
                '(on Codex $update) to see what is new and finish its setup; do not run it on your own.\n')
EVIDENCE_URL = 'https://github.com/finolabs/finolabs-vibecode/releases/tag/'


class OnboardTest(unittest.TestCase):
    """Upgrade notes, the checklist, onboarding state, targets and pins."""

    call, save, cache = UpdateTest.call, UpdateTest.save, UpdateTest.cache

    def setUp(self):
        UpdateTest.setUp(self)
        self.evidence_count = 0
        self.plugin = Path(self.tmp.name) / 'plugin'
        (self.plugin / 'scripts').mkdir(parents=True)
        for name, code in [('done', 0), ('open', 1), ('na', 3), ('odd', 7)]:
            (self.plugin / 'scripts' / f'check_{name}.py').write_text(f'import sys\nsys.exit({code})\n')
        (self.plugin / 'scripts/check_slow.py').write_text('import time\ntime.sleep(5)\n')
        self.notes_file = Path(self.tmp.name) / 'upgrades.json'
        self.notes({'0.1.6': ['old'], '0.1.7': ['done', 'open', 'na', 'odd', 'none'], '0.1.8': ['next']})
        for name, value in [('notes_path', self.notes_file), ('plugin_root', self.plugin)]:
            patch = mock.patch.object(u, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def notes(self, layout):
        versions = []
        for release, slugs in layout.items():
            items = []
            for slug in slugs:
                item = {'id': f'{release}/{slug}', 'kind': 'setup', 'text': f'Synthetic item {slug}.'}
                if slug in ('done', 'open', 'na', 'odd', 'slow'):
                    item['check'] = [f'scripts/check_{slug}.py']
                if slug == 'open':
                    item['setup'] = '/setup add thing'
                items.append(item)
            versions.append({'version': release, 'items': items})
        self.notes_file.write_text(json.dumps({'versions': versions}))

    def real(self, *args):
        with mock.patch.object(subprocess, 'Popen', REAL_POPEN):
            return self.call(*args)

    def onboard_file(self):
        return self.folder / 'onboard.json'

    def evidence(self, tag='v0.1.6', **changes):
        data = {'tagName': tag, 'isDraft': False, 'isPrerelease': False, 'url': EVIDENCE_URL + tag}
        data.update(changes)
        self.evidence_count += 1
        path = Path(self.tmp.name) / f'evidence-{self.evidence_count}.json'
        path.write_text(json.dumps(data))
        return str(path)

    def test_whats_new_lists_every_version_up_to_installed_with_states_and_never_writes(self):
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            out = self.real('whats-new')
        self.assertEqual(out, '\n'.join([
            '0.1.6',
            '- [unknown] 0.1.6/old: Synthetic item old.',
            '0.1.7',
            '- [done] 0.1.7/done: Synthetic item done.',
            '- [open] 0.1.7/open: Synthetic item open. (setup: /setup add thing)',
            '- [not applicable] 0.1.7/na: Synthetic item na.',
            '- [unknown] 0.1.7/odd: Synthetic item odd.',
            '- [unknown] 0.1.7/none: Synthetic item none.', '']))
        self.assertEqual(list(self.folder.iterdir()), [])
        self.transport.assert_not_called()

    def test_whats_new_starts_after_last_seen_and_marks_skipped(self):
        self.save('onboard.json', {'last_seen': '0.1.6', 'skipped': ['0.1.7/open']})
        before = self.onboard_file().read_bytes()
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            out = self.real('whats-new')
        self.assertNotIn('0.1.6', out)
        self.assertIn('- [skipped] 0.1.7/open: Synthetic item open.\n', out)
        self.assertNotIn('(setup:', out)
        self.assertEqual(self.onboard_file().read_bytes(), before)
        self.save('onboard.json', {'last_seen': '0.1.7', 'skipped': []})
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.assertEqual(self.real('whats-new'), 'No new upgrade notes.\n')

    def test_a_dev_build_excludes_its_own_release_notes(self):
        self.save('onboard.json', {'last_seen': '0.1.6', 'skipped': []})
        self.assertEqual(self.real('whats-new'), 'No new upgrade notes.\n')  # installed 0.1.7-dev

    def test_check_runs_plugin_script_without_shell_with_timeout_and_allowlisted_env(self):
        with mock.patch.object(u.subprocess, 'run') as run:
            run.return_value.returncode = 1
            self.assertEqual(u.check_state(['scripts/check_open.py', 'state']), 'open')
        args, kwargs = run.call_args
        self.assertEqual(args[0], [sys.executable, '-I', str(self.plugin / 'scripts/check_open.py'), 'state'])
        self.assertEqual(kwargs['timeout'], 10)
        self.assertNotIn('shell', kwargs)
        self.assertEqual(set(kwargs['env']) - set(u.run_env.BASE_NAMES), set())
        for missing in [['scripts/absent.py'], ['skills/fnl-x/scripts/absent.py']]:
            self.assertEqual(u.check_state(missing), 'unknown')
        with mock.patch.object(u, 'CHECK_TIMEOUT', 0.5), mock.patch.object(subprocess, 'Popen', REAL_POPEN):
            self.assertEqual(u.check_state(['scripts/check_slow.py']), 'unknown')
        with mock.patch.object(u, 'plugin_root', return_value=None):
            self.assertEqual(u.check_state(['scripts/check_done.py']), 'unknown')
        self.assertEqual(kwargs['cwd'], str(self.plugin / 'scripts'))

    def test_an_info_item_is_told_as_info(self):
        self.notes_file.write_text(json.dumps({'versions': [{'version': '0.1.7', 'items': [
            {'id': '0.1.7/news', 'kind': 'info', 'text': 'Synthetic news.'}]}]}))
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.assertEqual(self.call('whats-new'), '0.1.7\n- [info] 0.1.7/news: Synthetic news.\n')

    def test_a_repository_check_runs_in_the_current_folder(self):
        with mock.patch.object(u.subprocess, 'run') as run, mock.patch.object(u.os, 'getcwd', return_value='/work/repo'):
            run.return_value.returncode = 0
            self.assertEqual(u.check_state(['scripts/check_done.py'], 'repository'), 'done')
        self.assertEqual(run.call_args[1]['cwd'], '/work/repo')
        self.notes_file.write_text(json.dumps({'versions': [{'version': '0.1.7', 'items': [
            {'id': '0.1.7/repo', 'kind': 'setup', 'text': 'Synthetic repository item.',
             'check': ['scripts/check_done.py'], 'where': 'repository'}]}]}))
        with mock.patch.object(u, 'check_state', return_value='done') as state, \
                mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.assertIn('[done] 0.1.7/repo', self.call('whats-new'))
        state.assert_called_once_with(['scripts/check_done.py'], 'repository')

    def test_onboard_seen_and_skip_are_the_only_writers_and_bounded(self):
        self.assertEqual(self.call('onboard', 'seen', '0.1.7'), '')
        self.assertEqual(json.loads(self.onboard_file().read_text()), {'last_seen': '0.1.7', 'skipped': []})
        self.assertEqual(stat.S_IMODE(self.onboard_file().stat().st_mode), 0o600)
        self.assertEqual(self.call('onboard', 'skip', '0.1.8/next'), '')
        self.assertEqual(json.loads(self.onboard_file().read_text()), {'last_seen': '0.1.7', 'skipped': ['0.1.8/next']})
        before = self.onboard_file().read_bytes()
        for args in [('onboard', 'seen', '0.1.7-dev'), ('onboard', 'seen', 'x;id'),
                     ('onboard', 'skip', '0.1.8/unknown'), ('onboard', 'skip', 'bad id'),
                     ('onboard', 'skip'), ('onboard', 'other', 'x')]:
            with self.subTest(args=args):
                self.call(*args)
                self.assertEqual(self.onboard_file().read_bytes(), before)
        many = {'0.1.8': [f'n{i}' for i in range(201)]}
        self.notes(many)
        self.save('onboard.json', {'last_seen': None, 'skipped': [f'0.1.8/n{i}' for i in range(200)]})
        before = self.onboard_file().read_bytes()
        self.call('onboard', 'skip', '0.1.8/n200')
        self.assertEqual(self.onboard_file().read_bytes(), before)

    def test_onboard_first_marks_a_fresh_data_root_seen_and_leaves_an_existing_one(self):
        host = self.folder.parent / 'host.md'
        # Fresh: no host config and no onboarding state, so a new user gets no upgrade notes.
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.assertEqual(self.call('onboard', 'first'), '')
            self.assertEqual(json.loads(self.onboard_file().read_text()), {'last_seen': '0.1.7', 'skipped': []})
            self.assertEqual(self.real('whats-new'), 'No new upgrade notes.\n')
            self.assertIsNone(u.onboard_line('0.1.7'))
        # A development build records its own release, so that release's notes are not offered either.
        self.onboard_file().unlink()
        self.assertEqual(self.call('onboard', 'first'), '')  # installed 0.1.7-dev
        self.assertEqual(json.loads(self.onboard_file().read_text())['last_seen'], '0.1.7')
        # Existing: a host config or an onboarding file means an earlier install; nothing changes.
        self.save('onboard.json', {'last_seen': '0.1.5', 'skipped': ['0.1.6/old']})
        before = self.onboard_file().read_bytes()
        self.call('onboard', 'first')
        self.assertEqual(self.onboard_file().read_bytes(), before)
        self.onboard_file().unlink()
        host.write_text('## Routing\non\n')
        self.call('onboard', 'first')
        self.assertFalse(self.onboard_file().exists())
        host.unlink()
        for args in [('onboard', 'first', '0.1.7'), ('onboard', 'first', 'x')]:
            self.call(*args)
            self.assertFalse(self.onboard_file().exists())
        with mock.patch.object(u, 'installed_version', return_value=None):
            self.call('onboard', 'first')
        self.assertFalse(self.onboard_file().exists())

    def test_a_full_skip_ledger_of_long_ids_round_trips(self):
        slug = lambda r, i: f'r{r}-' + 'x' * 34 + f'-{i:02d}'
        releases = {f'0.1.{8 + r}': [slug(r, i) for i in range(30)] for r in range(7)}
        self.notes(releases)
        ids = [f'{v}/{s}' for v, items in releases.items() for s in items]
        for item in ids[:200]:
            self.call('onboard', 'skip', item)
        self.assertGreater(len(self.onboard_file().read_bytes()), 4096)
        self.assertEqual(u.onboard_state()['skipped'], ids[:200])
        before = self.onboard_file().read_bytes()
        self.call('onboard', 'skip', ids[200])
        self.assertEqual(self.onboard_file().read_bytes(), before)

    def test_invalid_onboard_state_is_replaced_by_a_writer_and_silences_the_hook(self):
        for bad in [[], {'last_seen': '0.1.6'}, {'last_seen': 'x', 'skipped': []},
                    {'last_seen': None, 'skipped': ['bad id']}, {'last_seen': None, 'skipped': [], 'x': 1}]:
            with self.subTest(bad=bad):
                self.save('onboard.json', bad)
                with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
                    self.assertEqual(self.call(), '')
                self.call('onboard', 'seen', '0.1.6')
                self.assertEqual(json.loads(self.onboard_file().read_text()), {'last_seen': '0.1.6', 'skipped': []})

    def test_session_start_line_until_seen_independent_of_release_notice(self):
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.cache('v0.1.7')
            self.assertEqual(self.call(), ONBOARD_LINE % '0.1.7')
            self.assertFalse(self.onboard_file().exists())  # the hook never writes
            self.cache('v0.1.8')
            out = self.call()
            self.assertEqual(out.splitlines()[1] + '\n', ONBOARD_LINE % '0.1.7')
            self.assertEqual(len(out.splitlines()), 2)
            self.call('never')
            self.assertEqual(self.call(), ONBOARD_LINE % '0.1.7')
            self.call('onboard', 'seen', '0.1.7')
            self.assertEqual(self.call(), '')
        self.spawn.assert_not_called()

    def test_session_start_line_fails_closed(self):
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.cache('v0.1.7')
            self.notes_file.write_text('{broken')
            self.assertEqual(self.call(), '')
            self.notes({'0.1.7': ['open']})
            with mock.patch.object(u.dr, 'read_data', side_effect=PermissionError):
                self.assertEqual(self.call(), '')
            with mock.patch.object(u, 'onboard_state', side_effect=RuntimeError):
                self.assertEqual(self.call(), '')
            self.save('onboard.json', {'last_seen': None, 'skipped': ['0.1.7/open']})
            self.assertEqual(self.call(), '')  # only skipped notes left

    def test_target_defaults_to_cached_latest(self):
        self.cache('v0.1.8')
        self.assertEqual(self.call('target'), 'target 0.1.8 latest upgrade\n')
        (self.folder / 'update-check.json').unlink()
        self.assertEqual(self.call('target'), 'refused: no cached latest release\n')
        self.transport.assert_not_called()

    def test_target_version_needs_matching_published_stable_evidence(self):
        with mock.patch.object(u, 'installed_version', return_value='0.1.7'):
            self.assertEqual(self.call('target', '0.1.8', '--evidence', self.evidence('v0.1.8')),
                             'target 0.1.8 chosen upgrade\n')
            self.assertEqual(self.call('target', '0.1.7', '--evidence', self.evidence('v0.1.7')),
                             'target 0.1.7 chosen installed\n')
            refusals = [
                ('0.1.8', None),
                ('0.1.8-dev', self.evidence('v0.1.8-dev')),
                ('0.1.8', self.evidence('v0.1.9')),
                ('0.1.8', self.evidence('v0.1.8', isDraft=True)),
                ('0.1.8', self.evidence('v0.1.8', isPrerelease=True)),
                ('0.1.8', self.evidence('v0.1.8', isPrerelease=0)),
                ('0.1.8', self.evidence('v0.1.8', url='https://github.com/other/finolabs-vibecode/releases/tag/v0.1.8')),
                ('0.1.8', self.evidence('v0.1.8', url=EVIDENCE_URL + 'v0.1.8/')),
                ('0.1.8', self.evidence('v0.1.8', extra=1)),
                ('0.1.8', str(Path(self.tmp.name) / 'absent.json')),
            ]
            for case, (version, evidence) in enumerate(refusals):
                with self.subTest(case=case):
                    args = ('target', version) + (('--evidence', evidence) if evidence else ())
                    self.assertTrue(self.call(*args).startswith('refused: '))
            big = Path(self.tmp.name) / 'big.json'
            big.write_text(' ' * 65537)
            self.assertTrue(self.call('target', '0.1.8', '--evidence', str(big)).startswith('refused: '))
        self.assertEqual(list(self.folder.iterdir()), [])
        self.transport.assert_not_called()

    def test_older_target_is_a_rollback_listing_lost_items(self):
        with mock.patch.object(u, 'installed_version', return_value='0.1.8'):
            out = self.call('target', '0.1.6', '--evidence', self.evidence('v0.1.6'))
        lines = out.splitlines()
        self.assertEqual(lines[0], 'target 0.1.6 chosen rollback')
        self.assertEqual(lines[1:], ['lost: 0.1.7/done: Synthetic item done.',
                                     'lost: 0.1.7/open: Synthetic item open.',
                                     'lost: 0.1.7/na: Synthetic item na.',
                                     'lost: 0.1.7/odd: Synthetic item odd.',
                                     'lost: 0.1.7/none: Synthetic item none.',
                                     'lost: 0.1.8/next: Synthetic item next.'])

    def test_pin_silences_release_notice_until_unpinned_and_status_shows_it(self):
        self.cache('v0.1.8')
        self.notes({'0.1.0': ['old']})
        self.save('onboard.json', {'last_seen': '0.1.0', 'skipped': []})
        self.assertTrue(self.call())
        self.assertEqual(self.call('pin', '0.1.7'), '')
        self.assertEqual(self.call(), '')
        self.assertEqual(json.loads(self.call('status'))['pinned'], '0.1.7')
        self.assertEqual(json.loads((self.folder / 'update-state.json').read_text()),
                         {'skipped': [], 'never_ask': False, 'pinned': '0.1.7'})
        self.call('skip', '0.1.9')
        self.assertEqual(json.loads(self.call('status'))['pinned'], '0.1.7')
        for bad in ['0.1.7-dev', 'x;id']:
            self.call('pin', bad)
            self.assertEqual(json.loads(self.call('status'))['pinned'], '0.1.7')
        self.assertEqual(self.call('unpin'), '')
        self.assertNotIn('pinned', json.loads(self.call('status')))
        self.assertTrue(self.call())
        self.spawn.assert_not_called()

    def test_new_commands_stop_when_off(self):
        with mock.patch.dict(os.environ, {'FNL_UPDATE_CHECK': 'off'}):
            for args in [('whats-new',), ('onboard', 'seen', '0.1.7'), ('target',), ('pin', '0.1.7'), ('unpin',)]:
                self.assertEqual(self.call(*args), '')
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_shipped_notes_resolve_from_both_copies(self):
        for script in ['scripts/update_check.py', 'skills/update/scripts/update_check.py']:
            with self.subTest(script=script):
                module_spec = importlib.util.spec_from_file_location('copy_' + script.replace('/', '_'), ROOT / script)
                module = importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(module)
                self.assertEqual(module.notes_path(), ROOT / 'skills/update/references/upgrades.json')
                self.assertEqual(module.plugin_root(), ROOT)


if __name__ == '__main__':
    unittest.main()
