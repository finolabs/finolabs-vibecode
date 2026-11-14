"""Assignment matrix parser, validator and renderer: pure text in, values out."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'skills/setup/scripts/assignments.py'


def load():
    spec = importlib.util.spec_from_file_location('assignments_under_test', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load()
HEAD = '## Assignment matrix\n\n- Consent: yes (2026-11-09)\n- Judge: jev\n'
FULL = (HEAD
        + '- claude: levels 1-5; works on frontend, design, video, three-d; model claude-opus-5-5; roles none\n'
        + '- claudework: levels 3-5; works on frontend; model claude-opus-5-5\n'
        + '- codex: levels 1-4; works on image-generation, transcription; roles security-review\n'
        + '- antigravity: levels 1-3; roles code-review, navigator\n')


class ConstantsTest(unittest.TestCase):
    def test_closed_lists(self):
        self.assertEqual(A.HEADING, '## Assignment matrix')
        self.assertEqual(A.TYPES, ('frontend', 'design', 'video', 'three-d', 'image-generation', 'transcription'))
        self.assertEqual(A.ROLES, ('code-review', 'security-review', 'navigator', 'advisor'))

    def test_advisor_role_names_one_agent_at_most(self):
        m = A.parse(HEAD + '- claude: levels 1-5\n- codex: levels 1-5; roles security-review, advisor\n')
        self.assertEqual((m.state, m.roles), ('valid', {'security-review': 'codex', 'advisor': 'codex'}))
        m = A.parse(HEAD + '- claude: levels 1-5; roles advisor\n- codex: levels 1-5; roles advisor\n')
        self.assertEqual((m.state, m.problems), ('invalid', ['duplicate role']))
        values = {'consent': 'yes', 'date': '2026-11-09', 'judge': 'host', 'agents': {
            'claude': {'levels': (1, 5), 'works': [], 'model': None, 'roles': ['advisor']},
            'codex': {'levels': (1, 5), 'works': [], 'model': None, 'roles': ['advisor']}}}
        with self.assertRaises(ValueError):
            A.validate(values)
        values['agents']['codex']['roles'] = []
        self.assertIn('- claude: levels 1-5; roles advisor\n', A.render(values))


class ParseValidTest(unittest.TestCase):
    def test_full_example(self):
        m = A.parse('# Host\n\n' + FULL + '\n## Other\nkeep\n')
        self.assertEqual((m.state, m.problems), ('valid', []))
        self.assertEqual((m.consent, m.date, m.judge), ('yes', '2026-11-09', 'jev'))
        self.assertEqual(list(m.agents), ['claude', 'claudework', 'codex', 'antigravity'])
        self.assertEqual(m.agents['claude'], {'levels': (1, 5), 'works': ['frontend', 'design', 'video', 'three-d'],
                                              'model': 'claude-opus-5-5', 'models': [], 'roles': []})
        self.assertEqual(m.agents['antigravity'], {'levels': (1, 3), 'works': [], 'model': None, 'models': [],
                                                   'roles': ['code-review', 'navigator']})
        self.assertEqual(m.roles, {'security-review': 'codex', 'code-review': 'antigravity', 'navigator': 'antigravity'})

    def test_consent_no_and_host_judge_without_agents(self):
        m = A.parse('## Assignment matrix\n- Consent: no\n- Judge: host\n')
        self.assertEqual((m.state, m.consent, m.date, m.judge, dict(m.agents)), ('valid', 'no', '', 'host', {}))

    def test_crlf_text(self):
        m = A.parse(FULL.replace('\n', '\r\n'))
        self.assertEqual(m.state, 'valid')

    def test_absent_without_heading(self):
        for text in ('', '# Host\n## Agent levels\n- Consent: no\n', '## Assignment matrix extra\n- Consent: no\n'):
            with self.subTest(text=text):
                m = A.parse(text)
                self.assertEqual((m.state, m.problems, m.roles), ('absent', [], {}))
                self.assertIsNone(m.judge)

    def test_heading_inside_fence_is_ignored(self):
        text = '# Host\n```\n' + HEAD + '- claude: levels 1-5\n```\n~~~md\n## Assignment matrix\n~~~\n'
        self.assertEqual(A.parse(text).state, 'absent')

    def test_an_info_string_does_not_close_a_fence(self):
        text = '```\n## Assignment matrix\n```python\n## Assignment matrix\n- Consent: no\n- Judge: host\n```\n'
        self.assertEqual(A.parse(text).state, 'absent')

    def test_real_heading_after_a_closed_fence_is_found(self):
        self.assertEqual(A.parse('```\nx\n```\n' + FULL).state, 'valid')

    def test_section_ends_at_next_heading(self):
        self.assertEqual(A.parse(FULL + '## Next\n- junk line\n').state, 'valid')
        self.assertEqual(A.parse(FULL + '# Top\n- junk line\n').state, 'valid')


class ParseInvalidTest(unittest.TestCase):
    def reasons(self, body, head=HEAD):
        m = A.parse(head + body)
        self.assertEqual(m.state, 'invalid', body)
        self.assertEqual(m.roles, {})
        self.assertIsNone(m.judge)
        return m.problems

    def test_missing_or_malformed_consent(self):
        self.assertIn('missing consent', A.parse('## Assignment matrix\n- Judge: host\n').problems)
        for line in ('- Consent: maybe', '- Consent: yes', '- Consent: yes (2026-13-45)', '- Consent: yes (26-11-09)',
                     '- Consent: no (2026-11-09)', '- consent: no'):
            with self.subTest(line=line):
                m = A.parse(f'## Assignment matrix\n{line}\n- Judge: host\n')
                self.assertEqual(m.state, 'invalid')
                self.assertTrue(set(m.problems) & {'missing consent', 'bad consent', 'unknown key', 'unknown agent'})

    def test_duplicate_consent_and_judge(self):
        self.assertIn('duplicate consent', self.reasons('- Consent: no\n'))
        self.assertIn('duplicate judge', self.reasons('- Judge: host\n'))

    def test_missing_and_bad_judge(self):
        self.assertIn('missing judge', A.parse('## Assignment matrix\n- Consent: no\n').problems)
        self.assertIn('bad judge', A.parse('## Assignment matrix\n- Consent: no\n- Judge: other\n').problems)

    def test_unknown_key_and_agent(self):
        self.assertIn('unknown key', self.reasons('- Note: hello\n'))
        self.assertIn('unknown key', self.reasons('plain text\n'))
        self.assertIn('unknown agent', self.reasons('- gemini: levels 1-2\n'))
        self.assertIn('unknown agent', self.reasons('- claude_work: levels 1-2\n'.replace('_', '-')))

    def test_unknown_field_or_wrong_order(self):
        self.assertIn('unknown key', self.reasons('- claude: levels 1-2; colour red\n'))
        self.assertIn('unknown key', self.reasons('- claude: levels 1-2; model m1; works on design\n'))
        self.assertIn('unknown key', self.reasons('- claude: levels 1-2; roles navigator; model m1\n'))
        self.assertIn('unknown key', self.reasons('- claude: levels 1-2; works on design; works on video\n'))

    def test_bad_levels(self):
        for rest in ('levels 0-2', 'levels 3-6', 'levels 5-3', 'levels 3', 'levels 1-2-3', 'works on design', 'levels 1 - 2', ''):
            with self.subTest(rest=rest):
                self.assertIn('bad levels', self.reasons(f'- claude: {rest}\n'))

    def test_unknown_and_duplicate_and_too_many_types(self):
        self.assertIn('unknown type', self.reasons('- claude: levels 1-5; works on backend\n'))
        self.assertIn('unknown type', self.reasons('- claude: levels 1-5; works on frontend,design\n'))
        self.assertIn('duplicate type', self.reasons('- claude: levels 1-5; works on design, design\n'))
        self.assertIn('too many types', self.reasons('- claude: levels 1-5; works on frontend, design, video, three-d, transcription\n'))
        self.assertNotIn('too many types', A.parse(HEAD + '- claude: levels 1-5; works on frontend, design, video, three-d\n').problems)

    def test_bad_model(self):
        for model in ('-x', 'a b', 'a/b', 'x' * 65, 'é'):
            with self.subTest(model=model):
                self.assertIn('bad model', self.reasons(f'- claude: levels 1-5; model {model}\n'))
        self.assertEqual(A.parse(HEAD + '- claude: levels 1-5; model ' + 'x' * 64 + '\n').state, 'valid')

    def test_unknown_and_duplicate_roles(self):
        self.assertIn('unknown role', self.reasons('- claude: levels 1-5; roles judge\n'))
        self.assertIn('unknown role', self.reasons('- claude: levels 1-5; roles none, navigator\n'))
        self.assertIn('duplicate role', self.reasons('- claude: levels 1-5; roles navigator, navigator\n'))
        self.assertIn('duplicate role', self.reasons('- claude: levels 1-5; roles navigator\n- codex: levels 1-5; roles navigator\n'))

    def test_duplicate_agent_line_and_limit(self):
        self.assertIn('duplicate agent', self.reasons('- claude: levels 1-5\n- claude: levels 1-2\n'))
        lines = ''.join(f'- claudex{i}: levels 1-5\n' for i in range(9))
        self.assertIn('too many agents', self.reasons(lines))
        lines = ''.join(f'- claudex{i}: levels 1-5\n' for i in range(8))
        self.assertEqual(A.parse(HEAD + lines).state, 'valid')

    def test_duplicate_heading(self):
        m = A.parse(FULL + '## Assignment matrix\n- Consent: no\n- Judge: host\n')
        self.assertEqual((m.state, m.problems), ('invalid', ['duplicate section']))

    def test_one_real_and_one_fenced_heading_is_not_duplicate(self):
        self.assertEqual(A.parse(FULL + '## Next\n```\n## Assignment matrix\n```\n').state, 'valid')

    def test_unclosed_fence_after_heading_is_invalid_and_before_is_absent(self):
        self.assertEqual(A.parse(FULL + '```\nopen\n').state, 'invalid')
        self.assertEqual(A.parse('```\n' + FULL).state, 'absent')

    def test_never_repairs(self):
        m = A.parse(HEAD + '- claude: levels 1-5; works on design\n- claude: levels 1-2\n')
        self.assertEqual(m.state, 'invalid')
        self.assertEqual(m.roles, {})


class DeclinedConsentTest(unittest.TestCase):
    def test_declined_consent_cannot_carry_assignments_or_the_judge_call(self):
        for lines in ('- Judge: host\n- codex: levels 1-4; roles code-review\n', '- Judge: jev\n'):
            m = A.parse('## Assignment matrix\n- Consent: no\n' + lines)
            self.assertEqual(m.state, 'invalid')
            self.assertIn('no consent', m.problems)
            self.assertIsNone(m.judge)
            self.assertEqual(m.roles, {})

    def test_declined_consent_alone_is_a_valid_record(self):
        self.assertEqual(A.parse('## Assignment matrix\n- Consent: no\n- Judge: host\n').state, 'valid')


class NoEchoAndNoRaiseTest(unittest.TestCase):
    def test_parse_never_raises_and_never_echoes(self):
        secret = 'zzSECRETzz'
        texts = [f'## Assignment matrix\n- Consent: yes ({secret})\n- {secret}: levels 1-2\n- claude: levels 1-5; model {secret}/x\n'
                 f'- claude: levels 1-5; works on {secret}\n- codex: levels 1-5; roles {secret}\n- Judge: {secret}\n- {secret}\n',
                 '\x00\xff\n## Assignment matrix\n\x00', '## Assignment matrix\n' + '- x\n' * 5000]
        for text in texts:
            m = A.parse(text)
            self.assertEqual(m.state, 'invalid')
            blob = repr((m.problems, m.agents, m.roles, m.judge, m.consent, m.date))
            self.assertNotIn(secret, blob)
            for reason in m.problems:
                self.assertRegex(reason, r'^[a-z ]{3,30}$')
        for value in (None, 5, b'## Assignment matrix', ['x']):
            self.assertEqual(A.parse(value).state, 'invalid')

    def test_validate_error_never_echoes(self):
        values = {'consent': 'yes', 'date': '2026-11-09', 'judge': 'host',
                  'agents': {'claude': {'levels': (1, 5), 'works': ['zzSECRETzz'], 'model': None, 'roles': []}}}
        with self.assertRaises(ValueError) as ctx:
            A.validate(values)
        self.assertEqual(ctx.exception.args, ('values',))


def good():
    return {'consent': 'yes', 'date': '2026-11-09', 'judge': 'jev', 'agents': {
        'claude': {'levels': (1, 5), 'works': ['frontend', 'design'], 'model': 'claude-opus-5-5', 'roles': []},
        'codex': {'levels': [1, 4], 'works': [], 'model': None, 'roles': ['security-review']}}}


class ValidateRenderTest(unittest.TestCase):
    def test_good_values_pass(self):
        A.validate(good())

    def test_each_violation_raises_values(self):
        def mutate(fn):
            v = good()
            fn(v)
            return v
        cases = {
            'extra key': lambda v: v.update(extra=1),
            'consent': lambda v: v.update(consent='maybe'),
            'date': lambda v: v.update(date='2026-02-31'),
            'date for no': lambda v: v.update(consent='no'),
            'judge': lambda v: v.update(judge='x'),
            'agent name': lambda v: v['agents'].update({'gemini': dict(v['agents']['codex'], roles=[])}),
            'agent entry keys': lambda v: v['agents']['claude'].update(extra=1),
            'levels order': lambda v: v['agents']['claude'].update(levels=(4, 2)),
            'levels range': lambda v: v['agents']['claude'].update(levels=(0, 2)),
            'levels bool': lambda v: v['agents']['claude'].update(levels=(True, 2)),
            'type': lambda v: v['agents']['claude'].update(works=['backend']),
            'type dup': lambda v: v['agents']['claude'].update(works=['design', 'design']),
            'type many': lambda v: v['agents']['claude'].update(works=list(A.TYPES[:5])),
            'model': lambda v: v['agents']['claude'].update(model='a b'),
            'role': lambda v: v['agents']['claude'].update(roles=['judge']),
            'role dup line': lambda v: v['agents']['claude'].update(roles=['navigator', 'navigator']),
            'role dup agents': lambda v: v['agents']['claude'].update(roles=['security-review']),
            'too many': lambda v: v['agents'].update({f'claudex{i}': dict(v['agents']['claude'], roles=[]) for i in range(8)}),
            'not dict': lambda v: v.update(agents=[]),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError) as ctx:
                    A.validate(mutate(fn))
                self.assertEqual(ctx.exception.args, ('values',))
        for bad in (None, [], 'x', {}):
            with self.assertRaises(ValueError):
                A.validate(bad)

    def test_render_canonical_text(self):
        self.assertEqual(A.render(good()), (
            '## Assignment matrix\n\n- Consent: yes (2026-11-09)\n- Judge: jev\n'
            '- claude: levels 1-5; works on frontend, design; model claude-opus-5-5\n'
            '- codex: levels 1-4; roles security-review\n\n'))

    def test_render_refuses_invalid_values(self):
        with self.assertRaises(ValueError):
            A.render({'consent': 'x'})

    def test_round_trip(self):
        for values in (good(), {'consent': 'no', 'date': '', 'judge': 'host', 'agents': {}}):
            text = A.render(values)
            m = A.parse('# Host\n\n' + text + '## After\nx\n')
            self.assertEqual(m.state, 'valid', m.problems)
            self.assertEqual(A.render(m.to_values()), text)
            A.validate(m.to_values())

    def test_round_trip_of_full_example(self):
        m = A.parse(FULL)
        self.assertEqual(A.parse(A.render(m.to_values())).to_values(), m.to_values())


OWNER_LINE = ('- antigravity: levels 1-5; works on design, video, image-generation, transcription; models '
              'gemini-4-argon-high then gemini-3.8-flash-high for security-review | gemini-4-hydrogen-high for design, '
              'video, three-d, image-generation, levels 4-5 | gemini-4-argon-high for implement, levels 4-5 | '
              'gemini-3.8-flash-high for code-review | gemini-3.8-flash-high for levels 3-4; roles security-review, '
              'navigator')
OWNER = '## Assignment matrix\n\n- Consent: yes (2026-11-14)\n- Judge: host\n' + OWNER_LINE + '\n\n'


def with_models(field):
    return HEAD + '- antigravity: levels 1-5; model m1; ' + field + '\n'


class ModelsFieldTest(unittest.TestCase):
    """docs/specs/matrix-models.md: the `models` field."""

    def test_owner_example_parses_and_renders_unchanged(self):
        m = A.parse(OWNER)
        self.assertEqual(m.state, 'valid', m.problems)
        rules = m.agents['antigravity']['models']
        self.assertEqual([(r['model'], r['then']) for r in rules], [
            ('gemini-4-argon-high', 'gemini-3.8-flash-high'), ('gemini-4-hydrogen-high', None),
            ('gemini-4-argon-high', None), ('gemini-3.8-flash-high', None), ('gemini-3.8-flash-high', None)])
        self.assertEqual(rules[1]['for'], ['design', 'video', 'three-d', 'image-generation', 'levels 4-5'])
        self.assertEqual(A.render(m.to_values()), OWNER)
        A.validate(m.to_values())

    def test_each_parse_problem_invalidates_the_whole_matrix(self):
        nine = ' | '.join(f'm{n} for code-review' for n in range(9))
        cases = {
            'models m2 for reviewing': 'unknown selector',
            'models m2 for levels 0-6': 'unknown selector',
            'models m2 for levels 5-3': 'bad levels',
            'models m_2 for implement': 'bad model',
            'models m2 then m_3 for implement': 'bad model',
            'models m2 implement': 'rule without for',
            'models m2 for implement |  | m3 for advisor': 'empty rule',
            'models m2 for implement, ': 'empty selector',
            'models m2 for implement; models m3 for advisor': 'duplicate models',
            'models ' + nine: 'too many rules',
            'models m2 then m3 then m4 for implement': 'second then',
        }
        for field, reason in cases.items():
            with self.subTest(field=field):
                m = A.parse(with_models(field))
                self.assertEqual(m.state, 'invalid')
                self.assertIn(reason, m.problems)
                self.assertEqual(m.roles, {})
                self.assertIsNone(m.judge)

    def test_models_field_order(self):
        self.assertIn('unknown key', A.parse(HEAD + '- codex: levels 1-5; roles navigator; models m for advisor\n').problems)
        self.assertEqual(A.parse(HEAD + '- codex: levels 1-5; models m for advisor; roles navigator\n').state, 'valid')

    def test_values_refuse_bad_rules(self):
        def entry(rules):
            v = good()
            v['agents']['codex']['models'] = rules
            return v
        A.validate(entry([{'model': 'm', 'then': None, 'for': ['advisor']}]))
        for rules in ([{'model': 'm', 'then': None, 'for': []}], [{'model': 'm', 'then': None, 'for': ['x']}],
                      [{'model': 'm', 'for': ['advisor']}], [{'model': 'm', 'then': None, 'for': ['advisor']}] * 9):
            with self.assertRaises(ValueError):
                A.validate(entry(rules))

    def test_choose_model_first_match_and_kindless_rules(self):
        entry = A.parse(OWNER).agents['antigravity']
        choose = A.choose_model
        self.assertEqual(choose(entry, 'security-review', None, 3)[:2], ('gemini-4-argon-high', 'gemini-3.8-flash-high'))
        self.assertEqual(choose(entry, 'implement', None, 4)[0], 'gemini-4-argon-high')
        self.assertEqual(choose(entry, 'implement', 'design', 4)[0], 'gemini-4-hydrogen-high')
        self.assertEqual(choose(entry, 'code-review', None, 2)[0], 'gemini-3.8-flash-high')
        self.assertEqual(choose(entry, 'implement', None, 3)[0], 'gemini-3.8-flash-high')
        self.assertEqual(choose(entry, 'advisor', None, 3), (None, None, False))
        self.assertEqual(choose(entry, 'implement', None, 2), (None, None, False))
        self.assertEqual(choose(entry, 'implement', None, None), (None, None, False))

    def test_pools(self):
        self.assertEqual([A.pool(m) for m in ('gemini-4-argon-high', 'gemini-4-hydrogen-high', 'gemini-3.8-flash-high',
                                              'claude-sonnet-5', 'gpt-6', 'other-model')],
                         ['argon', 'gemini', 'gemini', 'claude-gpt', 'claude-gpt', 'other'])


class PureModuleTest(unittest.TestCase):
    def test_imports_nothing_with_side_effects(self):
        text = PATH.read_text()
        for word in ('subprocess', 'import os', 'os.environ', 'open(', 'socket', 'urllib', 'import pwd', 'fcntl'):
            self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()
