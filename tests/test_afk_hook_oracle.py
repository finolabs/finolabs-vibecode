"""The afk hook tokenizer against real shells (docs/specs/afk-hook-tokenizer.md, Verification, oracle test).

Only corpus entries the tokenizer accepts are run, each under `bash --noprofile --norc` and `zsh -f` through
`sandbox-exec` with a profile that allows writes only inside a fresh temporary folder and denies network, under
`env -i` with `PATH` holding only recording stubs, with a 5-second CPU and wall-clock limit. Every program an entry
names must be a stub, else the harness refuses it. The tokenizer's command sites and file openings must equal what
each shell did; an entry the shells read differently must get the split message. macOS only: elsewhere the test is
skipped."""

import importlib.util
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / 'scripts/afk_check_hook.py'
SANDBOX = Path('/usr/bin/sandbox-exec')
STUBS = ('ok', 'git', 'gh', 'cat', 'grep', 'head', 'node', 'sort', 'wc')
SHELLS = [('bash', path, ['--noprofile', '--norc']) for path in ('/bin/bash', '/opt/homebrew/bin/bash')
          if Path(path).exists()] + [('zsh', path, ['-f']) for path in ('/bin/zsh',) if Path(path).exists()]

# (entry, output files it opens, input pipes it opens). Straight-line: every site runs exactly once, and only
# stubs (programs that are not builtins in either shell) are named. The cases come from the spec's "Why", the hook
# spec's Verification, PR 352's tests and the false denials of the 18/11 review.
CORPUS = [
    ('ok a "b c"', [], []),
    ('ok /tmp; git status', [], []),
    ('ok /tmp;git status', [], []),
    ('ok /tmp&& git status', [], []),
    ('no /tmp|| git status', [], []),
    ('ok /tmp| head', [], []),
    ('ok /tmp ; ok ""', [], []),
    ('git status 2>&1 | head', [], []),
    ('grep -E "a|b" f', [], []),
    ("git commit -m 'fix;' -q", [], []),
    ('git status -- "a;b"', [], []),
    ("ok 'a;b' \"c|d\" e\\;f", [], []),
    ('ok x\\ #; git status', [], []),
    ('ok x #; git status', [], []),
    ('ok a\\\nb', [], []),
    ('ok a\\\\\ngit status', [], []),
    ('ok "a\\\nb"', [], []),
    ("ok $'plain' # a note", [], []),
    ('ok >out1', ['out1'], []),
    ('ok>out1 a', ['out1'], []),
    ('ok x2>out1', ['out1'], []),
    ('ok 2>out1 a', ['out1'], []),
    ('ok >>out1; ok >|out2', ['out1', 'out2'], []),
    ('ok &>out1', ['out1'], []),
    ('gh>out1 auth token', ['out1'], []),
    ('ok; 2>&1 git x', [], []),
    ('cat <in1', [], ['in1']),
    ('cat<in1', [], ['in1']),
    ('cat <in1 <in2', [], ['in1', 'in2']),
    ('ok x<in1', [], ['in1']),
    ('X=1 Y=2 git log', [], []),
    ('X=1', [], []),
    ('ok && X=1 git x', [], []),
    ('(ok a; git b) | cat', [], []),
    ('{ ok a; git b; } | head', [], []),
    ('if ok; then git a; fi', [], []),
    ('for x in a; do git a; done', [], []),
    ("cat <<'EOF'\na; b\nEOF\ngit x", [], []),
    ("git commit -F - <<'EOF'\nfix; tidy\nEOF", [], []),
    ('cat <<-EOF\n\tx\n\tEOF', [], []),
    ("cat <<< 'a b'", [], []),
    ('ok "$HOME"/x $HOME ${HOME}/y', [], []),
    ('ok ~/x ~', [], []),
    ('codex_like exec -s read-only x', [], []),
    ('ok a\nok b\n\ngit c', [], []),
    ('! ok a', [], []),
    ('ok \\# a#b', [], []),
    ('ok "" \'\'', [], []),
    ('gh pr create --body; git x', [], []),
    ('git commit -m; git x', [], []),
    ('ok -c "print(1)\nprint(2)"', [], []),
    ("grep 'import|export' f | wc -l", [], []),
    ('ok a && no b || git c', [], []),
    ('ok a\\\n', [], []),
    ('X=a; git y', [], []),
    ('git x 2>out1 >out2 <in1', ['out1', 'out2'], ['in1']),
    ('ok <>out1', ['out1'], []),
]
STUBS = STUBS + ('codex_like', 'no')
HOME = '/oracle-home'

# Entries the tokenizer must refuse (the split message); they are never run.
REFUSED = ['ok $"abc"', 'ok 12>&1', 'ok |& cat', 'ok &| cat', 'ok >! f', 'case x in x) ok;; esac', '[[ a == b ]]',
           'for x; do ok; done', 'for ((i=0;i<1;i++)); do ok; done', 'x=(a b)', 'ok <1-3>', 'ok {x}>f', 'ok $X',
           'ok ${HOME:-x}', 'ok $(ok)', 'ok `ok`', 'ok <(ok)', 'ok $((1))', 'ok {a,b}', '=ok', 'ok ~+/x',
           'select x in a; do ok; done', 'coproc ok', 'repeat 2 ok', 'cat <<EOF\nno end', 'ok &>>f', "ok $'\\x61'",
           'cat <<true\ntr\\\nue\nok\ntrue', 'ok "$HOM""E"', 'ok $HO""ME', 'ok "${HO}ME"']


def hook_module():
    spec = importlib.util.spec_from_file_location('afk_check_hook_oracle', HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUB = '''#!/bin/sh
n=${0##*/}
{ printf '%s' "$n"; for a in "$@"; do printf '\\037%s' "$a"; done; printf '\\036'; } >> "$LOG"
[ "$n" != no ]
'''


def profile(folder):
    reads = ''.join(f'(subpath "{p}")' for p in ('/usr', '/bin', '/System', '/Library/Apple', '/private/var/db/dyld',
                                                  '/opt/homebrew', folder))
    return ('(version 1)(deny default)(allow process-exec*)(allow process-fork)(allow signal (target self))'
            '(allow sysctl-read)(allow file-read-metadata)'
            f'(allow file-read* {reads} (literal "/") (subpath "/private/etc") (subpath "/dev"))'
            f'(allow file-write* (subpath "{folder}") (literal "/dev/null"))'
            '(allow file-ioctl (literal "/dev/null"))(deny network*)')


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))


@unittest.skipUnless(sys.platform == 'darwin' and SANDBOX.exists() and SHELLS, 'needs macOS sandbox-exec and shells')
class TokenizerOracleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = hook_module()
        cls.versions = {}
        for name, path, _flags in SHELLS:
            version = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5).stdout
            cls.versions[path] = version.splitlines()[0] if version else name

    def run_entry(self, shell, command, inputs):
        """(sites run, output files created, input pipes opened) for one entry under one shell."""
        name, path, flags = shell
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw).resolve()
            stubs, home, work, tmp = folder / 'stubs', folder / 'home', folder / 'work', folder / 'tmp'
            for item in (stubs, home, work, tmp):
                item.mkdir()
            for stub in STUBS:
                (stubs / stub).write_text(STUB)
                (stubs / stub).chmod(0o755)
            log = folder / 'log'
            log.write_text('')
            opened, stop = set(), threading.Event()
            for pipe in inputs:
                os.mkfifo(work / pipe)

            def feed(pipe):
                while not stop.is_set():
                    try:
                        fd = os.open(work / pipe, os.O_WRONLY | os.O_NONBLOCK)
                    except OSError:
                        time.sleep(0.01)
                        continue
                    opened.add(pipe)
                    os.close(fd)
                    return

            threads = [threading.Thread(target=feed, args=(p,), daemon=True) for p in inputs]
            for thread in threads:
                thread.start()
            env = ['/usr/bin/env', '-i', f'HOME={home}', f'PATH={stubs}', f'LOG={log}', f'TMPDIR={tmp}', f'TMPPREFIX={tmp}/zsh']
            try:
                subprocess.run([str(SANDBOX), '-p', profile(folder), *env, path, *flags, '-c', command],
                               cwd=work, capture_output=True, timeout=5, preexec_fn=limits)
            finally:
                stop.set()
                for thread in threads:
                    thread.join(1)
            records = [r for r in log.read_text().replace(str(home), HOME).split('\x1e') if r]
            sites = sorted(tuple(r.split('\x1f')) for r in records)
            created = sorted(p.name for p in work.iterdir() if p.is_file() and p.name not in inputs)
            return sites, created, sorted(opened)

    def expected(self, command):
        saved = os.environ.get('HOME')
        os.environ['HOME'] = HOME
        try:
            return self.expected_sites(command)
        finally:
            if saved is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = saved

    def expected_sites(self, command):
        sites, _words, _listed = self.hook.judged(command)
        for site in sites:
            if site.argv and site.argv[0] not in STUBS:
                self.fail(f'the harness refuses {command!r}: {site.argv[0]!r} is not a stub')
        ran = sorted(tuple(w.expanded() for w in site.words) for site in sites if site.argv and not site.body)
        outputs = sorted({t.text for s in sites for _fd, op, t, _h in s.redirects if op in ('>', '>>', '>|', '&>', '<>')})
        inputs = sorted({t.text for s in sites for _fd, op, t, _h in s.redirects if op == '<'})
        return ran, outputs, inputs

    def test_accepted_entries_match_every_shell(self):
        for command, outputs, inputs in CORPUS:
            ran, out, into = self.expected(command)
            self.assertEqual((out, into), (sorted(outputs), sorted(inputs)), command)
            for shell in SHELLS:
                with self.subTest(command=command, shell=self.versions[shell[1]]):
                    self.assertEqual(self.run_entry(shell, command, inputs), (ran, out, into))

    def test_refused_entries_get_the_split_message_and_never_run(self):
        for command in REFUSED:
            with self.subTest(command=command):
                with self.assertRaises(self.hook.Unreadable):
                    self.hook.judged(command)

    def test_the_sandbox_denies_writes_outside_its_folder(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw).resolve()
            subprocess.run([str(SANDBOX), '-p', profile(folder), SHELLS[0][1], '--noprofile', '--norc', '-c',
                            f'echo x > {outside}/escaped'], capture_output=True, timeout=5)
        self.assertFalse((outside / 'escaped').exists())


if __name__ == '__main__':
    unittest.main()
