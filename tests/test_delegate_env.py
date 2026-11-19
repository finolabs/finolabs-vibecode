"""The dispatch wrapper's `ended` line: synthetic data roots and environments only."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import delegate_env
import away_lease
import log_scan

DISPATCH = 'd20261112-101500-abcd'
MARKER = 'synthetic-child-marker'


class EndedLineTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        base = Path(folder.name).resolve()
        self.home = account(self, base / 'home')
        self.ledger = self.home / '.finolabs/vibecode/ledger.jsonl'
        self.ledger.parent.mkdir(parents=True, mode=0o700)
        self.home.joinpath('.finolabs').chmod(0o700)
        self.ledger.write_text(json.dumps({'event': 'start', 'id': DISPATCH}) + '\n')
        self.ledger.chmod(0o600)
        self.logs = base / 'logs'
        self.source = {'PATH': os.defpath, 'HOME': str(self.home), 'LANG': 'C', 'TMPDIR': str(base)}

    def run_wrapper(self, child, dispatch=DISPATCH):
        source = dict(self.source)
        if dispatch is not None:
            source['FNL_DISPATCH_ID'] = dispatch
        argv = ['delegate_env.py', '--family', 'codex', '--', sys.executable, '-I', '-c', child, MARKER]
        with mock.patch.dict(os.environ, source, clear=True), mock.patch.object(sys, 'argv', argv), \
                mock.patch.object(log_scan, 'run_log_folder', return_value=self.logs):
            return delegate_env.main()

    def lines(self):
        return [json.loads(line) for line in self.ledger.read_text().splitlines()]

    def test_the_ended_line_holds_the_childs_exit_code_and_nothing_else(self):
        self.assertEqual(self.run_wrapper('import sys; sys.exit(3)'), 3)
        ended = self.lines()[-1]
        self.assertEqual(set(ended), {'event', 'id', 'ts', 'exit'})
        self.assertEqual((ended['event'], ended['id'], ended['exit']), ('ended', DISPATCH, 3))
        text = self.ledger.read_text()
        for leaked in (MARKER, 'sys.exit', sys.executable, str(self.home)):
            self.assertNotIn(leaked, text)  # no command text, output or path
        self.assertEqual(self.run_wrapper('pass'), 0)
        self.assertEqual(self.lines()[-1]['exit'], 0)

    def test_a_signal_terminated_child_records_its_negative_code(self):
        code = self.run_wrapper('import os, signal; os.kill(os.getpid(), signal.SIGTERM)')
        self.assertEqual(code, 1)  # the wrapper's own status is unchanged by this feature
        self.assertEqual(self.lines()[-1]['exit'], -15)

    def test_nothing_is_written_for_a_missing_or_malformed_id(self):
        before = self.ledger.read_bytes()
        for dispatch in (None, '', 'synthetic', 'd20261112-101500-ABCD', DISPATCH + 'x', 'bad id; rm',
                         DISPATCH + '\n'):
            with self.subTest(dispatch=dispatch):
                self.assertEqual(self.run_wrapper('import sys; sys.exit(2)', dispatch), 2)
                self.assertEqual(self.ledger.read_bytes(), before)

    def test_nothing_is_written_without_a_ledger(self):
        self.ledger.unlink()
        self.assertEqual(self.run_wrapper('import sys; sys.exit(4)'), 4)
        self.assertFalse(self.ledger.exists())

    def test_a_failed_ledger_write_never_changes_the_exit_status(self):
        before = self.ledger.read_bytes()
        for error in (OSError('synthetic'), ValueError('unsafe ledger'), RuntimeError('synthetic')):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(away_lease, 'append_ledger', side_effect=error):
                self.assertEqual(self.run_wrapper('import sys; sys.exit(5)'), 5)
        self.ledger.chmod(0o644 | 0o020)  # group-writable: the safe append refuses it
        self.assertEqual(self.run_wrapper('import sys; sys.exit(6)'), 6)
        self.ledger.chmod(0o600)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_ledger_reads_the_ended_line_as_open_not_finished(self):
        self.run_wrapper('import sys; sys.exit(7)')
        import importlib.util
        spec = importlib.util.spec_from_file_location('wrapper_ledger', ROOT / 'skills/delegate/scripts/ledger.py')
        ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ledger)
        ended = {}
        _, finishes = ledger.load(ended)
        self.assertEqual(finishes, {})
        self.assertEqual(ended[DISPATCH]['exit'], 7)



@unittest.skipUnless(Path('/bin/zsh').exists(), 'zsh is required')
class FunctionDispatchEnvironmentTest(unittest.TestCase):
    """A shell-function command behind delegate_env.py gets only approved names (names only, no values)."""

    def run_function(self, host_text):
        import subprocess
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import delegate_env
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp).resolve()
            (home / '.zshrc').write_text('claudetest() { if (( ${+LEVELS_SYNTH_NAME} )); then print -r -- "state:set"; else print -r -- "state:unset"; fi; }\n')
            with mock.patch.dict(os.environ, {'HOME': str(home), 'LEVELS_SYNTH_NAME': 'x', 'PATH': '/usr/bin:/bin'}, clear=True):
                env = delegate_env.environment('claude', host_text=host_text)
            self.assertNotIn('ZDOTDIR', env)
            result = subprocess.run(['/bin/zsh', '-ic', 'claudetest'], env=env, capture_output=True, text=True, timeout=30)
        return [line for line in result.stdout.splitlines() if line.startswith('state:')]

    def test_a_name_that_is_not_approved_does_not_reach_the_function(self):
        self.assertEqual(self.run_function('## Delegate environment\n- claude: none\n'), ['state:unset'])

    def test_documented_launch_form_uses_the_filter_and_the_users_zsh(self):
        text = (ROOT / 'skills/delegate/references/agents/claude-code.md').read_text()
        line = next(l for l in text.splitlines() if 'Declared Claude Code commands' in l)
        self.assertIn('delegate_env.py --family claude -- /bin/zsh -ic', line)
        self.assertNotIn('never behind `delegate_env.py`', line)

    def test_an_approved_name_reaches_the_function(self):
        self.assertEqual(self.run_function('## Delegate environment\n- claude: LEVELS_SYNTH_NAME\n'), ['state:set'])


if __name__ == '__main__':
    unittest.main()


class AfkHooksOffInChildrenTest(unittest.TestCase):
    """A headless Claude child never answers the afk stop or permission hook (owner decision, 19/11/2026)."""

    def test_claude_children_switch_both_afk_hooks_off_and_others_get_nothing_new(self):
        import sys
        sys.path.insert(0, str(ROOT / 'scripts'))
        import delegate_env
        with mock.patch.dict(os.environ, {'PATH': '/usr/bin:/bin', 'FNL_AFK_STOP': 'on'}, clear=True):
            claude = delegate_env.environment('claude', host_text='')
            codex = delegate_env.environment('codex', host_text='')
        self.assertEqual((claude['FNL_AFK_STOP'], claude['FNL_AFK_PERMIT'], claude['FNL_PROOF_NUDGE']), ('off', 'off', 'off'))
        self.assertNotIn('FNL_AFK_PERMIT', codex)
