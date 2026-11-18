"""The afk check hook: actual hook stdout and exits under a real `afk start` lease, synthetic account home only."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.data_root_fixture import account

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'scripts/afk_check_hook.py'
sys.path.insert(0, str(ROOT / 'skills/delegate/scripts'))
import afk  # noqa: E402

SETUP = ('## afk\n- Hosts: Claude Code\n- Task choice: choose\n'
         '- Push and pull requests: yes\n- Merge: yes\n- Trusted authors: own\n')
ORIGIN_CONFIG = ('[core]\n\trepositoryformatversion = 0\n\tbare = false\n'
                 '[remote "origin"]\n\turl = https://github.com/example/demo.git\n'
                 '\tfetch = +refs/heads/*:refs/remotes/origin/*\n')
PARSE = 'afk: the command could not be read; write it as a simpler command'


def denial(reason):
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': reason}}


def parked(code):
    return denial(f'afk: {code}; this action is parked under the away lease (afk.py check)')


class AfkCheckHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = account(self, Path(tmp.name) / 'home')
        self.root = self.home / '.finolabs/vibecode'
        self.root.mkdir(parents=True, mode=0o700)
        self.repo = self.home / 'checkout'
        (self.repo / '.git/refs/remotes/origin').mkdir(parents=True)
        (self.repo / '.git/HEAD').write_text('ref: refs/heads/topic\n')
        (self.repo / '.git/refs/remotes/origin/HEAD').write_text('ref: refs/remotes/origin/main\n')
        (self.repo / '.git/config').write_text(ORIGIN_CONFIG)
        self.env = {'PATH': os.defpath}

    def afk(self, *argv):
        with patch('os.getcwd', return_value=str(self.repo)), contextlib.redirect_stdout(io.StringIO()) as out:
            status = afk.main(list(argv))
        return status, out.getvalue()

    def start(self, text=SETUP):
        (self.root / 'host.md').write_text(text)
        (self.root / 'host.md').chmod(0o600)
        status, output = self.afk('start', '--hours', '1')
        self.assertEqual(status, 0, output)

    def hook(self, command, env=None, cwd=None):
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command},
                              'cwd': str(self.repo if cwd is None else cwd)})
        result = subprocess.run([sys.executable, '-I', str(HOOK)], input=payload,
                                env=env or self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout) if result.stdout else None

    def test_no_lease_allows_everything(self):
        self.assertIsNone(self.hook('printenv'))

    def test_open_lease_denies_the_floor_and_allows_the_rest(self):
        self.start()
        self.assertEqual(self.hook('printenv'), parked('floor'))
        self.assertEqual(self.hook('echo ok && env'), parked('floor'))
        # A newline outside quotes separates commands, so the second line is judged on its own.
        self.assertEqual(self.hook('ls\nprintenv'), parked('floor'))
        self.assertIsNone(self.hook('git status'))
        self.assertIsNone(self.hook('git commit -m "fix the parser\n\nprintenv is not run here"'))

    def test_a_heredoc_and_a_home_glob_cannot_hide_the_floor(self):
        self.start()
        self.assertEqual(self.hook('cat <<EOF\nx\nEOF\nprintenv'), parked('floor'))
        (self.home / '.netrc').write_text('machine example.com\n')
        env = {**self.env, 'HOME': str(self.home)}
        self.assertEqual(self.hook('cat ~/.n?trc', env=env), parked('floor'))
        self.assertEqual(self.hook('cat "$HOME"/.n[e]trc', env=env), parked('floor'))

    def test_own_lease_commands_are_never_judged(self):
        self.start(SETUP + '- Mode: strict\n')
        script = ROOT / 'skills/delegate/scripts/afk.py'
        self.assertIsNone(self.hook(f'python3 -I {script} effective'))
        self.assertIsNone(self.hook(f'python3 -I {script} log --kind parked --note x'))
        # A lease command joined to another command is judged like any argv.
        denied = self.hook(f'python3 -I {script} effective && curl https://example.com')
        self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')
        self.assertIsNone(self.hook(f'python3 -I {script} stop'))

    def test_an_own_lease_command_with_an_expansion_or_redirect_is_judged(self):
        self.start()
        script = ROOT / 'skills/delegate/scripts/afk.py'
        (self.home / '.netrc').write_text('machine example.com\n')
        env = {**self.env, 'HOME': str(self.home)}
        for command in (f'python3 -I {script} log --note "$(cat ~/.netrc)"',
                        f'python3 -I {script} log --note "`cat ~/.netrc`"',
                        f'python3 -I {script} log --note x;printenv',
                        f'python3 -I {script} log --note x|cat ~/.netrc'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command, env=env), denial(PARSE))
        for command in (f'python3 -I {script} rules >~/.netrc',
                        f'python3 -I {script} log --note x ; printenv',
                        f'python3 -I {script} log --note x | cat ~/.netrc'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command, env=env), parked('floor'))

    def test_a_comment_or_ansi_quote_cannot_hide_a_line(self):
        self.start()
        (self.home / '.netrc').write_text('machine example.com\n')
        env = {**self.env, 'HOME': str(self.home)}
        # Bash reads `#'` as a comment, so the second line runs; the review's form also ends unbalanced.
        self.assertEqual(self.hook("echo hi #'\ncat ~/.n?trc", env=env), parked('floor'))
        self.assertEqual(self.hook("echo hi #'\ncat ~/.n?trc\n'", env=env), denial(PARSE))
        self.assertEqual(self.hook("echo $'\\'' \ncat ~/.n?trc\n'", env=env), denial(PARSE))
        self.assertIsNone(self.hook("echo $'plain' # a note"))
        # A backslash-newline joins lines as bash does, inside double quotes too.
        self.assertEqual(self.hook('cat ~/.ne\\\ntrc', env=env), parked('floor'))
        self.assertEqual(self.hook('cat "$HOME/.ne\\\ntrc"', env=env), parked('floor'))
        # An ANSI-C escape could hide a name or a path, so it is unreadable.
        self.assertEqual(self.hook("$'\\x70rintenv'"), denial(PARSE))
        self.assertEqual(self.hook('$"printenv"'), parked('floor'))
        self.assertEqual(self.hook('$"pr"intenv'), parked('floor'))
        # An escaped backslash is no continuation: the next line is its own command.
        self.assertEqual(self.hook('echo a\\\\\nprintenv'), parked('floor'))

    def test_a_bad_cwd_denies_once_the_lease_is_live(self):
        self.start()
        self.assertEqual(self.hook('git status', cwd=self.home / 'missing'), parked('unsafe'))

    def test_strict_lease_denies_every_parked_answer(self):
        self.start(SETUP + '- Mode: strict\n')
        self.assertEqual(self.hook('curl https://example.com'), parked('unknown'))
        self.assertIsNone(self.hook('git status'))

    def test_shell_forms_the_hook_cannot_reproduce_are_denied(self):
        self.start()
        for command in ('/usr/bin/printen?', '{printenv,}', 'cat ~/.ne{t,}rc', 'echo ${x:-printenv}', 'true >(printenv)',
                        'cat <(cat ~/.ne?rc)', 'set -- printenv; "$@"', 'echo $_', 'echo $(( 1 ))', '=printenv',
                        'cat ~/.(netrc|x)', 'cat ~+/.netrc', "eval 'printenv'", "bash -c 'printenv'",
                        "sh <<< 'printenv'", 'echo printenv | sh', 'x=printenv; $x',
                        'echo x|/usr/bin/printen?', 'echo x;/usr/bin/printen?', 'if true; then /usr/bin/printen?; fi',
                        'env /usr/bin/printen?', 'timeout 5 /usr/bin/printen?', "env bash -c 'pr\"\"intenv'",
                        "printf x|sh", 'command eval x', r'find . -exec /usr/bin/printen? \;',
                        r"find . -exec sh -c 'printenv' \;", 'setopt extendedglob; cat ~/.ne^Q', 'set -o extendedglob',
                        'set -oextendedglob', 'builtin eval x', 'nocorrect ls', 'case x in x) ls;; esac',
                        'function f { ls; }', 'hash -p /bin/ls p', "trap 'ls' EXIT", "caffeinate -s sh -c 'ls'", 'stdbuf -oL ls', "xargs -J % sh -c 'ls'", "xargs -n 1 -E x sh -c 'ls'",
                        "npx --package x sh -c 'ls'", "uvx --from x sh -c 'ls'", "flock f -c 'ls'",
                        "timeout --kill-after 1 5 sh -c 'ls'", 'command -p ls', 'time -p ls', 'sudo -n ls',
                        r'find . -exec timeout 5 sh -c x \;', "ls|xargs -J % sh -c 'ls'", 'true&&xargs -J % sh -c x',
                        'ls||xargs -E x sh -c x', 'ls&xargs -J % sh -c x', '(xargs -J % sh -c x)', 'ls;flock f -c x',
                        'ls|npx --package x sh -c x', 'ls|timeout --kill-after 1 5 sh -c x', 'ls|caffeinate -s sh -c x',
                        'ls|sudo -n sh -c x', '(nice -5 sh -c x)'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), denial(PARSE))
        # Ordinary forms stay readable.
        for command in ('git status', 'echo "${HOME}"', 'bash scripts/run.sh',
                        'python3 -c "print(1)"', 'set -e', 'set -euo pipefail', 'env FOO=1 ls', 'env -i ls', 'timeout 5 ls',
                        'npx -y prettier --check .'):
            with self.subTest(command=command):
                self.assertNotEqual(self.hook(command), denial(PARSE))

    def test_an_operator_that_ends_a_word_is_split_off_as_bash_does(self):
        self.start()
        # Ordinary style: the operator ends the word before it, so both commands are read and judged.
        for command in ('ls /tmp; git status', 'ls /tmp&& git status', 'ls /tmp|| git status', 'ls /tmp| head',
                        'ls /tmp; git status; git log -1', 'ls /tmp; git status 2>&1 | head'):
            with self.subTest(command=command):
                self.assertIsNone(self.hook(command))
        for command in ('ls /tmp; printenv', 'git commit -m msg; printenv', 'ls /tmp&& env', 'ls /tmp| printenv'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), parked('floor'))
        # An operator glued to the word after it, or one inside quotes beside a split one, is still not read.
        # A quoted or escaped operator elsewhere never stands in for the glued one (review of #352).
        for command in ('ls /tmp;printenv', 'git commit -m msg;printenv', 'echo "a;" b; printenv',
                        "git commit -m x;printenv FNL_TEST 'a;'", 'git commit -m x;printenv FNL_TEST a\\;',
                        'git commit -m x&&printenv FNL_TEST "a&&"', "git commit -m x;printenv FNL_TEST $'a;'",
                        'git commit -m x;printenv FNL_TEST $"a;"', "git commit -m x;cat</tmp/.netrc - 'a;'",
                        "git commit -m 'x;' y;printenv"):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), denial(PARSE))
        # A quoted operator alone is a text value, as before.
        self.assertIsNone(self.hook('git commit -m "fix;" -q'))
        self.assertIsNone(self.hook('ls /tmp; pwd ""'))
        # A redirect glued to a word is its own word, so the program and the target are judged (review of #352).
        for command in ('printenv>&2', 'printenv>/tmp/afk-out', 'gh>out auth token', 'true; printenv>&2',
                        "true; pri''ntenv>&2", 'true; gh>out auth token', 'cat<~/.netrc', 'true; cat</tmp/x/.netrc'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), parked('floor'))

    def test_codex_exec_is_codex_s_subcommand_not_the_shell_wrapper(self):
        self.start()
        for command in ("codex exec -m gpt -s read-only 'review this'", 'codex exec --json -m gpt y'):
            with self.subTest(command=command):
                self.assertNotEqual(self.hook(command), denial(PARSE))
        # Every other placement keeps the wrapper rule, including the bypasses a looser walk let through.
        for command in ('exec -x ls', 'ls; exec -x ls', 'nohup exec -x ls', 'timeout 5 exec -x ls',
                        "codex exec -m gpt caffeinate -t 5 sh -c 'pr\"\"intenv'",
                        ">out caffeinate -t 5 sh -c 'pr\"\"intenv'", "env FOO=1 caffeinate -t 5 sh -c 'x'",
                        "pnpm exec caffeinate -t 5 sh -c 'x'", "exec -a 'a b' caffeinate -t 5 sh -c 'x'",
                        'exec -a codex exec -x ls', '>out codex exec -x ls', 'nohup codex exec -x ls',
                        "> 'out;codex' exec -- sh -c 'echo ok'", "ls; 'codex' exec -- sh -c x", "'codex' exec -- sh -c x",
                        'cd x && codex exec -- sh -c x', 'codex exec -m gpt; exec -x ls'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), denial(PARSE))

    def test_input_past_the_cap_denies_only_under_a_live_lease(self):
        padded = 'printenv' + ' ' * (262 * 1024)
        self.assertIsNone(self.hook(padded))
        self.start()
        self.assertEqual(self.hook(padded), parked('unsafe'))

    def test_a_variable_other_than_plain_home_is_not_read(self):
        self.start()
        for command in ('gh au${FNL_TEST_UNSET}th token', 'cat ~/.netrc$FNL_TEST_UNSET', 'print${FNL_TEST_UNSET}env',
                        'cat ~/.net"$NOPE"rc', "gh 'au'$NOPE'th' token", 'gh $SHELL:t:s/zsh/auth/ token',
                        'cat $HOME/.net$NOPE[1]rc', 'X=auth; gh $X token', 'printf -v x auth; gh $x token',
                        'cat ${HOME}rc', 'cat "$HOME"rc', 'cat $HOME[1]', 'cat $HOME:t'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), denial(PARSE))
        # Plain `$HOME` and `${HOME}` stay readable and are still expanded for the floor.
        self.assertEqual(self.hook('cat $HOME/.netrc'), parked('floor'))
        self.assertEqual(self.hook('cat "${HOME}"/.netrc'), parked('floor'))
        self.assertIsNone(self.hook('ls $HOME'))

    def test_the_lease_command_exemption_needs_a_plain_interpreter(self):
        self.start()
        script = str(ROOT / 'skills' / 'delegate' / 'scripts' / 'afk.py')
        self.assertIsNone(self.hook(f'python3 -I {script} effective'))
        import importlib.util
        spec = importlib.util.spec_from_file_location('afk_check_hook_under_test', HOOK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(module.own_lease_command(['python3', script, 'effective'], script, str(self.repo)))
        self.assertFalse(module.own_lease_command(['./python3', script, 'effective'], script, str(self.repo)))
        self.assertFalse(module.own_lease_command([str(self.repo / 'python3'), script, 'effective'], script, str(self.repo)))
        self.assertTrue(module.own_lease_command([sys.executable, script, 'effective'], script, str(self.repo)))
        relative = os.path.relpath(script, self.repo)
        self.assertTrue(module.own_lease_command(['python3', relative, 'effective'], script, str(self.repo)))
        (self.repo / 'sub').mkdir()
        self.assertFalse(module.own_lease_command(['python3', relative, 'effective'], script, str(self.repo / 'sub')))

    def test_substitution_and_a_glob_after_cd_are_not_read(self):
        self.start()
        for command in ('gh $(echo au)th token', 'gh `echo au`th token', 'cat $(echo ~/.ne)trc',
                        'gh "$(printf %s au)th" token', 'cd ~ && cat .ne?rc', 'cd && cat .ne?rc',
                        'cd ~ && cat .n[e]trc', 'cd ~/.cache/../ && cat .ne*c', 'pushd ~; cat .ne*c',
                        'chdir ~ && cat .ne?rc', '(cd ~ && cat .ne?rc)', '(cd ..; cat .ne?rc)', '{ cd ~; cat .ne?rc; }',
                        'echo auth token | xargs gh', "printf 'auth token' | xargs gh", 'xargs printenv',
                        'xargs az account get-access-token', 'xargs -0 -n 1 ls', "find ~ -name '.ne*c' -exec cat {} +",
                        "find ~ -name '.ne*c' | xargs cat", r'find . -exec env printenv \;', 'find . -name x -delete',
                        'fd netrc ~ -x cat', 'fd netrc ~ --exec-batch cat', 'git commit -m x;printenv',
                        'git commit -m x;gh auth token', 'echo ok&&printenv', 'cat ~/**/.ne?rc',
                        'git commit -m x;(printenv)', 'git commit -m x;(gh auth token)', 'git commit -m x|(printenv)'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), denial(PARSE))
        # A glob past the match limit is never truncated.
        many = self.home / 'many'
        many.mkdir()
        for index in range(201):
            (many / f'f{index:03d}').write_text('')
        self.assertEqual(self.hook(f'cat {many}/f*'), denial(PARSE))
        # A quoted operator stays one word.
        self.assertIsNone(self.hook('git status -- "a;b"'))
        self.assertIsNone(self.hook('git status 2>&1 | cat'))
        # A glob with no directory change, or anchored at `/` or `~`, is still expanded for the floor.
        self.assertIsNone(self.hook('cd src && ls /tmp/*.log'))
        self.assertIsNone(self.hook('ls *.py'))

    def test_a_credential_command_name_anywhere_is_the_floor(self):
        self.start()
        for command in ('nohup kubectl get secret x', 'nohup gh auth token', 'env -i printenv', 'nice printenv'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command), parked('floor'))
        # A flag after a wrapper whose flags are not read one by one denies before any name is judged.
        for command in ('caffeinate -s kubectl get secret x', 'caffeinate -t 5 gh auth token', 'caffeinate -s docker login'):
            with self.subTest(command=command):
                self.assertEqual(self.hook(command)['hookSpecificOutput']['permissionDecision'], 'deny')

    def test_a_redirect_glued_to_a_word_is_expanded(self):
        self.start()
        (self.home / '.netrc').write_text('machine example.com\n')
        env = {**self.env, 'HOME': str(self.home)}
        self.assertEqual(self.hook('cat x<~/.n?trc', env=env), parked('floor'))
        # The redirect is its own word since #352, so the program name is `cat` and the target is judged.
        self.assertEqual(self.hook('cat<~/.n?trc', env=env), parked('floor'))

    def test_an_unreadable_command_is_denied(self):
        self.start()
        self.assertEqual(self.hook('echo "unbalanced'), denial(PARSE))
        self.assertEqual(self.hook("echo 'unbalanced"), denial(PARSE))

    def test_a_stopped_lease_and_the_switch_allow(self):
        self.start()
        for value in ('off', 'OFF', '0', 'false', 'no'):
            with self.subTest(value=value):
                self.assertIsNone(self.hook('printenv', env={**self.env, 'FNL_AFK_HOOK': value}))
        self.afk('stop')
        self.assertIsNone(self.hook('printenv'))

    def test_other_tools_and_bad_input_allow(self):
        self.start()
        for payload in ('', 'not json', json.dumps({'tool_name': 'Edit', 'tool_input': {'command': 'printenv'}}),
                        json.dumps({'tool_name': 'Bash', 'tool_input': {}})):
            with self.subTest(payload=payload):
                result = subprocess.run([sys.executable, '-I', str(HOOK)], input=payload,
                                        env=self.env, capture_output=True, text=True, timeout=20)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    def test_the_command_text_is_never_stored(self):
        self.start()
        marker = 'zz-unique-command-marker'
        self.hook(f'echo {marker}')
        self.hook(f'printenv {marker}')
        for path in self.root.rglob('*'):
            if path.is_file():
                with self.subTest(path=path.name):
                    self.assertNotIn(marker.encode(), path.read_bytes())

    def test_a_pinned_merge_records_its_pin(self):
        self.start()
        head = 'c' * 40
        self.assertIsNone(self.hook(f'gh pr merge 7 --merge --match-head-commit {head} --repo github.com/example/demo'))
        log = (self.root / 'state/autopilot/log.jsonl').read_text().splitlines()
        pins = [json.loads(line) for line in log if json.loads(line).get('kind') == 'merge-pin']
        self.assertEqual([(p['pr'], p['head']) for p in pins], [(7, head)])

    def test_the_manifest_has_the_hook_in_its_own_group(self):
        manifest = json.loads((ROOT / '.claude-plugin/hooks.json').read_text())
        groups = [g for g in manifest['hooks']['PreToolUse']
                  if any('afk_check_hook.py' in h['command'] for h in g['hooks'])]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['matcher'], 'Bash')
        self.assertEqual(len(groups[0]['hooks']), 1)
        self.assertNotIn('metrics_hook.py', json.dumps(groups[0]))


if __name__ == '__main__':
    unittest.main()
