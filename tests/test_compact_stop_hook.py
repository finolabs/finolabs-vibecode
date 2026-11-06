"""Compaction stop acceptance using only a synthetic account."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/compact_stop_hook.py'
MESSAGE = 'The conversation is large. Run /compact, or start a fresh session with a short handover, then continue.'
STOP = {'injectSteps': [{'errorMessage': {'userMessage': MESSAGE}}], 'terminationBehavior': 'terminate'}


class CompactStopHookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = account(self, Path(self.temp.name) / 'home')
        self.root = self.home / '.finolabs/vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        self.host = self.root / 'host.md'
        self.host.write_text('## Compaction stop\n\nEnabled: yes\nLimit bytes: 50000\n')
        self.transcript = self.home / '.gemini/antigravity-cli/brain/example/.system_generated/logs/transcript.json'
        self.transcript.parent.mkdir(parents=True)
        self.resize(60000)
        self.event = {'conversationId': 'example', 'transcriptPath': str(self.transcript), 'invocationNum': 0}
        self.mark = self.root / ('state/compact-stop/' + hashlib.sha256(b'example').hexdigest()[:16] + '.json')
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def resize(self, size):
        with self.transcript.open('wb') as stream:
            stream.truncate(size)

    def run_hook(self, event=None, raw=None, args=None):
        self.assertTrue(SCRIPT.is_file(), 'the opted-in PreInvocation hook is not implemented')
        spec = importlib.util.spec_from_file_location('compact_stop_hook', SCRIPT)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        self.hook = hook
        stdin = io.TextIOWrapper(io.BytesIO(raw if raw is not None else json.dumps(self.event if event is None else event).encode()))
        out = io.StringIO()
        with mock.patch.object(sys, 'stdin', stdin), mock.patch.object(sys, 'argv', [str(SCRIPT), *(args if args is not None else ['--host', 'antigravity', '--event', 'PreInvocation'])]), contextlib.redirect_stdout(out):
            self.assertEqual(hook.main(), 0)
        result = out.getvalue()
        self.assertIn(result, ('{}\n', json.dumps(STOP, separators=(',', ':')) + '\n'))
        return json.loads(result)

    def test_acceptance_1_stop_shape_and_private_integer_mark(self):
        self.assertEqual(self.run_hook(), STOP)
        self.assertEqual(json.loads(self.mark.read_bytes()), 60000)
        self.assertEqual(stat.S_IMODE(self.mark.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.mark.parent.stat().st_mode), 0o700)

    def test_disabled_missing_invalid_and_unsafe_host_allow(self):
        original = self.host.read_bytes()
        for text in ('', '## Compaction stop\nEnabled: no\nLimit bytes: 50000\n',
                     '## Other\nEnabled: yes\nLimit bytes: 50000\n',
                     '## Compaction stop\nEnabled: yes\nLimit bytes: 49999\n',
                     '## Compaction stop\nEnabled: yes\nLimit bytes: 20000001\n',
                     '## Compaction stop\nEnabled: yes\nLimit bytes: true\n',
                     original.decode() * 2, '```\n' + original.decode() + '```\n'):
            with self.subTest(text=text):
                self.host.write_text(text)
                self.assertEqual(self.run_hook(), {})
        self.host.unlink()
        self.assertEqual(self.run_hook(), {})
        self.host.write_bytes(original)
        self.host.chmod(0o666)
        self.assertEqual(self.run_hook(), {})
        self.host.chmod(0o600)
        with mock.patch.dict(os.environ, {'FNL_COMPACT_STOP': 'off'}):
            self.assertEqual(self.run_hook(), {})
        self.assertFalse(self.mark.exists())

    def test_invalid_data_pointer_allows_without_fallback(self):
        (self.root / 'root.json').write_text('{}')
        self.assertEqual(self.run_hook(), {})
        self.assertFalse(self.mark.exists())

    def test_limit_boundary_and_second_turn_same_size_allow(self):
        self.resize(50000)
        self.assertEqual(self.run_hook(), {})
        self.resize(50001)
        self.assertEqual(self.run_hook(), STOP)
        self.assertEqual(self.run_hook(), {})
        self.resize(70000)
        self.assertEqual(self.run_hook(), {})
        self.resize(70001)
        self.assertEqual(self.run_hook(), STOP)

    def test_both_growth_bounds_and_shrink_reset(self):
        self.resize(300000)
        self.assertEqual(self.run_hook(), STOP)
        for size in (300000, 320000, 329999):
            self.resize(size)
            self.assertEqual(self.run_hook(), {})
        self.resize(330000)
        self.assertEqual(self.run_hook(), STOP)
        self.resize(60000)
        self.assertEqual(self.run_hook(), {})
        self.assertFalse(self.mark.exists())
        self.assertEqual(self.run_hook(), STOP)
        self.resize(100)
        self.assertEqual(self.run_hook(), {})
        self.assertFalse(self.mark.exists())

    def test_unwritable_state_and_failed_atomic_write_allow(self):
        self.mark.parent.mkdir(parents=True, mode=0o700)
        self.mark.parent.chmod(0o500)
        try:
            self.assertEqual(self.run_hook(), {})
        finally:
            self.mark.parent.chmod(0o700)
        # Portable failure seam also covers privileged test runners.
        self.run_hook(event={})
        with mock.patch.object(self.hook.dr, 'atomic_write', side_effect=OSError('private failure')):
            self.assertEqual(self.run_hook(), {})
        self.assertFalse(self.mark.exists())

    def test_symlink_outside_missing_and_nonregular_transcripts_allow(self):
        outside = self.home / 'outside'
        outside.write_bytes(b'x' * 60000)
        link = self.transcript.parent / 'link'
        link.symlink_to(self.transcript)
        for path in (outside, link, self.transcript.parent, self.transcript.parent / 'missing'):
            with self.subTest(path=path.name):
                self.assertEqual(self.run_hook(event={**self.event, 'transcriptPath': str(path)}), {})
        linked_folder = self.transcript.parent / 'escape'
        linked_folder.symlink_to(self.home, target_is_directory=True)
        self.assertEqual(self.run_hook(event={**self.event, 'transcriptPath': str(linked_folder / 'outside')}), {})

    def test_transcript_is_never_opened(self):
        original = os.open
        def checked(path, *args, **kwargs):
            self.assertNotEqual(str(path), str(self.transcript))
            return original(path, *args, **kwargs)
        with mock.patch.object(os, 'open', side_effect=checked), mock.patch.object(Path, 'open', side_effect=AssertionError('transcript opened')):
            self.assertEqual(self.run_hook(), STOP)

    def test_only_first_preinvocation_on_antigravity(self):
        for invocation in (1, 2, -1, False, '0', None):
            self.assertEqual(self.run_hook(event={**self.event, 'invocationNum': invocation}), {})
        for args in ([], ['--host', 'claude', '--event', 'PreInvocation'], ['--host', 'antigravity', '--event', 'PostInvocation'], ['--host', 'antigravity', '--event', 'SessionStart']):
            self.assertEqual(self.run_hook(args=args), {})
        for event in ([], {}, {**self.event, 'conversationId': ''}, {**self.event, 'transcriptPath': None}):
            self.assertEqual(self.run_hook(event=event), {})

    def test_malformed_oversize_and_idle_stdin_allow(self):
        for raw in (b'', b'not-json', b'[]', b'\xff', b' ' * 65537, b'[' * 1500):
            self.assertEqual(self.run_hook(raw=raw), {})
        reader, writer = os.pipe()
        self.addCleanup(os.close, writer)
        with os.fdopen(reader, 'r') as stream:
            self.run_hook(event={})
            out = io.StringIO()
            with mock.patch.object(sys, 'stdin', stream), mock.patch.object(sys, 'argv', [str(SCRIPT), '--host', 'antigravity', '--event', 'PreInvocation']), mock.patch.object(self.hook.select, 'select', return_value=([], [], [])) as select_call, contextlib.redirect_stdout(out):
                self.assertEqual(self.hook.main(), 0)
            self.assertEqual(out.getvalue(), '{}\n')
            self.assertLessEqual(select_call.call_args.args[3], 0.5)

    def test_unsafe_and_invalid_marks_allow(self):
        self.mark.parent.mkdir(parents=True, mode=0o700)
        for value in ('{}', 'true', '-1', '"private-content"'):
            self.mark.write_text(value)
            self.mark.chmod(0o600)
            self.assertEqual(self.run_hook(), {})
        self.mark.chmod(0o644)
        self.assertEqual(self.run_hook(), {})
        self.mark.unlink()
        self.mark.symlink_to(self.host)
        self.assertEqual(self.run_hook(), {})

    def test_cap_evicts_oldest_and_stores_no_content(self):
        self.mark.parent.mkdir(parents=True, mode=0o700)
        for i in range(200):
            mark = self.mark.parent / f'{i:016x}.json'
            mark.write_text('50001')
            mark.chmod(0o600)
            os.utime(mark, (i + 1, i + 1))
        self.assertEqual(self.run_hook(), STOP)
        self.assertEqual(len(list(self.mark.parent.glob('*.json'))), 200)
        self.assertFalse((self.mark.parent / ('0' * 16 + '.json')).exists())
        self.assertEqual(self.mark.read_text(), '60000')
