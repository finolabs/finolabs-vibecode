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
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/delegate/scripts/afk.py'
SETUP = '## afk\n- Hosts: Claude Code\n'
ORIGIN_CONFIG = ('[core]\n\trepositoryformatversion = 0\n\tbare = false\n'
                 '[remote "origin"]\n\turl = https://github.com/example/demo.git\n'
                 '\tfetch = +refs/heads/*:refs/remotes/origin/*\n')
# A setup 0.3.2 wrote for `strict`, with every line only `strict` read (docs/specs/afk-one-mode.md).
OLD_STRICT = ('## afk\n- Mode: strict\n- Hosts: Claude Code\n- Task choice: choose\n- Push and pull requests: yes\n'
              '- Merge: yes\n- Trusted authors: own\n- Lease hours: 8\n- Max runs: 20\n- Max runtime minutes: 480\n'
              '- Max actions per hour: 30\n- Quota floor percent: 15\n- Production: stop\n'
              '- Real users and customer data: stop\n- Unrecoverable deletion: stop\n'
              '- Messages outside the repository: stop\n- Tags and releases: stop\n- Publishing: stop\n'
              '- Shared settings: stop\n- Recoverable deletion: decide\n- Repository comments: decide\n'
              '- Excerpts leave the machine: no\n- Non-production targets: npm run deploy:dev\n'
              '- Test commands: make test\n- Top-level files: TASKS.md\n- Release targets: git tag v1.0.0\n'
              '- Production targets: npm run deploy:prod\n')


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
    def test_start_requires_setup(self):
        for text in ('', '## Other\n'):
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
        self.assertIn('Lease hours: 8', summary)

    def test_summary_private_lease_second_start_and_stop(self):
        self.setup_config()
        status, summary = self.invoke('start', '--hours', '2')
        self.assertEqual(status, 0, summary)
        self.assertEqual(summary.splitlines()[:7], [
            'afk started', '- Third-party instructions: guard', '- Default branch: guard', '- Lease hours: 2',
            '- Hosts: Claude Code', '- Quota floor percent: 15', '- Excerpts leave the machine: no'])
        for word in ('Mode', 'Max ', 'Merge', 'strict'):
            self.assertNotIn(word, summary)
        self.assertEqual(set(self.lease()), {'id', 'start', 'expiry', 'settings_hash'})  # no per-project counters
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
            status, output = self.invoke('stop', '--all')
            self.assertEqual(status, 0, output)
            self.assertFalse((self.state / 'lease.json').exists())
            self.assertTrue((self.state / 'stop').is_file())
        self.assertIn('already absent', output)
        self.assertEqual(stat.S_IMODE((self.state / 'stop').stat().st_mode), 0o600)
        self.assertEqual(self.invoke('start')[0], 0)
        self.assertFalse((self.state / 'stop').exists())

    def test_invalid_setup_and_hours_fail_closed(self):
        for text in (SETUP + '- Unknown: yes\n', SETUP + '- Lease hours: 25\n', SETUP + '- Lease hours: 0\n',
                     SETUP + '- Quota floor percent: 101\n', SETUP + '- Default branch: off\n',
                     SETUP + '- Third-party instructions: closed\n', SETUP + '- Hosts: Codex\n',
                     SETUP.replace('Claude Code', 'Gemini'), SETUP + '## afk\n- Lease hours: 4\n'):
            with self.subTest(text=text):
                self.setup_config(text)
                self.assertEqual(self.invoke('start')[0], 3)
        self.setup_config(SETUP + '- Lease hours: 8\n')
        for hours in ('0', '25', '9', 'nan'):
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
        self.setup_config(SETUP.replace('Claude Code', 'Codex'))
        self.check(['git', 'status'], tier=3, code='setup-changed')
        self.setup_config()
        for _ in range(40):  # no run, runtime or hourly limit: Lease hours is the only one
            self.check(['git', 'status'])
        self.clock += 8 * 3600 - 1
        self.check(['git', 'status'])

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
    'table yes, jev': (('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--of', '2', '--probability', '0.9'),
                       dict(by='jev', of=2, probability=0.9)),
    'table yes, host-small': (('--rung', 'table', '--settled', 'yes', '--by', 'host-small', '--of', '3', '--probability', '0.4'),
                              dict(by='host-small', of=3, probability=0.4)),
    'table unavailable': (('--rung', 'table', '--settled', 'unavailable', '--by', 'jev'), dict(by='jev')),
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


class AwayDecisionTest(AfkBase):
    """Away decisions, scripts part: decision records, reviews and the packet check."""

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
                      ('--rung', 'jev', '--settled', 'yes', '--by', 'jev', '--option', '1', '--of', '2', '--probability', '0.9'),
                      ('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--option', '1', '--of', '2', '--probability', '0.9'),
                      ('--rung', 'table', '--settled', 'no', '--by', 'jev', '--probability', '0.5'),
                      ('--rung', 'table', '--settled', 'yes', '--by', 'codex', '--of', '2', '--probability', '0.5'),
                      ('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--of', '7', '--probability', '0.5'),
                      ('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--of', '2', '--probability', 'nan'),
                      ('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--of', '2', '--probability', '1.5'),
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

    def test_a_schema_refusal_names_the_field_and_a_state_failure_stays_generic(self):
        self.start()
        generic = 'afk refused: setup or private state is missing, invalid, unsafe or already active\n'
        advisor_no = ROWS['advisor no'][0]
        for flags, kwargs, message in (
                (advisor_no + ('--option', '1', '--of', '3'), {}, 'the advisor no row takes no --of, --option'),
                (('--rung', 'advisor', '--settled', 'yes', '--by', 'codex'), {},
                 'the advisor yes row needs --dispatch, --model, --of, --option'),
                (ROWS['park yes'][0] + ('--decision', 'q20261115-000000-abcd'), {}, '--decision names no recorded decision id'),
                (ROWS['park yes'][0], dict(precedents='9'), '--precedents is a whole number from 0 to 8'),
                (ROWS['park yes'][0], dict(topic='src/private.py'), '--topic and --project are short labels'),
                (('--rung', 'user', '--settled', 'yes'), {}, '--rung and --settled name no row of the decision schema'),
                (('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '3', '--of', '2'), {},
                 '--option is a whole number from 1 to --of'),
                (('--rung', 'rule', '--settled', 'yes', '--by', 'rule', '--option', '1', '--of', '7'), {},
                 '--of is a whole number from 2 to 6'),
                (('--rung', 'advisor', '--settled', 'no', '--by', 'codex', '--dispatch', 'bad', '--model', 'm'), {},
                 '--dispatch is a ledger dispatch id')):
            with self.subTest(message=message):
                status, output = self.decide(*flags, **kwargs)
                self.assertEqual(status, 3, output)
                self.assertTrue(output.startswith('afk refused: ' + message), output)
                self.assertNotIn('private state', output)
        # The message never echoes a value the caller passed.
        status, output = self.decide(*ROWS['park yes'][0], topic='ghp_' + 'x' * 30)
        self.assertNotIn('ghp_', output)
        status, output = self.invoke('log', '--kind', 'action', '--rung', 'park')
        self.assertEqual(status, 3)
        self.assertIn('belong to --kind decision only', output)
        status, output = self.invoke('review', '--decision', 'q20261115-000000-abcd', 'kept')
        self.assertEqual((status, output), (3, 'afk refused: --decision names no recorded decision id\n'))
        # Without a live lease, or with unreadable private state, the refusal stays generic.
        self.assertEqual(self.invoke('stop', '--all')[0], 0)
        self.assertEqual(self.decide(*ROWS['park yes'][0]), (3, 'afk refused: --kind decision needs a live lease\n'))
        self.state.chmod(0o755)
        self.addCleanup(self.state.chmod, 0o700)
        self.assertEqual(self.decide(*ROWS['park yes'][0]), (3, generic))

    def test_a_table_probability_round_trips_unchanged_with_no_threshold(self):
        self.start()
        # Any top probability in 0..1 records as a table: the table decides nothing, so no value settles or blocks.
        for p in (0.823456789, 0.8, 1.0, 0.7999999999999999, 1 / 3, 0.0):
            with self.subTest(p=p):
                _, line = self.recorded('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--of', '2', '--probability', str(p))
                self.assertEqual(line['probability'], p)
                self.assertIs(type(line['probability']), float)
        # The judge's own table, with the provider call stubbed (no network), reaches the record unchanged.
        self.load()
        import judge
        spread = {'1': 0.823456789, '2': 0.176543211}
        with patch.object(judge, 'configured_judge', return_value='jev'), patch.object(judge, 'post', return_value=spread), \
                patch.dict(os.environ, {'FNL_JUDGE': 'on'}):
            table = judge.ask_choice('Which schema fits the spec?', ['Keep one schema', 'Split it'], 'Goal: one schema.')
        self.assertEqual(table, {'source': 'jev', 'of': 2, 'probabilities': [0.823456789, 0.176543211]})
        _, line = self.recorded('--rung', 'table', '--settled', 'yes', '--by', table['source'], '--of', str(table['of']),
                                '--probability', str(max(table['probabilities'])))
        self.assertEqual((line['of'], line['probability']), (2, 0.823456789))
        self.assertNotIn('option', line)
        # Anything that is not a bounded plain number in 0..1 is refused.
        for p in ('nan', 'inf', '-0.1', '1.0000001', '1e400', '0x1', '0.5 ', ' 0.5', '0.' + '5' * 40, '', '.5', '1_0', '8e-1'):
            with self.subTest(p=p):
                self.refused('--rung', 'table', '--settled', 'yes', '--by', 'jev', '--of', '2', '--probability', p)

    def test_the_id_is_generated_once_and_later_attempts_must_pass_an_existing_one(self):
        self.start()
        first, line = self.recorded(*ROWS['table unavailable'][0])
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
            'options not closed': ['advisor yes'],
            'jev refuses, times out or fails': ['table unavailable', 'table yes, host-small', 'advisor yes'],
            'a table, then the advisor': ['table yes, jev', 'advisor yes'],
            'host-only hosts, no advisor': ['table yes, jev', 'advisor unavailable, no candidate', 'host yes'],
            'advisor out of quota or failed': ['advisor unavailable, selected and started', 'host yes'],
            'advisor answers none': ['advisor no', 'host yes'],
            'advisor names an option outside the list': ['advisor no', 'host yes'],
            'a new fact at the same rung': ['advisor yes', 'advisor yes'],
            'a new fact and the answer does not hold': ['advisor yes', 'advisor no', 'host yes'],
            'a rule invalidated by new evidence': ['rule yes', 'rule no', 'host yes'],
            'where it must stop': ['park yes'],
            'a rung answered, then the check parked it': ['advisor yes', 'park yes'],
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                before = len(self.ledger())
                identifier, _ = self.recorded(*ROWS[rows[0]][0], precedents='0')
                for number, row in enumerate(rows[1:]):
                    # A later attempt may name the id in another case; it is recorded as generated (lowercase).
                    typed = identifier.upper() if number % 2 else identifier
                    self.recorded(*ROWS[row][0], '--decision', typed, precedents='0')
                lines = self.ledger()[before:]
                self.assertEqual({line['id'] for line in lines}, {identifier})
                self.assertEqual([(line['rung'], line['settled']) for line in lines],
                                 [tuple(ROWS[row][0][1:4:2]) for row in rows])
                self.assertEqual({line['precedents'] for line in lines}, {0})

    def test_review_records_kept_or_reversed_for_an_existing_decision_only(self):
        self.start()
        identifier, _ = self.recorded(*ROWS['host yes'][0])
        self.assertEqual(self.invoke('stop', '--all')[0], 0)  # reviews happen after the user returns
        for verdict in ('kept', 'reversed'):
            status, output = self.invoke('review', '--decision', identifier, verdict)
            self.assertEqual(status, 0, output)
            line = self.ledger()[-1]
            self.assertEqual(line, dict(event='decision_review', id=identifier, ts=line['ts'], verdict=verdict))
        # An id typed in another case names the same decision and is recorded as generated (lowercase).
        status, output = self.invoke('review', '--decision', identifier.upper(), 'kept')
        self.assertEqual(status, 0, output)
        self.assertEqual(self.ledger()[-1]['id'], identifier)
        before = self.ledger()
        for identifier in ('q20261110-010203-ffff', 'bad'):
            self.assertEqual(self.invoke('review', '--decision', identifier, 'kept')[0], 3)
        self.assertEqual(self.ledger(), before)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke('review', '--decision', identifier, 'maybe')

    # Where it must stop


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


class AwayFlowTest(AfkBase):
    """The merge pin and the log entries that name it."""
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

    def test_a_merge_entry_needs_an_allowed_merge_check_of_this_lease(self):
        self.start()
        self.cwd, _ = self.git_repo('pinned')
        head, other = 'c' * 40, 'd' * 40
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 3)  # no check yet
        self.check(['gh', 'pr', 'merge', '7', '--squash', '--match-head-commit=' + head, '--repo', 'github.com/example/demo'])
        for pr, sha in (('8', head), ('7', other)):
            with self.subTest(pr=pr, sha=sha):
                self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', pr, '--head', sha)[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 0)
        record = json.loads((self.state / 'log.jsonl').read_text().splitlines()[-1])
        self.assertEqual((record['kind'], record['repo']), ('merge', 'github.com/example/demo'))
        self.invoke('stop', '--all')
        self.clock += 60
        self.start()  # a new lease does not inherit the old pin
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 3)

    def test_a_merge_needs_no_merge_ok_receipt(self):
        # `merge-unchecked` belonged to `strict` (docs/specs/afk-one-mode.md): the merge gate stays advisory.
        self.start()
        self.check(['gh', 'pr', 'merge', '7', '--merge'] + PIN + ['--repo', 'github.com/example/demo'])
        self.check(['gh', 'pr', 'merge', '8'])

    def test_a_review_fallback_entry_records_the_head_and_pins_nothing(self):
        self.start()
        head = 'e' * 40
        self.assertEqual(self.invoke('log', '--kind', 'review-fallback', '--pr', '7', '--head', head)[0], 0)
        for flags in (('--pr', '7'), ('--head', head), ('--pr', '7', '--head', 'E' * 40), ('--pr', '07', '--head', head)):
            with self.subTest(flags=flags):
                self.assertEqual(self.invoke('log', '--kind', 'review-fallback', *flags)[0], 3)
        # It is not a merge: the merge entry still needs its own allowed merge check.
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 3)
        merge = ['python3', '-I', str(ROOT / 'skills/review-gate/scripts/merge_check.py'), '7', '--repo', 'example/demo',
                 '--independent', '--fallback-family', 'claude']
        self.check(merge)

    def test_check_exits_three_on_tier_three_and_zero_on_tier_one(self):
        self.start()
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')
        for argv, status, tier in ((['git', 'status'], 0, 1), (['git', 'push', 'origin', 'main'], 3, 3),
                                   (['git', 'show', 'HEAD:.env'], 3, 3), (['echo', 'safe'], 0, 1),
                                   (['npm', 'publish'], 0, 1)):
            with self.subTest(argv=argv):
                result = self.invoke('check', '--argv-json', json.dumps(argv))
                self.assertEqual(result[0], status, result)
                self.assertEqual(json.loads(result[1])['tier'], tier)
        self.assertEqual(self.invoke('check', '--paths', '.env')[0], 3)
        self.assertEqual(self.invoke('check', '--paths', '.github/workflows/x.yml')[0], 0)
        self.invoke('stop', '--all')
        self.assertEqual(self.invoke('check', '--argv-json', '["git", "status"]')[0], 3)  # no lease

    def test_a_merge_entry_matching_pins_of_two_repositories_is_refused(self):
        self.start()
        head = 'c' * 40
        first, _ = self.git_repo('first')
        second, git = self.git_repo('second')
        git('remote', 'set-url', 'origin', 'https://github.com/other/demo.git')
        self.cwd = first
        self.check(['gh', 'pr', 'merge', '7', '--merge', '--match-head-commit', head, '--repo', 'github.com/example/demo'])
        self.cwd = second
        self.check(['gh', 'pr', 'merge', '7', '--merge', '--match-head-commit', head, '--repo', 'github.com/other/demo'])
        status, output = self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)
        self.assertEqual(status, 3, output)

    def test_a_merge_check_with_an_unwritable_log_pins_nothing(self):
        # merge-gate.md: the check still answers, but a log that cannot be written records no pin, so the merge
        # entry for that head is refused and the cleanup parks.
        self.start()
        self.cwd, _ = self.git_repo('unwritable')
        head = 'c' * 40
        log = self.state / 'log.jsonl'
        log.write_text('[]\n')  # an invalid line makes every append refuse
        log.chmod(0o600)
        result = self.invoke('check', '--argv-json', json.dumps(
            ['gh', 'pr', 'merge', '7', '--merge', '--match-head-commit', head, '--repo', 'github.com/example/demo']))
        self.assertEqual((result[0], json.loads(result[1])['tier']), (0, 1), result)
        self.assertNotIn('merge-pin', log.read_text())
        self.assertEqual(self.invoke('log', '--kind', 'merge', '--pr', '7', '--head', head)[0], 3)


def load_store():
    spec = importlib.util.spec_from_file_location('project_store_tested', SCRIPT.parent / 'project_store.py')
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    return store


class RetiredSetupTest(AfkBase):
    """Decisions 3 and 4 of docs/specs/afk-one-mode.md: retired lines and keys start normally with one notice."""

    def setUp(self):
        super().setUp()
        self.store = load_store()

    def project(self, value):
        found, ident = self.store.identity(self.repo)
        self.store.write_setting(self.repo, 'autopilot', value, ident=ident)  # as an older setup wrote it

    def test_an_old_strict_setup_starts_normally_with_one_line_each(self):
        ap = self.load()
        self.setup_config(OLD_STRICT)
        status, output = self.invoke('start')
        self.assertEqual(status, 0, output)
        lines = output.splitlines()
        self.assertEqual(lines.count(ap.STRICT_REMOVED), 1)
        self.assertEqual(lines.count(ap.LIMITS_REMOVED), 1)
        for word in ('- Mode', '- Max', '- Merge', 'Task choice', 'Production', 'Test commands'):
            self.assertNotIn(word, output)
        self.assertEqual(set(self.lease()), {'id', 'start', 'expiry', 'settings_hash'})
        # The retired lines are not read: what strict denied is Tier 1, and no hourly cap of 30 applies.
        for argv in (['npm', 'publish'], ['gh', 'pr', 'merge', '7'], ['git', 'tag', 'v2.0.0']):
            self.check(argv)
        for _ in range(31):
            self.check(['git', 'status'])
        self.check(['printenv'], tier=3, code='floor')

    def test_the_notice_lines_name_only_what_the_setup_holds(self):
        ap = self.load()
        for text, expected in ((SETUP + '- Mode: strict\n', [ap.STRICT_REMOVED]),
                               (SETUP + '- Mode: open\n', []),
                               (SETUP + '- Max runs: 5\n- Max actions per hour: 9\n', [ap.LIMITS_REMOVED]),
                               (SETUP + '- Merge: no\n- Trusted authors: own\n', []),
                               (SETUP, [])):
            with self.subTest(text=text):
                self.invoke('stop', '--all')
                self.setup_config(text)
                status, output = self.invoke('start')
                self.assertEqual(status, 0, output)
                self.assertEqual([line for line in output.splitlines() if line.startswith('afk: ')], expected)

    def test_a_retired_line_still_may_not_repeat_and_the_lease_hash_ignores_its_value(self):
        self.setup_config(SETUP + '- Mode: strict\n- Mode: open\n')
        self.assertEqual(self.invoke('start')[0], 3)
        self.start(SETUP + '- Max runs: 5\n')
        self.setup_config(SETUP + '- Max runs: 6\n')  # the hash covers what is read; a retired value is not read
        self.check(['git', 'status'])
        self.setup_config(SETUP + '- Lease hours: 7\n')
        self.check(['git', 'status'], tier=3, code='setup-changed')

    def test_old_repository_keys_are_named_and_not_read(self):
        self.project({'mode': 'strict', 'max-runs': 5, 'merge': 'no', 'decide': [], 'default-branch': 'open'})
        self.setup_config()
        status, output = self.invoke('start')
        self.assertEqual(status, 0, output)
        self.assertIn("this repository's `mode` key is no longer read", output)
        self.assertIn("This repository's max-runs, max-runtime-minutes and max-actions-per-hour keys", output)
        self.assertIn('This folder (project): Third-party instructions: guard; Default branch: open.', output)
        self.check(['npm', 'publish'])
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/main\n')
        self.check(['git', 'push', 'origin', 'main'])  # the repository's guard key is still read
        status, output = self.invoke('effective')
        view = json.loads(output.splitlines()[0])
        self.assertEqual(output.splitlines()[1], 'Project settings: recorded')
        self.assertEqual((view['state'], view['guards']['Default branch'], len(view['retired'])), ('project', 'open', 2))
        self.assertNotIn('mode', view)

    def test_a_lease_written_before_0_3_3_reads_invalid_until_stopped(self):
        self.start()
        self.change_lease(lambda v: v.update(counters={}))
        self.check(['git', 'status'], tier=3, code='unsafe')
        self.assertEqual(self.invoke('start')[0], 3)
        self.assertEqual(self.invoke('stop', '--all')[0], 0)
        self.assertEqual(self.invoke('start')[0], 0)
        self.check(['git', 'status'])


class SetupNeverWritesRetiredTest(unittest.TestCase):
    """Decisions 3 and 4: setup asks no mode or limit question and never writes those lines or keys."""

    def test_the_account_section_has_no_retired_line(self):
        spec = importlib.util.spec_from_file_location('afk_setup_tested', ROOT / 'skills/setup/scripts/afk_setup.py')
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        spec = importlib.util.spec_from_file_location('afk_read', SCRIPT)
        ap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ap)
        values = {'Hosts': 'Claude Code', 'Lease hours': 8, 'Quota floor percent': 15,
                  'Third-party instructions': 'guard', 'Default branch': 'guard', 'Excerpts leave the machine': 'no'}
        section = setup.render(values)
        for name in ap.RETIRED:
            self.assertNotIn('- %s:' % name, section)
        for extra in ({'Mode': 'open'}, {'Max runs': 20}, {'Merge': 'yes'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                setup.validate({**values, **extra})
        with contextlib.redirect_stderr(io.StringIO()):
            for flag in (('--mode', 'strict'), ('--max-runs', '5'), ('--merge', 'yes'), ('--decide', 'publishing')):
                with self.subTest(flag=flag):
                    self.assertEqual(setup.main(['preview', *flag]), 1)

    def test_the_repository_writer_refuses_retired_keys(self):
        store = load_store()
        for value in ({'mode': 'open'}, {'mode': 'strict'}, {'max-runs': 5}, {'max-runtime-minutes': 60},
                      {'max-actions-per-hour': 9}, {'merge': 'decide'}, {'default-branch': 'open', 'max-runs': 5}):
            with self.subTest(value=value):
                self.assertTrue(store.valid_autopilot(value))  # an older approved file stays readable
                with self.assertRaises(ValueError):
                    store.autopilot_value(json.dumps(value))
        self.assertEqual(store.autopilot_value('{"default-branch": "open", "third-party-instructions": "guard"}'),
                         {'third-party-instructions': 'guard', 'default-branch': 'open'})


class DeciderTest(AfkBase):
    """docs/specs/afk-decider.md: the lease end the stop hook reads, the native rules notice and the permission
    approvals `check` never consumes."""

    def log_kinds(self):
        return [json.loads(line)['kind'] for line in (self.state / 'log.jsonl').read_text().splitlines()]

    def test_lease_over_follows_the_lease_only(self):
        ap = self.load()
        self.start(OLD_STRICT)
        with ap.private_folder() as folder:
            self.assertFalse(ap.lease_over(folder, self.clock))
            self.assertTrue(ap.lease_over(folder, self.clock + 8 * 3600))
        self.setup_config(SETUP.replace('Claude Code', 'Codex'))  # a setup change ends what the lease allows
        with ap.private_folder() as folder:
            self.assertTrue(ap.lease_over(folder, self.clock))

    def test_start_offers_the_native_allow_rules_and_warns_without_deny_rules(self):
        self.setup_config()
        status, output = self.invoke('start')
        self.assertEqual(status, 0, output)
        self.assertIn('Warning: Claude Code has no deny rule for the credential floor', output)
        self.invoke('stop', '--all')
        settings = self.home / '.claude/settings.json'
        settings.parent.mkdir()
        ap = self.load()
        settings.write_text(json.dumps({'permissions': {'deny': [ap.FLOOR_RULES[0]]}}))
        status, output = self.invoke('start')
        self.assertNotIn('Warning:', output)
        self.invoke('stop', '--all')
        settings.write_text(json.dumps({'permissions': {'defaultMode': 'default'}}))
        self.assertNotIn('Warning:', self.invoke('start')[1])
        self.invoke('stop', '--all')
        settings.write_text(json.dumps({'permissions': {'defaultMode': 'bypassPermissions'}}))
        self.assertIn('Warning:', self.invoke('start')[1])

    def test_the_floor_rules_match_the_setup_script(self):
        spec = importlib.util.spec_from_file_location('native_tested', ROOT / 'skills/setup/scripts/afk_native_rules.py')
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)
        self.assertEqual(self.load().FLOOR_RULES, native.FLOOR_RULES)

    def test_check_never_consumes_a_permission_approval(self):
        self.start()
        host = ('--rung', 'host', '--settled', 'yes', '--by', 'claude', '--option', '1', '--of', '2',
                '--model', 'claude-opus-5-5')
        status, output = self.invoke('log', '--kind', 'decision', '--project', 'demo', '--topic', 'run it',
                                     '--precedents', '0', *host, '--approve-request', 'c' * 64)
        self.assertEqual(status, 0, output)
        self.check(['scripts/ci-local.sh', 'fast'])
        permits = json.loads((self.state / 'permits.json').read_text())
        self.assertEqual([(e['kind'], e['digest']) for e in permits], [('approval', 'c' * 64)])
        self.assertIn('permit', self.log_kinds())
        for flag in ('--approve-argv-json', '--approve-paths'):  # removed with `strict`
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.invoke('log', '--kind', 'decision', '--project', 'demo', '--topic', 'run it', '--precedents',
                            '0', *host, flag, '["make"]')


def item(label='fix login', kind='fix', minutes=30):
    return {'label': label, 'kind': kind, 'minutes': minutes}


class GoalTest(AfkBase):
    """docs/specs/afk-goals.md A and E: the queue, the goal, `--item`, the idle refusals and the lease scope."""

    def items(self, values, name='items.json'):
        folder = self.repo / '.finolabs/briefs'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text(json.dumps(values))
        return str(path)

    def goal(self, values, status=0):
        code, output = self.invoke('goal', '--items-file', self.items(values))
        self.assertEqual(code, status, output)
        return output

    def queue(self):
        store = load_store()
        key = store.identity_digest(store.identity(self.repo)[1].main)
        return json.loads((self.state / f'queue-{key}.json').read_text()), key

    def records(self):
        return [json.loads(line) for line in (self.state / 'log.jsonl').read_text().splitlines()]

    def test_goal_prints_the_goal_line_the_queue_and_appends(self):
        ap = self.load()
        self.start()
        output = self.goal([item(), item('review pr 12', 'review', 45)])
        lines = output.splitlines()
        self.assertEqual(lines[0], 'Every item in the afk queue of this repository is done or parked, or the away '
                                   'lease has ended.')
        self.assertEqual(lines[0], ap.GOAL_LINE)
        self.assertEqual(lines[1], 'Queue (revision 1; 480 minutes left on the lease):')
        self.assertEqual(lines[2:4], ['1. [open] fix login (fix, 30 min)', '2. [open] review pr 12 (review, 45 min)'])
        self.assertIn('Warning: the queue is short: add the next work', lines)
        queue, key = self.queue()
        self.assertEqual((queue['revision'], [i['n'] for i in queue['items']]), (1, [1, 2]))
        self.assertEqual(stat.S_IMODE((self.state / f'queue-{key}.json').stat().st_mode), 0o600)
        self.assertNotIn(str(self.repo), (self.state / f'queue-{key}.json').read_text())
        # A second call appends and never removes; the long estimate names the first item beyond the lease.
        output = self.goal([item('release step', 'release-step', 400), item('tidy docs', 'other', 60)])
        queue, _ = self.queue()
        self.assertEqual((queue['revision'], len(queue['items'])), (2, 4))
        self.assertIn('Warning: the estimates exceed the minutes left on the lease from item 4 on', output)
        self.assertNotIn('the queue is short', output)
        self.goal([])  # an empty call changes nothing
        self.assertEqual(self.queue()[0]['revision'], 2)

    def test_goal_limits(self):
        self.start()
        synthetic = 'ghp_' + 'x' * 36
        for values in ([item(f'task {n}') for n in range(31)], [item('x' * 61)], [item('docs/readme')],
                       [item(synthetic)], [item(kind='deploy')], [item(minutes=0)], [item(minutes=481)],
                       [item(minutes=True)], [item(minutes='30')], [{'label': 'a', 'kind': 'fix'}],
                       {'label': 'a'}, [dict(item(), extra=1)]):
            with self.subTest(values=str(values)[:60]):
                self.goal(values, status=3)
        self.assertFalse(list(self.state.glob('queue-*.json')))
        self.goal([item(f'task {n}') for n in range(30)])
        self.goal([item('one more')], status=3)  # at most 30 open items in a queue
        outside = self.home / 'items.json'
        outside.write_text(json.dumps([item()]))
        self.assertEqual(self.invoke('goal', '--items-file', str(outside))[0], 3)

    def test_goal_refuses_without_a_live_lease(self):
        self.setup_config()
        self.goal([item()], status=3)  # no lease
        self.start()
        self.clock += 8 * 3600
        self.goal([item()], status=3)  # expired
        self.clock -= 8 * 3600
        self.setup_config(SETUP.replace('Claude Code', 'Codex'))
        self.goal([item()], status=3)  # setup changed
        self.setup_config()
        self.goal([item()])
        self.assertEqual(self.invoke('stop', '--all')[0], 0)
        self.assertFalse(list(self.state.glob('queue-*.json')))  # removed with the lease
        self.goal([item()], status=3)  # stopped

    def test_log_item_marks_and_refuses_unknown_numbers(self):
        self.start()
        self.goal([item(), item('second'), item('third')])
        self.assertEqual(self.invoke('log', '--kind', 'parked', '--item', '4')[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'parked', '--item', '0')[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'idle', '--item', '1')[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'action', '--done')[0], 3)  # --done needs --item
        self.assertEqual(self.invoke('log', '--kind', 'parked', '--item', '1', '--done')[0], 3)
        self.assertEqual(self.invoke('log', '--kind', 'parked', '--item', '1')[0], 0)
        self.assertEqual(self.invoke('log', '--kind', 'action', '--item', '2')[0], 0)  # no --done: still open
        self.assertEqual(self.invoke('log', '--kind', 'action', '--item', '2', '--done')[0], 0)
        self.assertEqual(self.invoke('log', '--kind', 'action', '--item', '2', '--done')[0], 3)  # already done
        queue, _ = self.queue()
        self.assertEqual([i['state'] for i in queue['items']], ['parked', 'done', 'open'])
        self.assertEqual(queue['revision'], 3)
        self.assertEqual([r.get('item') for r in self.records()], [1, 2, 2])

    def test_idle_needs_an_empty_queue(self):
        self.setup_config()
        self.assertEqual(self.invoke('log', '--kind', 'idle')[0], 3)  # no lease
        self.start()
        status, output = self.invoke('log', '--kind', 'idle')
        self.assertEqual(status, 3, output)
        self.assertIn('run goal first', output)
        self.goal([item(), item('second')])
        status, output = self.invoke('log', '--kind', 'idle')
        self.assertEqual(status, 3, output)
        self.assertIn('items are open: 1, 2', output)
        self.invoke('log', '--kind', 'parked', '--item', '1')
        self.invoke('log', '--kind', 'merge', '--item', '2', '--done')
        status, output = self.invoke('log', '--kind', 'idle', '--session', 'abc-123')
        self.assertEqual(status, 0, output)
        record = self.records()[-1]
        queue, key = self.queue()
        self.assertEqual((record['kind'], record['repository'], record['revision']), ('idle', key[:16], queue['revision']))
        self.assertEqual(record['session'], hashlib.sha256(b'abc-123').hexdigest()[:16])

    def test_idle_with_an_empty_goal_and_after_the_lease_ended(self):
        self.start()
        self.goal([])
        self.assertEqual(self.invoke('log', '--kind', 'idle')[0], 0)
        self.goal([item()])
        self.assertEqual(self.invoke('log', '--kind', 'idle')[0], 3)
        self.clock += 8 * 3600  # the lease has ended: idle is accepted with items open
        self.assertEqual(self.invoke('log', '--kind', 'idle')[0], 0)
        self.clock -= 8 * 3600
        self.assertEqual(self.invoke('stop', '--all')[0], 0)
        self.assertEqual(self.invoke('log', '--kind', 'idle')[0], 0)

    def test_plain_stop_is_refused_and_keeps_the_lease(self):
        ap = self.load()
        self.start()
        self.goal([item()])
        status, output = self.invoke('stop')
        self.assertEqual(status, 3, output)
        self.assertEqual(output, 'afk refused: ' + ap.STOP_REFUSED + '\n')
        self.assertIn('--kind idle', output)
        self.assertTrue((self.state / 'lease.json').exists())
        self.assertFalse((self.state / 'stop').exists())
        self.check(['git', 'status'])
        self.assertEqual(self.invoke('stop', '--all')[0], 0)
        self.assertFalse((self.state / 'lease.json').exists())
        self.assertFalse(list(self.state.glob('queue-*.json')))

    def test_a_new_lease_starts_with_no_queue(self):
        self.start()
        self.goal([item()])
        self.clock += 8 * 3600
        self.start()
        self.assertFalse(list(self.state.glob('queue-*.json')))

    def test_effective_names_project_settings(self):
        self.start()
        status, output = self.invoke('effective')
        self.assertEqual((status, output.splitlines()[1]), (0, 'Project settings: none'))
        store = load_store()
        found, ident = store.identity(self.repo)
        store.write_setting(self.repo, 'autopilot', {'default-branch': 'open'}, ident=ident)
        status, output = self.invoke('effective')
        self.assertEqual((status, output.splitlines()[1]), (0, 'Project settings: recorded'))
        self.cwd = self.home  # no repository
        status, output = self.invoke('effective')
        self.assertEqual((status, output.splitlines()[1]), (0, 'Project settings: none'))

    def test_goal_is_a_lease_command(self):
        self.assertIn('goal', self.load().LEASE_COMMANDS)


if __name__ == '__main__':
    unittest.main()
