"""Upgrade notes: closed schema, the shipped file, and the release test."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
NOTES = ROOT / 'skills/fnl-update/references/upgrades.json'
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('update_check_notes', ROOT / 'scripts/update_check.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)

VALID = {'versions': [{'version': '0.3.1', 'items': [
    {'id': '0.3.1/new-thing', 'kind': 'setup', 'text': 'A synthetic feature needs its own setup.',
     'setup': '/fnl-setup add thing', 'check': ['scripts/thing_check.py', 'state']},
    {'id': '0.3.1/old-name', 'kind': 'rename', 'text': 'The old command is renamed.', 'until': '0.4.0'},
]}]}


class NotesSchemaTest(unittest.TestCase):
    def test_valid_notes_parse_in_version_order(self):
        data = copy.deepcopy(VALID)
        data['versions'].insert(0, {'version': '0.3.2', 'items': [
            {'id': '0.3.2/later', 'kind': 'hook', 'text': 'A later hook needs trust.'}]})
        parsed = u.parse_notes(data)
        self.assertEqual([entry['version'] for entry in parsed], ['0.3.1', '0.3.2'])

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
            lambda d: item(d).update(setup='/fnl-setup add thing; rm'),
            lambda d: item(d).update(setup='fnl-setup add thing'),
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
        ]
        for number, edit in enumerate(cases):
            with self.subTest(case=number), self.assertRaises(ValueError):
                u.parse_notes(changed(edit))
        for bad in [[], None, 'x', {'versions': {}}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                u.parse_notes(bad)

    def test_shipped_notes_are_valid_and_hold_the_024_and_025_entries(self):
        parsed = u.parse_notes(json.loads(NOTES.read_text()))
        self.assertEqual([entry['version'] for entry in parsed], ['0.2.4', '0.2.5'])
        ids = [item['id'] for item in parsed[0]['items']]
        self.assertIn('0.2.4/checks-rename', ids)
        self.assertIn('0.2.4/checks-setup', ids)
        self.assertIn('0.2.4/ci-workflow', ids)
        self.assertIn('0.2.4/codex-hook-trust', ids)
        rename = next(item for item in parsed[0]['items'] if item['id'] == '0.2.4/checks-rename')
        self.assertEqual(rename['until'], '0.3.0')
        migrations = [item for item in parsed[1]['items'] if item['kind'] == 'migration']
        self.assertEqual(len(migrations), 1)
        self.assertIn('checks_setup.py migrate', migrations[0]['text'])
        self.assertIn('host.md', migrations[0]['text'])

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
