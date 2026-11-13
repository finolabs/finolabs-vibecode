"""Upgrade notes: closed schema, the shipped file, and the release test."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / 'skills/update/references/upgrades.json'
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('update_check_notes', ROOT / 'scripts/update_check.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

VALID = {'versions': [{'version': '0.3.1', 'items': [
    {'id': '0.3.1/new-thing', 'kind': 'setup', 'text': 'A synthetic feature needs its own setup.',
     'setup': '/setup add thing', 'check': ['scripts/thing_check.py', 'state']},
    {'id': '0.3.1/old-name', 'kind': 'rename', 'text': 'The old command is renamed.', 'until': '0.4.0'},
]}]}


class NotesSchemaTest(unittest.TestCase):
    def test_valid_notes_parse_in_version_order(self):
        data = copy.deepcopy(VALID)
        data['versions'].insert(0, {'version': '0.3.2', 'items': [
            {'id': '0.3.2/later', 'kind': 'hook', 'text': 'A later hook needs trust.'},
            {'id': '0.3.2/news', 'kind': 'info', 'text': 'Something changed that needs no step.'}]})
        parsed = u.parse_notes(data)
        self.assertEqual([entry['version'] for entry in parsed], ['0.3.1', '0.3.2'])
        # A check may run in the user's current repository, never without a check.
        data['versions'][1]['items'][0]['where'] = 'repository'
        self.assertEqual(u.parse_notes(data)[0]['items'][0]['where'], 'repository')

    def test_unknown_keys_and_bad_values_are_refused(self):
        def changed(edit):
            data = copy.deepcopy(VALID)
            edit(data)
            return data
        item = lambda d: d['versions'][0]['items'][0]
        cases = [
            lambda d: d.update(extra=1),
            lambda d: d['versions'][0].update(extra=1),
            lambda d: item(d).update(extra=1),
            lambda d: item(d).update(kind='other'),
            lambda d: item(d).update(id='0.3.2/new-thing'),
            lambda d: item(d).update(id='0.3.1/Bad_Slug'),
            lambda d: item(d).update(id='0.3.1/' + 'a' * 41),
            lambda d: item(d).update(text='x' * 201),
            lambda d: item(d).update(text='two\nlines'),
            lambda d: item(d).update(text=''),
            lambda d: item(d).update(setup='/setup add thing; rm'),
            lambda d: item(d).update(setup='setup add thing'),
            lambda d: item(d).update(check='scripts/thing_check.py'),
            lambda d: item(d).update(check=[]),
            lambda d: item(d).update(check=['/abs/thing.py']),
            lambda d: item(d).update(check=['../thing.py']),
            lambda d: item(d).update(check=['sh', '-c', 'x']),
            lambda d: item(d).update(check=['scripts/thing_check.py', '$(id)']),
            lambda d: item(d).update(until='0.4.0-dev'),
            lambda d: d['versions'][0].update(version='0.3.1-dev'),
            lambda d: d['versions'][0].update(items=[]),
            lambda d: d['versions'].append(copy.deepcopy(d['versions'][0])),
            lambda d: d['versions'][0]['items'].append(copy.deepcopy(item(d))),
            lambda d: item(d).pop('text'),
            lambda d: item(d).update(where='home'),
            lambda d: item(d).update(where=True),
            lambda d: d['versions'][0]['items'][1].update(where='repository'),
        ]
        for number, edit in enumerate(cases):
            with self.subTest(case=number), self.assertRaises(ValueError):
                u.parse_notes(changed(edit))
        for bad in [[], None, 'x', {'versions': {}}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                u.parse_notes(bad)

    def test_shipped_notes_backfill_020_to_023_with_setup_steps_and_checks(self):
        parsed = u.parse_notes(json.loads(NOTES.read_text()))
        self.assertEqual([entry['version'] for entry in parsed], ['0.2.0', '0.2.1', '0.2.2', '0.2.3', '0.2.4', '0.2.5'])
        items = {item['id']: item for entry in parsed for item in entry['items']}
        state = 'skills/setup/scripts/upgrade_state.py'
        expected = {
            '0.2.0/codex-hook-trust': ('hook', None, None),
            '0.2.0/context-reading': ('setup', '/setup add compaction', None),
            '0.2.0/removed-skills': ('removed', None, None),
            '0.2.1/codex-hook-trust': ('hook', None, None),
            '0.2.1/parallel-limits': ('setup', '/setup add delegation', [state, 'no-parallel-lines']),
            '0.2.1/away-setup': ('setup', '/setup add afk', [state, 'afk']),
            '0.2.2/agent-levels': ('setup', '/setup add delegation', [state, 'levels']),
            '0.2.3/matrix-migrate': ('migration', '/setup add delegation', [state, 'matrix']),
            '0.2.3/help-rename': ('rename', None, None),
            '0.2.3/away-decisions': ('setup', '/setup add afk', [state, 'afk-decisions']),
            '0.2.3/question-gate-trust': ('hook', None, None),
            '0.2.3/codex-hook-trust': ('hook', None, None),
            '0.2.4/checks-setup': ('setup', '/setup add checks', [state, 'repo-checks']),
            '0.2.5/checks-store': ('setup', '/setup add checks', [state, 'no-checks-section']),
            '0.2.5/parallel-settings': ('setup', '/setup add delegation', [state, 'no-project-settings']),
            '0.2.5/project-settings': ('setup', '/setup add project', [state, 'no-project-settings', 'no-global-lines']),
            '0.2.5/project-labels': ('setup', '/setup add project', [state, 'no-project-labels']),
            '0.2.5/codex-hook-trust': ('hook', None, None),
            '0.2.5/quota-repin': ('setup', '/setup add quota', None),
            '0.2.5/context-probe': ('setup', '/setup add quota', None),
            '0.2.5/worktree-sweep': ('info', None, None),
            '0.2.5/afk-goal': ('info', None, None),
            '0.2.5/main-checkout': ('info', None, None),
            '0.2.5/full-names': ('info', None, None),
            '0.2.5/afk-section': ('setup', '/setup add afk', [state, 'afk-section']),
            '0.2.5/tidy-rename': ('info', None, None),
        }
        for ident, (kind, setup, check) in expected.items():
            with self.subTest(item=ident):
                item = items[ident]
                self.assertEqual((item['kind'], item.get('setup'), item.get('check')), (kind, setup, check))
                # Every check script exists in the plugin; only the repository check runs in the user's folder.
                if check:
                    self.assertTrue((ROOT / check[0]).is_file())
                self.assertEqual(item.get('where'), 'repository' if ident == '0.2.4/checks-setup' else None)
        for ident in ('0.2.0/codex-hook-trust', '0.2.1/codex-hook-trust', '0.2.3/codex-hook-trust', '0.2.5/codex-hook-trust'):
            self.assertIn('/hooks', items[ident]['text'])
        for phrase in ('## Limits', 'no longer read', 'each repository', 'by hand'):
            self.assertIn(phrase, items['0.2.1/parallel-limits']['text'])
        self.assertIn('matrix_setup.py migrate', items['0.2.3/matrix-migrate']['text'])
        self.assertIn('help', items['0.2.3/help-rename']['text'])
        for phrase in ('Claude Code', 'Codex', 'update'):
            self.assertIn(phrase, items['0.2.5/quota-repin']['text'])
        self.assertIn('/finolabs-vibecode:help', items['0.2.5/full-names']['text'])
        self.assertIn('/finolabs-vibecode:status', items['0.2.5/full-names']['text'])
        self.assertIn('/goal', items['0.2.5/afk-goal']['text'])
        self.assertIn('/loop', items['0.2.5/afk-goal']['text'])
        # Superseded steps (the 0.2.0 Limits lines and Agent roles) are not offered again.
        self.assertFalse([i for i in items if i.startswith('0.2.0/') and ('roles' in i or 'limits' in i)])

    def test_shipped_notes_are_valid_and_hold_the_024_and_025_entries(self):
        parsed = u.parse_notes(json.loads(NOTES.read_text()))[-2:]
        self.assertEqual([entry['version'] for entry in parsed], ['0.2.4', '0.2.5'])
        ids = [item['id'] for item in parsed[0]['items']]
        self.assertIn('0.2.4/checks-rename', ids)
        self.assertIn('0.2.4/checks-setup', ids)
        self.assertIn('0.2.4/ci-workflow', ids)
        self.assertIn('0.2.4/codex-hook-trust', ids)
        rename = next(item for item in parsed[0]['items'] if item['id'] == '0.2.4/checks-rename')
        self.assertEqual(rename['until'], '0.3.0')
        self.assertEqual([item['kind'] for item in parsed[1]['items']][:5], ['setup', 'setup', 'setup', 'setup', 'rename'])
        store = parsed[1]['items'][0]
        self.assertEqual(store['id'], '0.2.5/checks-store')
        self.assertEqual(store['setup'], '/setup add checks')
        for phrase in ('0.2.4', 'no longer read', 'each repository', '## Checks', 'host.md', 'by hand'):
            self.assertIn(phrase, store['text'])
        # Parallel limits and caps are set again before the old section is deleted.
        parallel, settings, labels, names = parsed[1]['items'][1:5]
        # Skills lost the fnl- prefix. The aliases are user-only, so a file that tells the model to
        # invoke an old name no longer loads it: typed names work, files need the new names.
        self.assertEqual(names['id'], '0.2.5/skill-names')
        self.assertNotIn('setup', names)
        for phrase in ('fnl- prefix', 'typed', 'instruction files', 'new names', '/setup check'):
            self.assertIn(phrase, names['text'])
        self.assertNotIn('keep working through the aliases', names['text'])
        self.assertEqual((parallel['id'], parallel['setup']), ('0.2.5/parallel-settings', '/setup add delegation'))
        for phrase in ('no longer read', 'host.md', 'each repository', 'parallel', 'caps', 'before', '## Project settings'):
            self.assertIn(phrase, parallel['text'])
        self.assertEqual((settings['id'], labels['id']), ('0.2.5/project-settings', '0.2.5/project-labels'))
        for phrase in ('no longer read', 'host.md', 'each repository', '## Project settings', 'Ledger project:',
                       'Task file:', 'by hand'):
            self.assertIn(phrase, settings['text'])
        for phrase in ('no longer read', 'host.md', 'each repository', '## Project labels', 'by hand'):
            self.assertIn(phrase, labels['text'])
        for item in (store, parallel, settings, labels):
            self.assertNotIn('migrate', item['text'])

    def test_025_names_the_afk_section_step_and_the_tidy_rename(self):
        items = {item['id']: item for entry in u.parse_notes(json.loads(NOTES.read_text()))
                 for item in entry['items']}
        afk = items['0.2.5/afk-section']
        # Modeled on checks-store: the old section is not read, setup runs again, the user deletes it by hand.
        self.assertEqual((afk['kind'], afk['setup'], afk['check']),
                         ('setup', '/setup add afk', ['skills/setup/scripts/upgrade_state.py', 'afk-section']))
        self.assertTrue((ROOT / afk['check'][0]).is_file())
        for phrase in ('/afk', '## Autopilot', 'host.md', 'no longer read', '/setup add afk', 'by hand'):
            self.assertIn(phrase, afk['text'])
        tidy = items['0.2.5/tidy-rename']
        self.assertEqual(tidy['kind'], 'info')
        self.assertNotIn('setup', tidy)
        for phrase in ('session-hygiene', 'tidy', 'typed', 'instruction files', '/setup check'):
            self.assertIn(phrase, tidy['text'])

    def test_release_version_needs_an_entry(self):
        notes = u.parse_notes(json.loads(NOTES.read_text()))
        released = {entry['version'] for entry in notes}
        self.assertFalse(u.missing_release_entry('0.2.4-dev', released))
        self.assertFalse(u.missing_release_entry('0.2.4', released))
        self.assertFalse(u.missing_release_entry('0.2.5', released))
        self.assertTrue(u.missing_release_entry('0.2.6', released))
        self.assertFalse(u.missing_release_entry('0.2.5-dev', released))
        manifest = json.loads((ROOT / '.claude-plugin/plugin.json').read_text())['version']
        self.assertFalse(u.missing_release_entry(manifest, released),
                         'a released manifest version needs an entry in upgrades.json')


if __name__ == '__main__':
    unittest.main()
