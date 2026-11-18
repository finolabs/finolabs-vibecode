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
    ('ok x ""2>out1', ['out1'], []),
    ('ok &&\\\n git x', [], []),
    # Read through the joined text (class 4 of the PR 358 checkpoint): the shells join these too.
    ("cat <$\\\n'i3'", [], ['i3']),
    ('ok 2>&\\\n1', [], []),
    ('ok a\\\n>out1', ['out1'], []),
    ('ok $\\\n{HOME}/x "$\\\nHOME"', [], []),
    ('ok "$HOME"/x', [], []),
    ("ok '~'/x \\~/y", [], []),
]
STUBS = STUBS + ('codex_like', 'no')
HOME = '/oracle-home'

# Entries the tokenizer must refuse (the split message); they are never run.
REFUSED = ['ok $"abc"', 'ok 12>&1', 'ok |& cat', 'ok &| cat', 'ok >! f', 'case x in x) ok;; esac', '[[ a == b ]]',
           'for x; do ok; done', 'for ((i=0;i<1;i++)); do ok; done', 'x=(a b)', 'ok <1-3>', 'ok {x}>f', 'ok $X',
           'ok ${HOME:-x}', 'ok $(ok)', 'ok `ok`', 'ok <(ok)', 'ok $((1))', 'ok {a,b}', '=ok', 'ok ~+/x',
           'select x in a; do ok; done', 'coproc ok', 'repeat 2 ok', 'cat <<EOF\nno end', 'ok &>>f', "ok $'\\x61'",
           'cat <<true\ntr\\\nue\nok\ntrue', 'ok "$HOM""E"', 'ok $HO""ME', 'ok "${HO}ME"',
           'for HOME in a; do ok; done', 'HOME=a; ok ~',
           "read -aHOME <<<'x'; ok", 'ok 2\\\n>o1', '>o1', 'ok; <i1', 'cat <1\\\n-3> out',
           # Class 4: bash joins a continuation inside an operator, zsh reads a parse error (oracle, 18/11/2026).
           'ok &\\\n& git x', 'ok 2>\\\n&1', 'ok >\\\n> o1', 'ok <\\\n> o1', 'cat <\\\n<<y', 'ok |\\\n| git x',
           'ok >\\\n|o1', 'cat <\\\n<-E\nx\nE', 'ok 1\\\n2>o1',
           # The generated oracle: zsh's child for a bare `exec` in a pipeline runs the rest of the call again.
           'exec 3<f1 | ok A; ok B', 'exec >o1 | ok A', 'ok | exec 3<f1',
           # Class 1: bash expands `~` after `=` in any word, zsh only in an assignment.
           'ok --p=~/x', 'ok x=\\\n~/q', 'X=~/a ok', 'ok a:~/b',
           # Class 2: every binding form that names `HOME`.
           'read -r -aHOME <<<x; ok', "read 'HOME?p' <<<x; ok", 'declare -n r=HOME; ok', 'export HOME=x; ok',
           'typeset -x HOME; ok', 'getopts a HOME; ok', 'mapfile HOME <<<x; ok', 'unset HOME; ok', 'printf -vHOME x']


def hook_module():
    spec = importlib.util.spec_from_file_location('afk_check_hook_oracle', HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUB = '''#!/bin/sh
n=${0##*/}
r=$n
for a in "$@"; do r="$r$(printf '\\037')$a"; done
printf '%s\\036' "$r" >> "$LOG"  # one write, so stubs run in the background never interleave
if [ "$n" = node ]; then  # a code reader: record whether any descriptor besides stdout and stderr gives it input
  for fd in 0 3 4 5 6 7 8 9; do
    [ -e /dev/fd/$fd ] || continue
    t=$(/usr/bin/stat -L -f %HT /dev/fd/$fd)
    [ "$fd" = 0 ] && [ "$t" = 'Character Device' ] && continue  # the harness's /dev/null
    printf 'input\\036' >> "$LOG.in"
  done
fi
[ "$n" != no ]
'''
# Files present in the working folder of every run and of the tokenizer's reading: globs match them, a quoted `'~'`
# names the folder `~`, and a file `HOME` lets a glob name the variable.
FIXTURES = ('f1', 'f2', 'HOME', '~/n1')


def make_fixtures(folder):
    for name in FIXTURES:
        (folder / name).parent.mkdir(exist_ok=True)
        (folder / name).write_text('')


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


class OracleBase(unittest.TestCase):
    """The sandboxed harness: runs one entry under one shell and reads what the tokenizer expects."""

    BUILTINS = ()  # builtins an entry may name besides the stubs: none for the corpus

    @classmethod
    def setUpClass(cls):
        cls.hook = hook_module()
        cls.versions = {}
        for name, path, _flags in SHELLS:
            version = subprocess.run([path, '--version'], capture_output=True, text=True, timeout=5).stdout
            cls.versions[path] = version.splitlines()[0] if version else name
        fixtures = tempfile.TemporaryDirectory()
        cls.addClassCleanup(fixtures.cleanup)
        cls.fixtures = Path(fixtures.name).resolve()
        make_fixtures(cls.fixtures)

    def run_entry(self, shell, command, inputs):
        """(sites run, output files created, input pipes opened) for one entry under one shell."""
        return self.run_full(shell, command, inputs)[:3]

    def run_full(self, shell, command, inputs):
        """(sites run, output files created, input pipes opened, whether a `node` stub was given input)."""
        name, path, flags = shell
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw).resolve()
            stubs, home, work, tmp = folder / 'stubs', folder / 'home', folder / 'work', folder / 'tmp'
            for item in (stubs, home, work, tmp):
                item.mkdir()
            make_fixtures(work)
            for stub in STUBS:
                (stubs / stub).write_text(STUB)
                (stubs / stub).chmod(0o755)
            log = folder / 'log'
            log.write_text('')
            (folder / 'log.in').write_text('')
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
                    os.close(fd)  # keep feeding: an entry may open the same input twice

            threads = [threading.Thread(target=feed, args=(p,), daemon=True) for p in inputs]
            for thread in threads:
                thread.start()
            env = ['/usr/bin/env', '-i', f'HOME={home}', f'PATH={stubs}', f'LOG={log}', f'TMPDIR={tmp}', f'TMPPREFIX={tmp}/zsh']
            try:
                try:
                    subprocess.run([str(SANDBOX), '-p', profile(folder), *env, path, *flags, '-c', command],
                                   cwd=work, stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
                                   preexec_fn=limits)
                except subprocess.TimeoutExpired:
                    pass  # a site that waits on an input nobody feeds; what ran before it still counts
            finally:
                stop.set()
                for thread in threads:
                    thread.join(1)
            records = [r for r in log.read_text().replace(str(home), HOME).split('\x1e') if r]
            sites = sorted(tuple(r.split('\x1f')) for r in records)
            created = sorted(p.name for p in work.iterdir()
                             if p.is_file() and p.name not in inputs and p.name not in FIXTURES)
            fed = bool((folder / 'log.in').read_text())
            return sites, created, sorted(opened), fed

    def expected(self, command):
        saved, here = os.environ.get('HOME'), os.getcwd()
        os.environ['HOME'] = HOME
        os.chdir(self.fixtures)  # globs and quoted anchors are read against the same files the shells see
        try:
            return self.expected_sites(command)
        finally:
            os.chdir(here)
            if saved is None:
                os.environ.pop('HOME', None)
            else:
                os.environ['HOME'] = saved

    def expected_sites(self, command):
        sites, _words, _listed = self.hook.judged(command)
        for site in sites:
            if site.argv and not site.body and site.argv[0] not in STUBS + self.BUILTINS:
                self.fail(f'the harness refuses {command!r}: {site.argv[0]!r} is not a stub')

        def argv(site):
            out = []
            for word in site.words:
                matches = sorted(word.paths()) if word.globbed else []
                out.extend(matches or [word.expanded()])  # no match: bash keeps the word, zsh runs nothing
            return tuple(out)

        ran = sorted(argv(site) for site in sites if site.argv and site.argv[0] in STUBS and not site.body)
        outputs = sorted({t.text for s in sites for _fd, op, t, _h in s.redirects
                          if op in ('>', '>>', '>|', '&>', '<>') or op == '>&' and not t.text.isdigit() and t.text != '-'})
        inputs = sorted({t.text for s in sites for _fd, op, t, _h in s.redirects if op == '<'})
        return ran, outputs, inputs


@unittest.skipUnless(sys.platform == 'darwin' and SANDBOX.exists() and SHELLS, 'needs macOS sandbox-exec and shells')
class TokenizerOracleTest(OracleBase):
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


# A grammar for generated inputs, one fragment list per class of the PR 358 checkpoint. Words (class 1): quoted and
# unquoted anchors, globs over the fixtures, `~` after `=` and `:`. Bindings (class 2): every form that may bind a
# name, `HOME` or another, each followed by a site that expands `$HOME` and `~`. Redirects (class 3): every redirect
# that supplies input, on `node`, the code-reader stub. Continuations (class 4): a backslash-newline inserted at a
# random place, inside operators, words and globs.
WORDS = ['a', '"a b"', "'c;d'", '\\;', '$HOME', '"$HOME"/x', '${HOME}/y', '~', '~/y', "'~'/n?", '"~"/n1', '\\~/n1',
         '~/n?', 'f?', "'f?'", '"f"?', 'f[12]', '$HOME/n?', 'x=~/q', '--p=~/q', 'a:~/b', 'HOME', 'HO?E', '2', "$'q'",
         ' #c']
REDIRECTS = ['>o1', '2>o2', '<i1', '<>o3', '3<i2', '0<i1', '<&0', '0>&2', '2>&1', '<<<x', '>&2', '>>o4', '1>&2']
BINDINGS = ['read -aHOME <<<x', 'read -r HOME <<<x', "read 'HOME?p' <<<x", 'read -a HO?E <<<x', 'export HOME=x',
            'HOME=x', 'declare -x HOME=x', 'typeset HOME=x', 'printf -v HOME x', 'printf -vHOME x', 'getopts a HOME',
            'unset HOME', 'readonly HOME', 'mapfile HOME <<<x', 'for HOME in x; do ok; done', 'read x <<<y',
            'export Y=1', 'exec 3<i2', 'read -a y <<<x', 'printf -v y x']
SEPARATORS = ['; ', ' && ', '\n', ' | ', ';']
PROGRAMS = ['ok', 'git', 'cat', 'node']


def generated(seed, count):
    """`count` (command, classes) pairs from the grammar, reproducible from `seed`."""
    import random
    rng = random.Random(seed)
    for _ in range(count):
        classes, sites = set(), []
        if rng.random() < 0.3:
            sites.append(rng.choice(BINDINGS))
            sites.append('ok "$HOME"/x ~/z')
            classes.add(2)
        for _site in range(rng.randint(1, 2)):
            parts = [rng.choice(PROGRAMS)]
            for _word in range(rng.randint(0, 3)):
                parts.append(rng.choice(WORDS))
                classes.add(1)
            for _redirect in range(rng.randint(0, 2)):
                parts.append(rng.choice(REDIRECTS))
                classes.add(3)
            sites.append(' '.join(parts))
        command = sites[0]
        for site in sites[1:]:
            command += rng.choice(SEPARATORS) + site
        if rng.random() < 0.15:
            command += ' <<E\nx\nE'
            classes.add(3)
        if rng.random() < 0.5:
            at = rng.randrange(1, len(command))
            command = command[:at] + '\\\n' + command[at:]
            classes.add(4)
        yield command, classes


@unittest.skipUnless(sys.platform == 'darwin' and SANDBOX.exists() and SHELLS, 'needs macOS sandbox-exec and shells')
class GeneratedOracleTest(OracleBase):
    """Generated inputs (fixed seed, capped count): the hook either reads them as every shell does or refuses them.
    For every input the tokenizer accepts, what each shell ran must be among the sites the tokenizer read, and every
    file it created or input pipe it opened among the tokenizer's redirect targets; a shell may run less (a failed
    `&&`, a parse error, a glob with no match in zsh), never more, and when all shells agree they must agree with the
    tokenizer. A `node` stub that any shell gave readable input must be refused by the hook's call-wide rules."""

    BUILTINS = ('read', 'export', 'declare', 'typeset', 'printf', 'getopts', 'unset', 'readonly', 'mapfile', 'exec')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        sys.path.insert(0, str(ROOT / 'skills/delegate/scripts'))
        import afk
        cls.afk = afk

    def refused_by_the_hook(self, command):
        """True when the hook's per-site and call-wide rules refuse the tokenizer's reading of `command`."""
        sites, _words, listed = self.hook.judged(command)
        return (any(self.hook.reparsed(site.full, self.afk) for site in sites if site.full)
                or self.hook.call_wide(sites, listed, self.afk))

    def expected_sites(self, command):
        sites, _words, _listed = self.hook.judged(command)
        for site in sites:
            for word in site.assignments + site.words:
                word.paths()  # as `site_entries` reads it: a glob that names `HOME` is refused
        return super().expected_sites(command)

    def test_generated_inputs_are_read_as_the_shells_read_them_or_refused(self):
        from collections import Counter
        wanted = int(os.environ.get('FNL_ORACLE_CASES', '60'))
        accepted, seen = 0, Counter()
        for command, classes in generated(358, 3000):
            if accepted >= wanted:
                break
            try:
                ran, outputs, inputs = self.expected(command)
            except self.hook.Unreadable:
                continue  # the split message: never run
            except AssertionError:
                continue  # a program that is not a stub (a comment made the rest a command): never run
            if set(outputs) & set(inputs):
                continue
            accepted += 1
            seen.update(classes)
            results = {}
            for shell in SHELLS:
                with self.subTest(command=command, shell=self.versions[shell[1]]):
                    sites, created, opened, fed = self.run_full(shell, command, inputs)
                    results[shell[1]] = (sites, created, opened)
                    self.assertEqual(Counter(sites) - Counter(ran), Counter(), 'a site the tokenizer did not read')
                    self.assertLessEqual(set(created), set(outputs), 'a file the tokenizer did not read')
                    self.assertLessEqual(set(opened), set(inputs), 'an input the tokenizer did not read')
                    if fed:
                        self.assertTrue(self.refused_by_the_hook(command), 'a code reader given input')
            if len(set(map(repr, results.values()))) == 1 and not any(c in command for c in '&|'):
                with self.subTest(command=command, shells='all agree'):
                    self.assertEqual(next(iter(results.values())), (ran, outputs, inputs))
        self.assertGreaterEqual(accepted, min(wanted, 20), 'too few generated inputs were accepted')
        self.assertEqual(sorted(seen), [1, 2, 3, 4], 'every class reaches the shells')

    def test_generated_refusals_cover_every_class(self):
        from collections import Counter
        refused = Counter()
        for command, classes in generated(358, 3000):
            try:
                self.expected(command)
            except self.hook.Unreadable:
                refused.update(classes)
            except AssertionError:
                pass  # a program that is not a stub
        self.assertEqual(sorted(refused), [1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
