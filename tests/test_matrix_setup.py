"""Assignment matrix writer: preview, digest, backup, section-only write, show and migrate with synthetic accounts."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest import mock

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/setup/scripts/matrix_setup.py'
PREFIX = b'# Host\r\n\r\n## Other\r\nkeep \xc3\xa9  \r\n'
TODAY = '2026-11-09'
LINES = ('--line', 'claude: levels 1-5; works on frontend, design; model claude-opus-5-5',
         '--line', 'codex: levels 1-4; works on image-generation; roles security-review',
         '--line', 'antigravity: levels 1-3; roles code-review, navigator')
LEGACY = (b'## Agent roles\r\n\r\n- code review: antigravity\r\n- security review: codex\r\n- navigator: claude\r\n- judge: jev\r\n\r\n'
          b'## Agent levels\r\n\r\n- Consent: yes (2026-10-01)\r\n- claudework: levels 3-5\r\n- codex: levels 1-4\r\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MatrixSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.home = account(self, base / 'home')
        ancestors = {p.stat().st_ino for p in base.parents if p.stat().st_mode & 0o022}
        original = os.fstat

        def fstat(fd):
            info = original(fd)
            if info.st_ino in ancestors and stat.S_ISDIR(info.st_mode):
                fields = list(info)
                fields[0] &= ~0o022
                return os.stat_result(fields)
            return info
        patch = mock.patch.object(os, 'fstat', side_effect=fstat)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.dict(os.environ, {'HOME': str(self.home)}, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.host = self.home / '.finolabs/vibecode/host.md'
        self.host.parent.mkdir(parents=True, exist_ok=True)
        self.host.write_bytes(PREFIX)
        self.plan = self.host.parent / 'state/matrix-setup/preview.json'

    def cli(self, *args):
        self.assertTrue(SCRIPT.is_file(), 'matrix writer is missing')
        writer = load('matrix_setup_test', SCRIPT)
        writer.today = lambda: TODAY
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = writer.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def preview(self, *args):
        code, out, err = self.cli('preview', '--judge', 'jev', '--consent', 'yes', *(args or LINES))
        self.assertEqual(code, 0, err)
        return out.split('Digest: ')[1].splitlines()[0]

    def backups(self):
        return sorted(self.host.parent.glob('host.md.bak-*'))

    # validate and preview

    def test_validate_prints_the_section_and_writes_nothing(self):
        code, out, err = self.cli('validate', '--judge', 'jev', '--consent', 'yes', *LINES)
        self.assertEqual((code, err), (0, ''))
        self.assertIn('## Assignment matrix', out)
        self.assertIn(f'- Consent: yes ({TODAY})', out)
        self.assertIn('- claude: levels 1-5; works on frontend, design; model claude-opus-5-5', out)
        self.assertEqual(self.host.read_bytes(), PREFIX)
        self.assertFalse(self.plan.exists())

    def test_invalid_input_is_refused_and_writes_nothing(self):
        bad = ('gemini: levels 1-2', 'claude: levels 5-3', 'claude: levels 1-2; works on backend', 'claude: levels 1-2; model a b',
               'claude: levels 1-2; roles judge', 'claude', 'claude: levels 1-2\n- Judge: host', 'Consent: no', '- claude: levels 1-2')
        for line in bad:
            with self.subTest(line=line):
                self.assertEqual(self.cli('preview', '--judge', 'host', '--consent', 'yes', '--line', line)[0], 1)
                self.assertEqual(self.cli('validate', '--judge', 'host', '--consent', 'yes', '--line', line)[0], 1)
        self.assertEqual(self.cli('preview', '--judge', 'host', '--consent', 'yes', '--line', 'claude: levels 1-2', '--line', 'claude: levels 3-4')[0], 1)
        self.assertEqual(self.cli('preview', '--judge', 'host', '--consent', 'yes', '--line', 'claude: levels 1-2; roles navigator',
                                  '--line', 'codex: levels 1-2; roles navigator')[0], 1)
        self.assertEqual(self.cli('preview', '--judge', 'other', '--consent', 'yes', *LINES)[0], 1)
        self.assertEqual(self.cli('preview', '--judge', 'host', *LINES)[0], 1)
        self.assertEqual(self.cli('preview', '--judge', 'host', '--consent', 'maybe', *LINES)[0], 1)
        many = [x for i in range(9) for x in ('--line', f'claudex{i}: levels 1-2')]
        self.assertEqual(self.cli('preview', '--judge', 'host', '--consent', 'yes', *many)[0], 1)
        self.assertEqual(self.host.read_bytes(), PREFIX)
        self.assertFalse(self.plan.exists())

    def test_refusal_never_echoes_the_input(self):
        code, out, err = self.cli('preview', '--judge', 'host', '--consent', 'yes', '--line', 'claude: levels 1-2; model zzSECRETzz/x')
        self.assertEqual(code, 1)
        self.assertNotIn('zzSECRETzz', out + err)

    def test_preview_writes_only_a_private_plan(self):
        digest = self.preview()
        self.assertEqual(self.host.read_bytes(), PREFIX)
        self.assertEqual(stat.S_IMODE(self.plan.stat().st_mode), 0o600)
        self.assertRegex(digest, r'^[0-9a-f]{64}$')

    # apply

    def test_apply_writes_only_the_section_keeps_other_bytes_and_backs_up(self):
        digest = self.preview()
        code, _, err = self.cli('apply', '--digest', digest[:12])
        self.assertEqual(code, 0, err)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(PREFIX))
        section = raw[len(PREFIX):].decode().lstrip('\r\n')
        self.assertTrue(section.startswith('## Assignment matrix\r\n'))
        self.assertIn('- codex: levels 1-4; works on image-generation; roles security-review\r\n', section)
        self.assertNotIn('\n', section.replace('\r\n', ''))
        self.assertEqual([b.read_bytes() for b in self.backups()], [PREFIX])
        self.assertFalse(self.plan.exists())
        code, out, _ = self.cli('show')
        self.assertEqual(code, 0)
        self.assertIn('| claude | 1-5 | frontend, design | claude-opus-5-5 | none |', out)

    def test_apply_replaces_an_existing_section_and_nothing_else(self):
        old = PREFIX + b'## Assignment matrix\n- Consent: no\n- Judge: bogus\n## Tail\nafter\n'
        self.host.write_bytes(old)
        self.assertEqual(self.cli('apply', '--digest', self.preview())[0], 0)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(PREFIX))
        self.assertTrue(raw.endswith(b'## Tail\nafter\n'))
        self.assertEqual(raw.count(b'## Assignment matrix'), 1)
        self.assertNotIn(b'bogus', raw)
        self.assertEqual(self.backups()[0].read_bytes(), old)

    def test_legacy_sections_are_untouched_by_a_plain_apply(self):
        self.host.write_bytes(PREFIX + LEGACY)
        self.assertEqual(self.cli('apply', '--digest', self.preview())[0], 0)
        raw = self.host.read_bytes()
        self.assertTrue(raw.startswith(PREFIX + LEGACY))

    def test_apply_creates_a_missing_host_without_backup(self):
        self.host.unlink()
        self.assertEqual(self.cli('apply', '--digest', self.preview())[0], 0)
        self.assertTrue(self.host.read_text().startswith('## Assignment matrix\n'))
        self.assertEqual(self.backups(), [])

    def test_wrong_digest_missing_digest_and_changed_host_write_nothing(self):
        digest = self.preview()
        self.assertEqual(self.cli('apply', '--digest', '0' * 64)[0], 1)
        self.assertEqual(self.cli('apply', '--digest', 'abc')[0], 1)
        self.host.write_bytes(PREFIX + b'changed\r\n')
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)
        self.assertNotIn(b'Assignment matrix', self.host.read_bytes())
        self.assertEqual(self.backups(), [])

    def test_expired_preview_is_refused(self):
        digest = self.preview()
        with mock.patch.object(time, 'time', return_value=time.time() + 3601):
            self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)
        self.assertEqual(self.host.read_bytes(), PREFIX)
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 0)

    def test_preview_is_single_use(self):
        digest = self.preview()
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 0)
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)

    def test_tampered_plan_is_refused(self):
        digest = self.preview()
        data = json.loads(self.plan.read_text())
        data['plan']['values']['judge'] = 'host'
        self.plan.write_text(json.dumps(data))
        os.chmod(self.plan, 0o600)
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)
        self.assertEqual(self.host.read_bytes(), PREFIX)

    def test_symlinked_host_is_refused(self):
        target = self.host.parent / 'elsewhere.md'
        target.write_bytes(PREFIX)
        self.host.unlink()
        self.host.symlink_to(target)
        self.assertEqual(self.cli('preview', '--judge', 'host', '--consent', 'yes', *LINES[:2])[0], 1)
        self.assertEqual(target.read_bytes(), PREFIX)
        self.assertFalse(self.plan.exists())

    def test_symlinked_host_after_preview_is_refused_at_apply(self):
        digest = self.preview()
        target = self.host.parent / 'elsewhere.md'
        target.write_bytes(PREFIX)
        self.host.unlink()
        self.host.symlink_to(target)
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)
        self.assertEqual(target.read_bytes(), PREFIX)

    # show

    def test_show_prints_table_then_judge(self):
        self.assertEqual(self.cli('apply', '--digest', self.preview())[0], 0)
        code, out, _ = self.cli('show')
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            '| Agent | Levels | Works on | Model | Roles |',
            '| --- | --- | --- | --- | --- |',
            '| claude | 1-5 | frontend, design | claude-opus-5-5 | none |',
            '| codex | 1-4 | image-generation |  | security-review |',
            '| antigravity | 1-3 |  |  | code-review, navigator |',
            'Judge: jev',
            'Review posting: not recorded',
            'Unverified: claude model claude-opus-5-5 is not among the allowed models on this machine'])
        self.assertNotIn(str(self.home), out)

    def test_show_reports_posting_words_and_accepts_an_allowed_model(self):
        self.assertEqual(self.cli('apply', '--digest', self.preview())[0], 0)
        extra = (b'\n## Agents on this machine\n\n| Agent | Present | Version | Allowed models | Checked |\n| --- | --- | --- | --- | --- |\n'
                 b'| Claude Code | yes | 1 | claude-opus-*,other | 2026-11-09 |\n'
                 b'\n## Review posting\n\n- codex: unverified (checked 2026-11-08)\n- antigravity: yes private note\n')
        self.host.write_bytes(self.host.read_bytes() + extra)
        out = self.cli('show')[1]
        self.assertIn('Review posting: codex unverified, antigravity yes', out)
        self.assertNotIn('Unverified', out)
        self.assertNotIn('private note', out)

    def test_show_ignores_fenced_posting_and_inventory_lines(self):
        self.assertEqual(self.cli('apply', '--digest', self.preview())[0], 0)
        # An info-string fence line inside a fence does not close it; only a bare closing fence does.
        extra = (b'\n## Agents on this machine\n\n| Agent | Present | Version | Allowed models | Checked |\n| --- | --- | --- | --- | --- |\n'
                 b'```md\n```text\n| Claude Code | yes | 1 | claude-opus-* | 2026-11-09 |\n```\n'
                 b'\n## Review posting\n\n- codex: no (checked 2026-11-08)\n~~~\n~~~md\n- antigravity: yes (checked 2026-11-08)\n~~~\n')
        self.host.write_bytes(self.host.read_bytes() + extra)
        code, out, _ = self.cli('show')
        self.assertEqual(code, 0)
        self.assertIn('Review posting: codex no\n', out)
        self.assertIn('Unverified: claude model claude-opus-5-5', out)

    def test_advisor_role_is_accepted_once(self):
        code, out, err = self.cli('validate', '--judge', 'host', '--consent', 'yes', '--line', 'claude: levels 1-5',
                                  '--line', 'codex: levels 1-5; roles advisor')
        self.assertEqual((code, err), (0, ''))
        self.assertIn('- codex: levels 1-5; roles advisor\n', out)
        self.assertEqual(self.cli('validate', '--judge', 'host', '--consent', 'yes', '--line', 'claude: levels 1-5; roles advisor',
                                  '--line', 'codex: levels 1-5; roles advisor')[0], 1)

    def test_show_absent_says_legacy_applies(self):
        code, out, _ = self.cli('show')
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), 'The assignment matrix is not set: no review roles, judge host; Agent roles is no longer read, and migrate converts it.')
        self.host.unlink()
        self.assertEqual(self.cli('show')[:2], (0, out))

    def test_show_invalid_lists_each_reason_and_no_table(self):
        self.host.write_bytes(PREFIX + b'## Assignment matrix\n- Consent: no\n- Judge: host\n- gemini: levels 1-2\n'
                              b'- claude: levels 1-2; roles navigator\n- codex: levels 1-2; roles navigator\n')
        code, out, _ = self.cli('show')
        self.assertEqual(code, 3)
        self.assertIn('Problem: unknown agent', out)
        self.assertIn('Problem: duplicate role', out)
        self.assertNotIn('| Agent', out)
        self.assertNotIn('gemini', out)

    def test_show_reports_unreadable_host(self):
        self.host.write_bytes(b'\xff\xfe## Assignment matrix\n')
        self.assertEqual(self.cli('show')[0], 3)

    # migrate

    def migrate(self, *extra):
        code, out, err = self.cli('migrate', *extra)
        self.assertEqual(code, 0, err)
        return out, out.split('Digest: ')[1].splitlines()[0]

    def test_migrate_preview_maps_roles_levels_judge_and_shows_new_yes(self):
        self.host.write_bytes(PREFIX + LEGACY)
        out, _ = self.migrate()
        self.assertIn('- Judge: jev', out)
        self.assertIn('- claudework: levels 3-5', out)
        self.assertIn('- codex: levels 1-4; roles security-review', out)
        self.assertIn('- claude: levels 1-5; roles navigator', out)
        self.assertIn('- antigravity: levels 1-5; roles code-review', out)
        self.assertIn('claude: no levels recorded; levels 1-5 shown', out)
        self.assertIn('new yes is needed', out)
        self.assertNotIn('dropped', out)
        self.assertEqual(self.host.read_bytes(), PREFIX + LEGACY)

    def test_migrate_apply_needs_a_new_consent_and_removes_legacy_in_one_write(self):
        self.host.write_bytes(PREFIX + LEGACY + b'## Tail\r\nafter\r\n')
        _, digest = self.migrate()
        before = self.host.read_bytes()
        self.assertEqual(self.cli('apply', '--digest', digest)[0], 1)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(self.cli('apply', '--digest', digest, '--consent', 'yes')[0], 0)
        raw = self.host.read_bytes()
        self.assertNotIn(b'## Agent roles', raw)
        self.assertNotIn(b'## Agent levels', raw)
        self.assertNotIn(b'2026-10-01', raw)
        self.assertTrue(raw.startswith(PREFIX))
        self.assertIn(b'## Tail\r\nafter\r\n', raw)
        self.assertIn(f'- Consent: yes ({TODAY})'.encode(), raw)
        self.assertEqual(self.backups()[0].read_bytes(), before)
        code, out, _ = self.cli('show')
        self.assertEqual(code, 0)
        self.assertIn('| claudework | 3-5 |  |  | none |', out)
        self.assertIn('Judge: jev', out)

    def test_migrate_lists_dropped_lines_and_refuses_without_ack(self):
        legacy = (b'## Agent roles\n- code review: gemini\n- security review: codex\n- navigator: claude\n- judge: jev\n- note: zzSECRETzz hello\n'
                  b'## Agent levels\n- Consent: no\n')
        self.host.write_bytes(PREFIX + legacy)
        out, digest = self.migrate()
        self.assertEqual(len([l for l in out.splitlines() if l.startswith('dropped:')]), 2)
        self.assertIn('dropped: Agent roles line 1', out)
        self.assertNotIn('zzSECRETzz', out)
        before = self.host.read_bytes()
        code, _, err = self.cli('apply', '--digest', digest, '--consent', 'yes')
        self.assertEqual(code, 3)
        self.assertNotIn('zzSECRETzz', err)
        self.assertEqual(self.host.read_bytes(), before)
        self.assertEqual(self.cli('apply', '--digest', digest, '--consent', 'yes', '--ack-dropped')[0], 0)
        raw = self.host.read_bytes()
        self.assertNotIn(b'gemini', raw)
        self.assertNotIn(b'## Agent roles', raw)
        self.assertEqual(self.backups()[0].read_bytes(), before)

    def test_migrate_never_prints_the_text_of_a_dropped_line(self):
        secret = 'a' * 32
        self.host.write_bytes(PREFIX + b'## Agent roles\n- password: ' + secret.encode() + b'\n- code review: codex\n')
        out = self.cli('migrate')[1]
        self.assertIn('dropped: Agent roles line 1: unrecognized or repeated line', out)
        self.assertNotIn(secret, out)
        self.assertNotIn('password', out)
        self.assertNotIn(secret.encode(), self.plan.read_bytes())

    def test_migrate_unreadable_levels_section_is_dropped(self):
        self.host.write_bytes(PREFIX + b'## Agent levels\n- Consent: yes (2026-10-01)\n- claudework: levels 9-9\n')
        out, digest = self.migrate()
        self.assertIn('dropped: Agent levels section unreadable', out)
        self.assertEqual(self.cli('apply', '--digest', digest, '--consent', 'yes')[0], 3)

    def test_migrate_refuses_when_matrix_exists_or_nothing_to_migrate(self):
        self.host.write_bytes(PREFIX + LEGACY + b'## Assignment matrix\n- Consent: no\n- Judge: host\n')
        before = self.host.read_bytes()
        self.assertEqual(self.cli('migrate')[0], 1)
        self.host.write_bytes(PREFIX)
        self.assertEqual(self.cli('migrate')[0], 1)
        self.host.write_bytes(PREFIX + b'## Agent roles\n- judge: host\n## Agent roles\n- judge: jev\n')
        self.assertEqual(self.cli('migrate')[0], 1)
        self.assertFalse(self.plan.exists())
        self.host.write_bytes(before)
        self.assertEqual(self.cli('migrate')[0], 1)

    def test_migrate_ignores_fenced_legacy_headings(self):
        self.host.write_bytes(PREFIX + b'```\n## Agent roles\n- judge: jev\n```\n')
        self.assertEqual(self.cli('migrate')[0], 1)

    def test_migrate_judge_defaults_to_host_and_agent_limit_is_dropped(self):
        levels = b''.join(f'- claudex{i}: levels 1-2\n'.encode() for i in range(8))
        self.host.write_bytes(PREFIX + b'## Agent roles\n- navigator: codex\n## Agent levels\n- Consent: yes (2026-10-01)\n' + levels)
        out, digest = self.migrate()
        self.assertIn('- Judge: host', out)
        self.assertIn('dropped: Agent roles line 1', out)
        self.assertEqual(self.cli('apply', '--digest', digest, '--consent', 'yes')[0], 3)

    def test_migrate_plan_cannot_be_applied_as_a_changed_host(self):
        self.host.write_bytes(PREFIX + LEGACY)
        _, digest = self.migrate()
        self.host.write_bytes(PREFIX + LEGACY + b'x\r\n')
        self.assertEqual(self.cli('apply', '--digest', digest, '--consent', 'yes')[0], 1)

    # candidates and isolation

    def test_candidates_lists_names_only_and_runs_nothing(self):
        bin_dir = self.home / 'bin'
        bin_dir.mkdir()
        for name, mode in (('claudework', 0o755), ('claudeomni', 0o755), ('claudenox', 0o644), ('claude', 0o755), ('other', 0o755)):
            (bin_dir / name).write_text('#!/bin/sh\n')
            (bin_dir / name).chmod(mode)
        (self.home / '.claude-work').mkdir()
        with mock.patch.dict(os.environ, {'PATH': f'{bin_dir}:relative/bin'}), \
                mock.patch('subprocess.run', side_effect=AssertionError('command run')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('command run')):
            code, out, _ = self.cli('candidates')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {'commands': ['claudeomni', 'claudework'], 'folders': ['work']})
        self.assertNotIn(str(self.home), out)

    def test_writer_runs_no_command_and_makes_no_network_call(self):
        self.host.write_bytes(PREFIX + LEGACY)
        with mock.patch('subprocess.run', side_effect=AssertionError('command run')), \
                mock.patch('subprocess.Popen', side_effect=AssertionError('command run')), \
                mock.patch('socket.socket', side_effect=AssertionError('network')):
            self.preview()
            _, digest = self.migrate()
            self.assertEqual(self.cli('apply', '--digest', digest, '--consent', 'yes')[0], 0)
        text = SCRIPT.read_text()
        for word in ('subprocess', 'socket', 'urllib', 'os.environ'):
            self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()
