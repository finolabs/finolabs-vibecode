#!/usr/bin/env python3
"""Claude Code PreToolUse Bash hook for the away lease (CLAUDE.md, tenth scoped exception; docs/specs/afk-check-hook.md).

While a valid, unexpired away lease exists, it splits the Bash command into words in memory and judges that argv
through the same `afk.py check --coordinator claude --argv-json` code, in the hook's working folder. A Tier 3 answer,
in either mode, denies the call with one fixed message naming the code; a command that cannot be split into words is
denied with another fixed message, and once a lease is live any error denies as `unsafe`. With no live lease, or on a
Tier 1 answer, it prints nothing and returns no decision. The
command text is never stored, logged or sent: only what a `check` call keeps is written.
"""

import os
import re
import signal
import sys

PARSE_MESSAGE = 'afk: the command could not be read; write it as a simpler command'


def parked(code):
    return f'afk: {code}; this action is parked under the away lease (afk.py check)'


UNSAFE = parked('unsafe')


def deny(reason):
    import json
    os.write(1, (json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                                    'permissionDecisionReason': reason}},
                            separators=(',', ':')) + '\n').encode())


def unquoted_newlines(command):
    """The command with every newline outside quotes and comments turned into a `;` separator, so each line is judged
    as its own command (shlex alone reads a newline as a space). Quotes are tracked as bash tracks them: a `#` that
    starts a word comments to the end of the line, a backslash-newline outside single quotes joins lines, and a
    `$'...'` string holding a backslash is refused. Raises ValueError on an unbalanced quote or a form it cannot read the way bash does."""
    out, single, double, i, n = [], False, False, 0, len(command)
    while i < n:
        char = command[i]
        if char == '\\' and not single:
            if i + 1 < n and command[i + 1] == '\n':
                i += 2  # line continuation: bash joins the two lines
                continue
            out.append(command[i:i + 2])
            i += 2
            continue
        if not single and not double:
            if char == '$' and i + 1 < n and command[i + 1] == "'":
                end = command.find("'", i + 2)
                if end < 0 or '\\' in command[i + 2:end]:
                    raise ValueError('ansi-c quote')
                out.append(command[i + 1:end + 1])
                i = end + 1
                continue
            if char == '$' and i + 1 < n and command[i + 1] == '"':
                i += 1  # a locale string `$"..."` reads as `"..."`
                continue
            if char == '#' and (i == 0 or command[i - 1] in ' \t\n;&|()<>'):
                end = command.find('\n', i)
                i = n if end < 0 else end
                continue
            if char == '\n':
                out.append(' ; ')
                i += 1
                continue
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        out.append(char)
        i += 1
    if single or double:
        raise ValueError('unbalanced quote')
    return ''.join(out)


NAME_REF = re.compile(r'\$\{[A-Za-z_][A-Za-z0-9_]*\}')
SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'mksh', 'fish', 'csh', 'tcsh'}


VARIABLE = re.compile(r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))')


def home_reference(command, end, double):
    """True when the variable that ends at `end` is `$HOME` or `${HOME}` followed by `/`, whitespace or the end, or
    inside double quotes by a closing quote followed by one of those: the only form whose value the hook and the
    Bash tool share and whose word boundary is plain."""
    name = command[command.rfind('$', 0, end):end].strip('${}')
    if name != 'HOME':
        return False
    after = command[end:end + 1]
    if double and after == '"':
        after = command[end + 1:end + 2]
    return after in ('', '/') or after.isspace()


def unreadable(command):
    """True when the command holds a shell form the hook cannot reproduce exactly (bash and zsh): brace expansion,
    a `${...}` with an operator, a special or positional parameter, arithmetic, process substitution, a zsh `=name`,
    a `(` inside a word or a `~+`, `~-` or `~N` prefix. Single-quoted text is literal and skipped."""
    single, double, i, n = False, False, 0, len(command)
    while i < n:
        char, nxt = command[i], command[i + 1:i + 2]
        start = i == 0 or command[i - 1] in ' \t\n;&|<>'
        if char == '\\' and not single:
            i += 2
            continue
        if char == "'" and not double:
            single = not single
        elif char == '"' and not single:
            double = not double
        elif not single:
            if char == '`':
                return True  # command substitution: its output exists only at run time
            if char == '$':
                if nxt == '{' and not NAME_REF.match(command, i):
                    return True
                if nxt and nxt in '_@*#?-$!0123456789[' or command.startswith('$((', i):
                    return True
                if nxt == '(':
                    return True  # command substitution: its output exists only at run time
                ref = VARIABLE.match(command, i)
                if ref and not home_reference(command, ref.end(), double):
                    return True  # a variable the shell may expand differently (unset, set in the command, zsh forms)
            if not double:
                if char in '<>' and nxt == '(':
                    return True
                if char == '{':
                    end = command.find('}', i)
                    if end > 0 and (',' in command[i:end] or '..' in command[i:end]):
                        return True
                if char == '=' and start:
                    return True
                if char == '(' and i > 0 and command[i - 1] not in ' \t\n;&|<>$(':
                    return True
                if char == '~' and start and nxt and nxt in '+-0123456789':
                    return True
        i += 1
    return False


OPTION_COMMANDS = {'setopt', 'unsetopt', 'shopt', 'emulate'}
# Words a shell reads as code or as a lookup the hook cannot follow: never judged, always the split message.
OPAQUE_WORDS = {'builtin', 'nocorrect', 'hash', 'alias', 'function', 'case', 'coproc', 'enable', 'unalias', 'trap',
                'watch', 'parallel'}
# The only flags a wrapper may carry before the command it runs: flags the shared table reads correctly (each
# valued one with its value). Any other flag after any wrapper, and any flag at all after `flock` or `script`, may
# hide that command, so it gets the split message.
WRAPPER_FLAGS = {'timeout': {'-k': 1, '-s': 1}, 'nice': {'-n': 1}, 'exec': {'-a': 1, '-c': 0, '-l': 0},
                 'npx': {'-y': 0, '--yes': 0, '-p': 1}}
GLOB_OPTIONS = ('glob', 'magic', 'equals', 'brace', 'rcexpand', 'wordsplit')
EXEC_FLAGS = {'-exec', '-execdir', '-ok', '-okdir'}


def bad_program(program, words):
    """True for a program the hook cannot read the way the shell runs it."""
    if not isinstance(program, str):
        return False  # only assignments: nothing runs
    if any(c in program for c in '$`*?[{^#~') and program != '#inline':
        return True
    base = os.path.basename(program)
    if base in {'eval', 'source', '.'} or base in OPTION_COMMANDS:
        return True
    if base == 'set' and any(any(o in w.lower().replace('_', '') for o in GLOB_OPTIONS) for w in words):
        return True
    return base in SHELLS and (any(w in {'-c', '-s', '<<<', '<'} or w.startswith('-c') for w in words)
                               or all(w.startswith('-') for w in words))


def glued_split(argv, afk):
    """argv with every operator glued to a word (`ls|xargs`, `(xargs`, `true&&xargs`) cut out as `;`, so the
    wrapper-flag rule sees each wrapper wherever the shell starts a command."""
    words = []
    for word in argv:
        for piece in afk.SPLIT_INLINE.split(word):
            if afk.SPLIT_INLINE.fullmatch(piece):
                words.append(';')
            else:
                words.extend(w.strip('()') for w in piece.split() if w.strip('()'))
    return words


def reparsed(argv, afk):
    """True when any command `check` reads out of argv (every reading, wrappers, glued operators and compound words
    included, and a `find -exec` command) runs code a shell parses again, changes the shell's glob options, or has
    a program name holding an expansion, a glob or a brace."""
    if any(word in OPAQUE_WORDS for word in argv):
        return True
    wrappers = afk.PREFIX_WORDS | afk.FILE_PREFIXES
    words = glued_split(argv, afk)
    for index, word in enumerate(words):
        base = os.path.basename(word)
        if base not in wrappers:
            continue
        allowed, at = WRAPPER_FLAGS.get(base, {}), index + 1
        if base in afk.FILE_PREFIXES and any(w.startswith('-') for w in words[index + 1:index + 4]):
            return True
        while at < len(words) and words[at].startswith('-') and words[at] not in OPERATORS:
            if words[at] not in allowed:
                return True  # a wrapper flag `commands_of` may misread
            at += 1 + allowed[words[at]]
    for reading in afk.READINGS:
        for program, words, _env, inline, _pattern in afk.commands_of(argv, full=True, split_patterns=reading):
            if inline:
                continue
            if bad_program(program, list(words)):
                return True
            for index, word in enumerate(words):
                if word in EXEC_FLAGS and index + 1 < len(words):
                    rest = [w for w in words[index + 1:] if w not in {';', '\\;', '+', '{}'}]
                    if rest and reparsed(rest, afk):
                        return True
    return False


def floor_words(argv, paths, afk):
    """True when any word that is not a commit or pull request text value, or any expanded path, names a credential
    command that is a floor in every use (`printenv`, `security`, ...), or a credential command with subcommands is
    followed anywhere by one of them (`gh ... auth`), wherever it stands: a wrapper or its flags cannot hide it."""
    names = {name for name, subs in afk.CREDENTIAL_COMMANDS.items() if subs is None}
    stripped, _texts = afk.open_texts(argv)
    words = [w for w in stripped if isinstance(w, str)]
    expanded = [os.path.basename(p) for p in paths if isinstance(p, str)]
    bases = [os.path.basename(w) for w in words]
    if any(b in names for b in bases + expanded):
        return True
    # A credential command with subcommands floors when one of them follows it anywhere (an expanded program path
    # counts wherever it stands), and so does a credential pair or triple in order, so no wrapper flag hides it.
    for index, base in enumerate(bases):
        subs = afk.CREDENTIAL_COMMANDS.get(base)
        if subs and any(w in subs for w in words[index + 1:]):
            return True
    if any((afk.CREDENTIAL_COMMANDS.get(b) or set()) & set(words) for b in expanded):
        return True
    for pair in afk.CREDENTIAL_PAIRS:
        if pair[0] in expanded and all(w in words for w in pair[1:]):
            return True
        position = 0
        for base in bases:
            if position < len(pair) and (base if position == 0 else base) == pair[position]:
                position += 1
        if position == len(pair):
            return True
    return False


LEASE_COMMANDS = {'stop', 'log', 'review', 'effective', 'rules', 'check', 'packet-check'}
OPERATORS = {';', '&&', '||', '|', '&', '|&'}
SAFE_ARGUMENT = re.compile(r'[A-Za-z0-9 ._,:=/@+%-]*')


def own_lease_command(argv, script, cwd):
    """True for `python3 [-I] <this install's afk.py> <lease command> ...` with no operator after it and no argument
    made of anything but letters, digits, spaces and `._,:=/@+%-`. The interpreter is a bare `python3` or `python`
    or a path to the hook's own interpreter; the script path is resolved against the Bash tool's `cwd`."""
    if not argv:
        return False
    if '/' in argv[0]:
        if os.path.realpath(argv[0]) != os.path.realpath(sys.executable):
            return False  # a path names the hook's own interpreter or nothing
    elif argv[0] not in {'python3', 'python'}:
        return False
    rest = argv[1:]
    while rest and rest[0] in {'-I', '-B', '-u'}:
        rest = rest[1:]
    if len(rest) < 2 or rest[1] not in LEASE_COMMANDS or any(t in OPERATORS for t in rest):
        return False
    if not all(SAFE_ARGUMENT.fullmatch(word) for word in rest[1:]):
        return False  # a word bash could expand, redirect or split is judged like any command
    try:
        return os.path.realpath(os.path.join(cwd, rest[0])) == os.path.realpath(script)
    except (OSError, ValueError):
        return False




DIRECTORY_CHANGES = {'cd', 'pushd', 'popd', 'chdir'}
# Programs that build a command or pick its files from data that exists only at run time (stdin, a match): the hook
# cannot know what they run, so a command holding one is never read.
RUNTIME_PROGRAMS = {'xargs'}
RUNTIME_ACTIONS = {'find': EXEC_FLAGS | {'-delete'}, 'fd': {'-x', '-X', '--exec', '--exec-batch'},
                   'fdfind': {'-x', '-X', '--exec', '--exec-batch'}}


def command_words(argv, afk):
    """The argv's words with commit and pull request text values left out and glued operators cut out, each
    stripped of a leading `(`, `{` or `!`, as base names."""
    stripped, _texts = afk.open_texts(argv)
    words = glued_split([w for w in stripped if isinstance(w, str)], afk)
    return [os.path.basename(w.lstrip('({!')) for w in words]


def glued_operator(text, argv):
    """True when an operator outside quotes is glued to a word (`x;printenv`, `a&&b`, `ls|cat`): the word reads as
    one argument here, as a commit message or another text value, while the shell runs what follows it."""
    import shlex
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.commenters = ''
    lexer.whitespace_split = True
    return operators_in(list(lexer)) != operators_in(argv)


PUNCTUATION = re.compile(r'[();<>|&]+')
REDIRECT = re.compile(r'[0-9]*(?:&>>?|[<>]+[&|]?)')
OPERATOR = re.compile(r'\|\||&&|\|&|;|\||&')


def operators_in(tokens):
    """The control operators inside every token made only of punctuation (`;(` holds `;`), redirects left out."""
    found = []
    for token in tokens:
        if PUNCTUATION.fullmatch(token):
            found.extend(OPERATOR.findall(REDIRECT.sub(' ', token)))
    return sorted(found)


def outside_allowlist(argv, afk):
    """True when the command holds a form outside the syntax the hook reads in full: a program fed by run-time
    data (`xargs`, `find -exec` or `-delete`, `fd --exec`), or a glob not anchored at `/` or `~` in a command
    that changes directory (`cd`, `pushd`, `popd`, `chdir`, in a subshell or a group too), which the shell
    expands in a folder the hook cannot know."""
    words = command_words(argv, afk)
    if any(w in RUNTIME_PROGRAMS for w in words):
        return True
    for program, actions in RUNTIME_ACTIONS.items():
        if program in words and any(w in actions or (w.startswith('--exec') and program != 'find') for w in words):
            return True
    if any(w in DIRECTORY_CHANGES for w in words):
        return any(any(c in w for c in '*?[') and not w.startswith(('/', '~')) for w in argv)
    return False


def shell_expanded(word):
    """`~` and `$name`/`${name}` expanded as the shell does: an unset variable becomes empty, not literal text."""
    return VARIABLE.sub(lambda m: os.environ.get(m.group(1) or m.group(2), ''), os.path.expanduser(word))


def expanded_paths(argv, limit=200):
    """The paths the shell would read for each word, and each whitespace-separated piece of a word, holding `~`, `$`
    or a glob character, in memory only."""
    import glob
    found = []
    for piece in (p for word in argv for p in re.split(r'[\s<>|&;()]+', word) if p):
        if not any(c in piece for c in '~$*?['):
            continue
        value = shell_expanded(piece)
        if '**' in value:
            raise ValueError('recursive glob')  # zsh `**/` also matches no folder; never read as Python's glob
        matches = glob.glob(value) if any(c in value for c in '*?[') else [value]
        if len(matches) > limit:
            raise ValueError('too many matches')  # the split message, never a truncated reading
        found.extend(matches)
    return found


def main():
    live = False
    try:
        def timed_out(*_):
            if live:
                deny(UNSAFE)
            os._exit(0)
        signal.signal(signal.SIGALRM, timed_out)
        signal.alarm(12)
        if os.environ.get('FNL_AFK_HOOK', '').lower() in {'off', '0', 'false', 'no'}:
            return 0

        import io
        import json
        import shlex
        import time
        from contextlib import redirect_stdout
        from pathlib import Path

        raw = sys.stdin.buffer.read(256 * 1024)
        sys.dont_write_bytecode = True
        here = Path(__file__).resolve().parent
        sys.path.insert(0, str(here))
        import away_lease
        if len(raw) == 256 * 1024:
            if away_lease.live_lease(time.time()) is not None:
                deny(UNSAFE)  # input past the cap under a live lease cannot be judged
            return 0
        event = json.loads(raw)
        if not isinstance(event, dict) or event.get('tool_name') != 'Bash':
            return 0
        command = (event.get('tool_input') or {}).get('command')
        if not isinstance(command, str) or not command.strip():
            return 0

        if away_lease.live_lease(time.time()) is None:
            return 0
        live = True  # from here on every failure denies, as `check` answers `unsafe`

        try:
            argv = shlex.split(unquoted_newlines(command), comments=False, posix=True)
        except ValueError:
            deny(PARSE_MESSAGE)
            return 0
        if not argv:
            return 0
        if unreadable(command):
            deny(PARSE_MESSAGE)
            return 0
        cwd = event.get('cwd')
        if not isinstance(cwd, str) or not os.path.isdir(cwd):
            deny(UNSAFE)
            return 0
        script = here.parent / 'skills' / 'delegate' / 'scripts' / 'afk.py'
        if own_lease_command(argv, script, cwd):
            return 0
        os.chdir(cwd)
        sys.path.insert(0, str(script.parent))
        import afk

        if (glued_operator(unquoted_newlines(command), argv) or reparsed(argv, afk)
                or outside_allowlist(argv, afk)):
            deny(PARSE_MESSAGE)
            return 0
        try:
            paths = expanded_paths(argv)
        except ValueError:
            deny(PARSE_MESSAGE)  # a recursive glob or more matches than the hook reads: never truncated
            return 0
        expanded = [shell_expanded(word) for word in argv]
        if ((paths and afk.floored(None, paths, cwd)) or (expanded != argv and afk.floored(expanded, None, cwd))
                or floor_words(argv, paths, afk) or floor_words(expanded, paths, afk)):
            deny(parked('floor'))
            return 0
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            afk.main(['check', '--coordinator', 'claude', '--argv-json', json.dumps(argv)])
        answer = json.loads(buffer.getvalue().strip().splitlines()[-1])
        code = answer.get('code')
        if answer.get('tier') == 1:
            return 0  # no decision: the host's own permission rules still apply
        if isinstance(code, str) and code in afk.ENDED:
            return 0
        deny(parked(code if isinstance(code, str) and code.replace('-', '').isalpha() else 'unsafe'))
    except Exception:
        if live:
            try:
                deny(UNSAFE)
            except Exception:
                pass
    finally:
        try:
            signal.alarm(0)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
