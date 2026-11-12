"""Content-free process snapshots; all process-table assertions use injected rows."""
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('agent_processes_test', ROOT / 'scripts/agent_processes.py')
ap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ap)


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        account(self, Path(self.tmp.name) / 'home')

    def test_exact_roots_uid_names_elapsed_apps_and_hostile_names(self):
        raw = ('42 1 0 1-02:03:04 /private/claude\n'
               '42 2 1 00:01 /secret/node\n42 3 1 00:02 /secret/evil name</script>\n'
               '42 4 1 00:01 evil\x01name\n43 5 1 00:01 codex\n'
               '42 6 0 00:03 codexd\n42 7 0 00:03 claude-helper\n'
               '42 8 0 00:03 node\n42 9 0 02:03 agy\n42 10 0 03:04 codex\n'
               '42 11 0 00:01 /apps/Claude\n42 12 0 00:01 Codex\n42 13 0 00:01 Antigravity\n'
               'bad\n42 x 1 00:01 claude\n42 15 1 garbage claude\n42 16 1 99:99 claude\n')
        result = ap.parse(raw, 42, 'now')
        self.assertEqual([r['family'] for r in result['processes']], ['claude', 'agy', 'codex'])
        self.assertEqual(result['processes'][0], dict(family='claude', elapsed_seconds=93784,
                                                    descendants={'node': 1, 'other': 2}))
        self.assertEqual(result['apps'], {'Claude': 1, 'Codex': 1, 'Antigravity': 1})
        self.assertEqual(result['time'], 'now')
        text = json.dumps(result)
        for bad in ('private', 'secret', 'evil', '</script>', 'codexd', 'claude-helper', '\\u0001'):
            self.assertNotIn(bad, text)

    def test_depth_row_bounds_cycles_and_other_users(self):
        rows = ['42 1 0 00:01 claude']
        rows += [f'42 {i} {i-1} 00:01 node' for i in range(2, 10)]
        rows += ['43 20 1 00:01 node', '42 21 20 00:01 node']
        self.assertEqual(ap.parse('\n'.join(rows), 42, 'now')['processes'][0]['descendants'], {'node': 6})
        rows = ['42 1 2 00:01 claude', '42 2 1 00:01 node']
        self.assertEqual(ap.parse('\n'.join(rows), 42, 'now')['processes'][0]['descendants'], {'node': 1})
        rows = ['42 1 0 00:01 claude'] + [f'42 {i} 1 00:01 node' for i in range(2, 602)]
        self.assertEqual(ap.parse('\n'.join(rows), 42, 'now')['processes'][0]['descendants'], {'node': 500})

    def test_ps_path_checks_disable_without_spawning(self):
        for mode, uid in ((stat.S_IFLNK | 0o755, 0), (stat.S_IFREG | 0o775, 0),
                          (stat.S_IFREG | 0o757, 0), (stat.S_IFREG | 0o755, 42)):
            with self.subTest(mode=mode, uid=uid), mock.patch.object(ap.os, 'lstat', return_value=SimpleNamespace(st_mode=mode, st_uid=uid)), \
                    mock.patch.object(ap.subprocess, 'Popen') as spawn:
                result = ap.snapshot()
                self.assertEqual(result['reason'], 'ps unavailable')
                self.assertEqual(result['processes'], [])
                spawn.assert_not_called()

    def test_fixed_argv_environment_cwd_and_failure_reasons(self):
        with mock.patch.object(ap, 'resolve_ps', return_value='/usr/bin/ps'), \
                mock.patch.object(ap, 'execute', return_value=b'') as execute:
            self.assertEqual(ap.snapshot()['reason'], '')
            execute.assert_called_once_with('/usr/bin/ps')
        for error, reason in ((TimeoutError(), 'ps timed out'), (ValueError(), 'ps output too large'),
                              (OSError('/secret hostile'), 'ps failed')):
            with mock.patch.object(ap, 'resolve_ps', return_value='/usr/bin/ps'), \
                    mock.patch.object(ap, 'execute', side_effect=error):
                result = ap.snapshot()
                self.assertEqual(result['reason'], reason)
                self.assertEqual(result['processes'], [])
                self.assertNotIn('secret', json.dumps(result))

    def test_execution_contract_and_bounded_output(self):
        # A local Python stand-in exercises pipes, cap, timeout, nonzero exit and
        # process-group cleanup without reading the machine's process table.
        real_popen = subprocess.Popen
        for program, error in (("print('42 1 0 00:01 claude')", None),
                               ('import sys; sys.exit(3)', OSError),
                               ("print('x' * 300000)", ValueError),
                               ('import time; time.sleep(10)', TimeoutError)):
            calls = []
            def spawn(argv, **kwargs):
                calls.append((argv, kwargs))
                return real_popen([sys.executable, '-I', '-c', program], **kwargs)
            with mock.patch.object(ap.subprocess, 'Popen', side_effect=spawn), \
                    mock.patch.object(ap.os, 'killpg', wraps=os.killpg) as kill:
                if error:
                    with self.assertRaises(error):
                        ap.execute('/usr/bin/ps')
                else:
                    self.assertIn(b'claude', ap.execute('/usr/bin/ps'))
                kill.assert_called()
            argv, kwargs = calls[0]
            self.assertEqual(argv, ['/usr/bin/ps', '-axo', 'uid=,pid=,ppid=,etime=,comm='])
            self.assertEqual(kwargs['env'], {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            self.assertTrue(kwargs['start_new_session'])
            self.assertFalse(kwargs.get('shell', False))
            self.assertFalse(Path(kwargs['cwd']).exists())  # neutral temporary folder removed


class SnapshotConsentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = account(self, Path(self.tmp.name) / 'home')
        self.root = self.home / '.finolabs/vibecode'
        self.root.mkdir(parents=True)
        self.host = self.root / 'host.md'
        self.env = mock.patch.dict(os.environ, {'FNL_AGENT_SNAPSHOT': '', 'FNL_METRICS': ''})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_setup_on_off_requires_yes_preserves_host_and_cli_collects_only_with_both_consents(self):
        self.host.write_text('# Host\n\n## Other\n\nKeep this.\n')
        before = self.host.read_bytes()
        self.assertFalse(ap.enabled())
        self.assertEqual(ap.main(['on']), 1)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(ap.main(['on', '--dry-run']), 0)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(ap.main(['on', '--yes']), 0)
        self.assertTrue(ap.enabled())
        self.assertTrue(self.host.read_bytes().startswith(before))
        self.assertEqual(self.host.stat().st_mode & 0o777, 0o600)
        with mock.patch.object(ap, 'snapshot', return_value=ap.empty()) as probe:
            ap.main([])
            probe.assert_not_called()
            (self.root / 'state').mkdir(mode=0o700)
            (self.root / 'state/consent.json').write_text('{"date":"2026-11-06","retention_days":90}')
            ap.main([])
            probe.assert_called_once()
            with mock.patch.dict(os.environ, {'FNL_AGENT_SNAPSHOT': 'off'}):
                self.assertFalse(ap.enabled())
                ap.main([])
            probe.assert_called_once()
        self.assertEqual(ap.main(['off', '--yes']), 0)
        self.assertFalse(ap.enabled())
        self.assertEqual(self.host.read_text().count('## Agent snapshot'), 1)
        self.assertIn('- Snapshot: off', self.host.read_text())

    def test_unsafe_ambiguous_redirected_or_unresolved_consent_is_off(self):
        for body in ('```md\n## Agent snapshot\n- Snapshot: on\n```\n',
                     '## Agent snapshot\n- Snapshot: on\n## Agent snapshot\n- Snapshot: on\n',
                     '## Agent snapshot\n- Snapshot: on\n- Snapshot: off\n',
                     '## Agent snapshot\n- Snapshot: on\nextra\n'):
            self.host.write_text(body)
            self.assertFalse(ap.enabled())
        self.host.write_text('## Agent snapshot\n- Snapshot: on\n')
        self.host.chmod(0o666)
        self.assertFalse(ap.enabled())
        self.host.chmod(0o600)
        outside = self.home / 'outside.md'
        self.host.rename(outside)
        self.host.symlink_to(outside)
        self.assertFalse(ap.enabled())
        self.host.unlink()
        with mock.patch.dict(os.environ, {'ORCHESTRATION_HOST_CONFIG': str(outside), 'HOME': str(self.home / 'fake')}):
            self.assertFalse(ap.enabled())
        self.host.write_text('## Agent snapshot\n- Snapshot: on\n')
        (self.root / 'root.json').write_text('{}')
        self.assertFalse(ap.enabled())
        self.assertEqual(ap.main(['on', '--yes']), 1)

    def test_copies_and_phase_one_docs_match_the_policy_without_hook_changes(self):
        original = (ROOT / 'scripts/agent_processes.py').read_bytes()
        for skill in ('status', 'setup'):
            self.assertEqual(original, (ROOT / f'skills/{skill}/scripts/agent_processes.py').read_bytes())
        for file, phrases in {
            'PRIVACY.md': ('## Agent snapshot', 'FNL_AGENT_SNAPSHOT=off', 'comm', 'data.js', 'user-chosen names'),
            'README.md': ('Running now', 'FNL_AGENT_SNAPSHOT=off'),
            'CHANGELOG.md': ('## [Unreleased]', 'process snapshot'),
            'docs/specs/index.md': ('implemented; phase 1',),
            'skills/status/SKILL.md': ('same `running` block', 'advisory'),
            'skills/setup/references/features/metrics.md': ('agent_processes.py on --yes', 'unresolved means off'),
            'CLAUDE.md': ('absolute path owned by root', '2-second limit', '256 KiB output cap'),
        }.items():
            for phrase in phrases:
                self.assertIn(phrase, (ROOT / file).read_text(), file)


if __name__ == '__main__':
    unittest.main()
