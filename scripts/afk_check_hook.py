#!/usr/bin/env python3
"""Claude Code PreToolUse Bash hook for the away lease (CLAUDE.md, tenth scoped exception; docs/specs/afk-check-hook.md
and docs/specs/afk-hook-tokenizer.md).

While a valid, unexpired away lease exists, one tokenizer reads the Bash command in memory into command sites (each
with its assignments, argv and redirects), keeping the quoting of every character, and the sites are judged through
the same `afk.py check --coordinator claude --commands-json` code, in the hook's working folder. A Tier 3 answer, in
either mode, denies the call with one fixed message naming the code; a command outside the syntax the tokenizer reads
is denied with another fixed message, and once a lease is live any error denies as `unsafe`. With no live lease, or
on a Tier 1 answer, it prints nothing and returns no decision. The command text is never stored, logged or sent: only
what a `check` call keeps is written.
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


# ---- The tokenizer (docs/specs/afk-hook-tokenizer.md A) ----------------------------------------------------------------
# One pass over the raw text. Every character of a word keeps its quoting: `u` unquoted, `s` single-quoted (and a
# `$'...'` string with no backslash), `d` double-quoted, `e` escaped by a backslash. The grammar is the intersection of
# bash and zsh with default options; any form outside it raises Unreadable, which is the split message.

class Unreadable(ValueError):
    """A form outside the syntax the tokenizer reads: the split message."""


ASSIGNMENT_WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\+?=')


class Word:
    __slots__ = ('chars', 'segments', 'refs', 'marks')

    def __init__(self):
        self.chars = []     # (character, quoting)
        self.segments = []  # per character, the quoted or unquoted segment it came from: `"$HOM""E"` is two
        self.refs = []      # (start, end) of each `$HOME` or `${HOME}` reference, quoting `u` or `d`
        self.marks = []     # where each quote or escape began, an empty `""` included

    def mark(self):
        self.marks.append(len(self.chars))
        return self

    def add(self, chars, quoting, segment):
        for c in chars:
            self.chars.append((c, quoting))
            self.segments.append(segment)

    @property
    def text(self):
        return ''.join(c for c, _ in self.chars)

    @property
    def plain(self):
        """True when no quote or escape took part, an empty `""` included: only then can the word be a reserved word,
        a fd number or an unquoted heredoc delimiter."""
        return not self.marks and all(q == 'u' for _, q in self.chars)

    @property
    def globbed(self):
        return any(q == 'u' and c in '*?[' for c, q in self.chars)

    def assignment(self):
        """True when the word's `NAME=` or `NAME+=` part is unquoted, as both shells need for an assignment."""
        match = ASSIGNMENT_WORD.match(self.text)
        return bool(match) and all(m >= match.end() for m in self.marks)

    @property
    def anchored(self):
        """True when the word names a path from `/` or from an unquoted `~`: a quoted `'~'` is a folder named `~`
        in the working folder (class B of the PR 358 checkpoint)."""
        return bool(self.chars) and (self.chars[0][0] == '/' or self.chars[0] == ('~', 'u')
                                     or any(start == 0 for start, _end in self.refs))

    def paths(self, limit=200):
        """The paths the shell reads for this word, from its quoting: an unquoted leading `~` and `$HOME` expanded,
        an unquoted `*`, `?` or `[` a glob, every quoted character literal. Raises Unreadable for `**` or more
        matches than the hook reads."""
        import glob
        if not self.globbed:
            return [self.expanded()] if self.refs or self.chars[:1] == [('~', 'u')] else []
        raw_home = os.environ.get('HOME', '')
        home = glob.escape(raw_home)
        out, index, chars, prefix = [], 0, self.chars, ''
        if chars[0] == ('~', 'u'):
            end = next((k for k, (c, q) in enumerate(chars) if c == '/' and q == 'u'), len(chars))
            prefix = os.path.expanduser(''.join(c for c, _ in chars[:end]))
            out.append(glob.escape(prefix))
            index = end
        refs = dict(self.refs)
        if 0 in refs:
            prefix = raw_home
        while index < len(chars):
            if index in refs:
                out.append(home)
                index = refs[index]
                continue
            c, q = chars[index]
            out.append(c if q == 'u' and c in '*?[' else glob.escape(c))
            index += 1
        pattern = ''.join(out)
        if '**' in pattern:
            raise Unreadable('recursive glob')
        matches = glob.glob(pattern)
        if len(matches) > limit:
            raise Unreadable('too many matches')
        if any('HOME' in (match[len(prefix):] if match.startswith(prefix) else match) for match in matches):
            # `read -a HO?E` binds `HOME` in bash when a file `HOME` matches: a glob whose match names `HOME`
            # may rebind it, as a word holding `HOME` may (class 2 of the PR 358 checkpoint).
            raise Unreadable('home binding')
        return matches

    def expanded(self):
        """The word as the shell expands an unquoted leading `~` and `$HOME`; quoted text stays literal."""
        home = os.environ.get('HOME', '')
        out, index, chars = [], 0, self.chars
        if chars and chars[0] == ('~', 'u'):
            end = next((k for k, (c, q) in enumerate(chars) if c == '/' and q == 'u'), len(chars))
            out.append(os.path.expanduser(''.join(c for c, _ in chars[:end])))
            index = end
        refs = dict(self.refs)
        while index < len(chars):
            if index in refs:
                out.append(home)
                index = refs[index]
                continue
            out.append(chars[index][0])
            index += 1
        return ''.join(out)


# Longest match first; a form one shell reads differently, or that a shorter operator could misread, is refused.
REFUSED_OPERATORS = ('&>>', '>&|', '>>|', '&>|', '>>!', '|&', '&|', '&!', '>!', ';;', ';&', ';|')
REDIRECTS = ('<<<', '<<-', '<<', '<>', '<&', '>>', '>&', '>|', '&>', '<', '>')
OPERATOR_TEXT = sorted(REFUSED_OPERATORS + REDIRECTS + ('&&', '||', ';', '&', '|', '(', ')'), key=len, reverse=True)
NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
ZSH_NUMERIC_GLOB = re.compile(r'<[0-9]*-[0-9]*>')
NAMED_FD = re.compile(r'\{[A-Za-z_][A-Za-z0-9_]*\}')
DIGITS = re.compile(r'[0-9]+')  # ASCII only: the shells read no other digit as a fd


def joined(text, i, count):
    """(the next `count` characters from `i` as the shell reads them, the raw index after each one): every
    backslash-newline is dropped, so a lookahead sees the joined text (class A of the PR 358 checkpoint). Only
    called outside quotes."""
    chars, ends = [], []
    while i < len(text) and len(chars) < count:
        if text.startswith('\\\n', i):
            i += 2
            continue
        chars.append(text[i])
        i += 1
        ends.append(i)
    return ''.join(chars), ends


def lex(text):
    """[(kind, value)] tokens: ('word', Word), ('op', operator or newline), ('redir', (fd, operator, heredoc)). A
    heredoc is a dict holding its delimiter, whether it was quoted and its body, read at the newline after it."""
    tokens, pending, word, i, n = [], [], None, 0, len(text)
    segment = 0  # a new number at every quote, escape and return to unquoted text
    continued = False  # a continuation came after the last character: `2\` + newline + `>` is no fd in zsh

    def end_word():
        nonlocal word
        if word is not None:
            if tokens and tokens[-1][0] == 'redir' and tokens[-1][1][2] is not None \
                    and 'delimiter' not in tokens[-1][1][2]:
                heredoc = tokens[-1][1][2]
                if not word.chars or any(q == 'u' and c in '$`' for c, q in word.chars):
                    raise Unreadable('heredoc delimiter')
                heredoc['delimiter'], heredoc['quoted'] = word.text, not word.plain
                pending.append(heredoc)
            tokens.append(('word', word))
            word = None

    while i < n:
        if text.startswith('\\\n', i):
            i += 2  # a continuation: the shell joins the two lines, and every lookahead below reads them joined
            continued = True
            continue
        c, glued, continued = text[i], not continued, False
        if c == '\\':
            if i + 1 >= n:
                raise Unreadable('trailing backslash')
            word = (word or Word()).mark()
            word.add(text[i + 1], 'e', segment + 1)
            segment += 2
            i += 2
            continue
        if c == "'":
            end = text.find("'", i + 1)
            if end < 0:
                raise Unreadable('unbalanced quote')
            word = (word or Word()).mark()
            word.add(text[i + 1:end], 's', segment + 1)
            segment += 2
            i = end + 1
            continue
        if c == '"':
            word = (word or Word()).mark()
            segment += 1
            j = i + 1
            while True:
                if j >= n:
                    raise Unreadable('unbalanced quote')
                ch = text[j]
                if ch == '"':
                    break
                if ch == '\\' and j + 1 < n:
                    nxt = text[j + 1]
                    if nxt == '\n':
                        j += 2
                        continue
                    if nxt in '$`"\\':
                        word.add(nxt, 'e', segment + 1)
                        segment += 2
                        j += 2
                        continue
                word.add(ch, 'd', segment)
                j += 1
            segment += 1
            i = j + 1
            continue
        ahead, ends = joined(text, i, 2)
        if ahead == "$'":
            start = ends[1]
            end = text.find("'", start)
            if end < 0 or '\\' in text[start:end]:
                raise Unreadable('ansi-c quote')  # its escapes could hide a name or a path
            word = (word or Word()).mark()
            word.add(text[start:end], 's', segment + 1)
            segment += 2
            i = end + 1
            continue
        if ahead == '$"':
            raise Unreadable('locale string')  # bash and zsh expand `$"..."` differently
        if c in ' \t':
            end_word()
            i += 1
            continue
        if c == '\n':
            end_word()
            tokens.append(('op', '\n'))
            i = heredoc_bodies(text, i + 1, pending)
            continue
        if c == '#' and word is None:
            end = text.find('\n', i)
            i = n if end < 0 else end  # a comment runs to the end of the line
            continue
        if c in ';&|<>()':
            ahead, ends = joined(text, i, 3)
            op = next(o for o in OPERATOR_TEXT if ahead.startswith(o))
            after = ends[len(op) - 1]  # the raw index after the operator, continuations inside it included
            if op in REFUSED_OPERATORS:
                raise Unreadable('operator')
            if after - i != len(op):
                # bash joins `&\` + newline + `&` into `&&`, zsh reads `&` and then a parse error (the oracle): a
                # continuation inside any operator of two or more characters gets the split message.
                raise Unreadable('continuation in an operator')
            if op == '(':
                if word is not None:
                    raise Unreadable('paren in a word')  # zsh glob alternation, qualifiers, an array
                if ahead.startswith('(('):
                    raise Unreadable('arithmetic')
                tokens.append(('op', '('))
                i = after
                continue
            if op in REDIRECTS:
                if op == '<' and ZSH_NUMERIC_GLOB.match(joined(text, i, 64)[0]):
                    raise Unreadable('zsh numeric glob')
                fd = None
                if word is not None and word.plain and DIGITS.fullmatch(word.text):
                    if not glued:
                        raise Unreadable('fd number')  # bash joins `2\` + newline + `>` into a fd, zsh does not
                    if len(word.text) > 1:
                        raise Unreadable('fd number')  # bash reads `12>` as a fd, zsh as an argument
                    if op != '&>':
                        fd, word = word.text, None
                elif word is not None and word.plain and NAMED_FD.fullmatch(word.text):
                    raise Unreadable('named fd')
                end_word()
                i = after
                if joined(text, i, 1)[0] == '(':
                    raise Unreadable('process substitution')
                heredoc = {'quoted': False, 'body': None, 'strip': op == '<<-'} if op in ('<<', '<<-') else None
                tokens.append(('redir', (fd, op, heredoc)))
                continue
            end_word()
            tokens.append(('op', op))
            i = after
            continue
        word = word or Word()
        word.add(c, 'u', segment)
        i += 1
    end_word()
    if pending:
        raise Unreadable('heredoc without a body')
    return tokens


def heredoc_bodies(text, i, pending):
    """Read the body of each pending heredoc from `i`, the start of the next line; returns the index after the last
    delimiter line. A heredoc with no closing delimiter is refused."""
    while pending:
        heredoc = pending.pop(0)
        lines = []
        while True:
            if i >= len(text):
                raise Unreadable('heredoc without its delimiter')
            end = text.find('\n', i)
            line = text[i:] if end < 0 else text[i:end]
            i = len(text) if end < 0 else end + 1
            if not heredoc['quoted'] and (len(line) - len(line.rstrip('\\'))) % 2:
                raise Unreadable('heredoc continuation')  # the shell joins the next line before it looks for the end
            if heredoc['strip']:
                line = line.lstrip('\t')
            if line == heredoc['delimiter']:
                break
            lines.append(line)
        heredoc['body'] = ''.join(line + '\n' for line in lines)
    return i


def check_word(word):
    """Raise Unreadable for any form the hook cannot reproduce in both shells; record `$HOME` references."""
    chars = word.chars
    for k, (c, q) in enumerate(chars):
        if q in 'se':
            continue
        if c == '`':
            raise Unreadable('command substitution')
        if c == '$':
            segments = word.segments
            if k + 1 >= len(chars) or segments[k + 1] != segments[k]:
                continue  # a lone `$` before a quote or at the end is literal
            nxt = chars[k + 1][0]
            if nxt == '{':
                end = next((j for j in range(k + 2, len(chars)) if segments[j] != segments[k] or chars[j][0] == '}'),
                           None)
                if (end is None or segments[end] != segments[k]
                        or ''.join(ch for ch, _ in chars[k + 2:end]) != 'HOME'):
                    raise Unreadable('parameter')
                end += 1
            elif nxt == '_' or nxt.isalpha():
                end = k + 1
                while (end < len(chars) and segments[end] == segments[k]
                       and (chars[end][0] == '_' or chars[end][0].isalnum())):
                    end += 1
                if ''.join(ch for ch, _ in chars[k + 1:end]) != 'HOME':
                    raise Unreadable('variable')
            else:
                raise Unreadable('parameter')  # special, positional, arithmetic, substitution, zsh forms
            if end < len(chars) and chars[end][0] != '/':
                raise Unreadable('home boundary')  # `$HOME:t`, `$HOME[1]`, `${HOME}rc`
            word.refs.append((k, end))
            continue
        if q != 'u':
            continue
        if c == '{':
            end = next((j for j in range(k + 1, len(chars)) if chars[j] == ('}', 'u')), None)
            inner = chars[k + 1:end] if end is not None else []
            if any(ch == ',' and qq == 'u' for ch, qq in inner) or '..' in ''.join(ch for ch, qq in inner if qq == 'u'):
                raise Unreadable('brace expansion')
        if c == '=' and k == 0:
            raise Unreadable('zsh equals')
        if c == '~' and k == 0:
            end = next((j for j in range(len(chars)) if chars[j] == ('/', 'u')), len(chars))
            prefix = chars[1:end]
            if any(qq != 'u' for _, qq in prefix) or (prefix and prefix[0][0] in '+-0123456789'):
                raise Unreadable('tilde')
        if c == '~' and k > 0 and chars[k - 1] in (('=', 'u'), (':', 'u')):
            # bash expands `~` after `=` in any word (`--p=~/x`) and after `:` in an assignment, zsh only in an
            # assignment: the hook expands a leading `~` only, so every other unquoted `~` after them is refused.
            raise Unreadable('tilde')
    # An allowlist, not a list of binding forms (class C of the PR 358 checkpoint): `HOME` may appear only inside a
    # `$HOME` or `${HOME}` reference, so no assignment, `for`, `read -a`, `printf -v`, `export` or other form in
    # the call can change what the hook expands it to.
    bare, index, refs = [], 0, dict(word.refs)
    while index < len(chars):
        if index in refs:
            bare.append(' ')
            index = refs[index]
            continue
        bare.append(chars[index][0])
        index += 1
    if 'HOME' in ''.join(bare):
        raise Unreadable('home binding')


RESERVED = {'if', 'then', 'elif', 'else', 'fi', 'while', 'until', 'do', 'done', '{', '}', '!', 'for'}
REFUSED_WORDS = {'case', 'esac', 'select', 'function', 'coproc', 'repeat', 'foreach', '[[', ']]'}
CLOSERS = {'then', 'elif', 'else', 'fi', 'do', 'done', '}'}
LOOPS = {'while', 'for'}


class Site:
    """One command site: assignments, words and redirects (fd, operator, target word, heredoc), the operator that
    ends it, whether a pipe feeds it (`piped`) or takes its output (`pipes_out`), whether the pipe after it feeds a
    compound command, whether it sits in a loop (`repeated`) and whether it came from a heredoc body."""
    __slots__ = ('assignments', 'words', 'redirects', 'separator', 'piped', 'pipes_out', 'next_compound',
                 'repeated', 'body')

    def __init__(self, piped, repeated):
        self.assignments, self.words, self.redirects = [], [], []
        self.separator, self.piped, self.pipes_out, self.next_compound = None, piped, False, False
        self.repeated, self.body = repeated, False

    @property
    def argv(self):
        return [w.text for w in self.words]

    @property
    def full(self):
        return [w.text for w in self.assignments] + self.argv


def parse(text):
    """(sites, list words) for a command text: every command site with its assignments, words and redirects, and
    the `for` list words the floor reads as paths. Raises Unreadable for anything outside the grammar."""
    tokens = lex(text)
    sites, listed, stack = [], [], []
    state = {'site': None, 'last': 'start', 'piped': False, 'closed': None}

    def repeated():
        return any(frame['kind'] in LOOPS for frame in stack)

    def piped_now():
        return state['piped'] or any(frame['piped'] for frame in stack)

    def new_site():
        state['site'] = Site(piped_now(), repeated())
        state['piped'] = False

    def finish(separator):
        site = state['site']
        if site is not None and site.redirects and not site.words:
            raise Unreadable('redirect only')  # zsh runs `$NULLCMD` (`cat`) for it, bash runs nothing
        if site is not None and site.argv == ['exec'] and (site.piped or site.pipes_out or separator == '|'):
            # zsh's child for `exec 3<f | ok A; ok B` goes on to run `ok A; ok B` a second time, and a bare `exec`
            # last in a pipeline keeps its descriptors in zsh's own shell only (the generated oracle, 18/11/2026).
            raise Unreadable('exec in a pipeline')
        if site is not None:
            site.separator = separator
            sites.append(site)
            if stack:
                stack[-1]['had'] = True
            state['site'] = None

    def opened(kind, phase=None):
        stack.append({'kind': kind, 'phase': phase, 'had': False, 'piped': piped_now(), 'start': len(sites)})
        if state['piped'] and sites:
            sites[-1].next_compound = True  # the pipe feeds a compound command
        state['piped'] = False

    def closed(kind, phases):
        if not stack or stack[-1]['kind'] != kind or stack[-1]['phase'] not in phases or not stack[-1]['had']:
            raise Unreadable('compound')
        frame = stack.pop()
        if stack:
            stack[-1]['had'] = True
        state['closed'] = frame

    def phase(kind, phases, new):
        top = stack[-1] if stack else None
        if not top or top['kind'] != kind or top['phase'] not in phases or not top['had']:
            raise Unreadable('compound')
        top['phase'], top['had'] = new, False

    index = 0
    while index < len(tokens):
        kind, value = tokens[index]
        index += 1
        last = state['last']
        if kind == 'word':
            check_word(value)
            if state['site'] is None:
                keyword = value.text if value.plain else None
                if last == 'close' and keyword not in CLOSERS:
                    raise Unreadable('word after a compound command')
                if keyword in REFUSED_WORDS:
                    raise Unreadable('compound')
                if keyword in RESERVED:
                    if keyword == 'if':
                        opened('if', 'cond')
                    elif keyword in {'while', 'until'}:
                        opened('while', 'cond')
                    elif keyword == '{':
                        opened('brace')
                    elif keyword == '!':
                        if last not in {'start', 'sep', 'keyword', 'andor', 'pipe'}:
                            raise Unreadable('negation')
                    elif keyword == 'then':
                        phase('if', {'cond', 'elif'}, 'then')
                    elif keyword == 'elif':
                        phase('if', {'then'}, 'elif')
                    elif keyword == 'else':
                        phase('if', {'then'}, 'else')
                    elif keyword == 'fi':
                        closed('if', {'then', 'else'})
                    elif keyword == 'do':
                        phase('while', {'cond'}, 'body')
                    elif keyword == 'done':
                        closed('for' if stack and stack[-1]['kind'] == 'for' else 'while', {'body'})
                    elif keyword == '}':
                        closed('brace', {None})
                    elif keyword == 'for':
                        index = for_header(tokens, index, listed)
                        opened('for', 'body')
                    state['last'] = 'close' if keyword in {'fi', 'done', '}'} else 'keyword'
                    continue
                new_site()
            site = state['site']
            if not site.words and value.assignment():
                site.assignments.append(value)
            else:
                site.words.append(value)
            state['last'] = 'cmd'
            continue
        if kind == 'redir':
            fd, op, heredoc = value
            if last == 'close':
                raise Unreadable('redirect on a compound command')
            if index >= len(tokens) or tokens[index][0] != 'word':
                raise Unreadable('redirect without a target')
            target = tokens[index][1]
            index += 1
            check_word(target)
            if state['site'] is None:
                new_site()
            state['site'].redirects.append((fd, value[1], target, heredoc))
            state['last'] = 'cmd'
            continue
        op = value
        if op == '(':
            if state['site'] is not None or last in {'cmd', 'close'}:
                raise Unreadable('paren')
            opened('subshell')
            state['last'] = 'keyword'
            continue
        if op == ')':
            finish(op)
            closed('subshell', {None})
            state['last'] = 'close'
            continue
        if op == '\n':
            if last in {'pipe', 'andor'}:
                continue  # the command goes on after `|`, `&&` or `||` and a newline
            finish(';')
            if last in {'cmd', 'close'}:
                state['last'] = 'sep'
            state['closed'] = None
            continue
        if last not in {'cmd', 'close'}:
            raise Unreadable('operator without a command')
        if op == '|':
            if state['site'] is not None:
                state['site'].pipes_out = True
            elif state['closed'] is not None:
                for inner in sites[state['closed']['start']:]:
                    inner.pipes_out = True  # a compound command whose output feeds a pipe
            finish(op)
            state['piped'], state['last'] = True, 'pipe'
        else:
            finish(op)
            state['last'] = 'andor' if op in {'&&', '||'} else 'sep'
        state['closed'] = None
    finish(None)
    if stack or state['last'] in {'pipe', 'andor'}:
        raise Unreadable('unfinished command')
    return sites, listed


def for_header(tokens, index, listed):
    """Read `NAME in words;` (and newlines) up to `do`; the list words go to `listed`. Returns the index after `do`."""
    if index + 1 >= len(tokens) or tokens[index][0] != 'word' or tokens[index + 1][0] != 'word':
        raise Unreadable('for')
    name, keyword = tokens[index][1], tokens[index + 1][1]
    check_word(name)  # `for HOME in ...` is refused by the HOME allowlist
    if not name.plain or not NAME.fullmatch(name.text) or not keyword.plain or keyword.text != 'in':
        raise Unreadable('for')  # `for x; do`, `for x (a b)`, `for ((`
    index += 2
    while index < len(tokens) and tokens[index][0] == 'word':
        check_word(tokens[index][1])
        listed.append(tokens[index][1])
        index += 1
    if index >= len(tokens) or tokens[index] not in (('op', ';'), ('op', '\n')):
        raise Unreadable('for')
    index += 1
    while index < len(tokens) and tokens[index] == ('op', '\n'):
        index += 1
    if index >= len(tokens) or tokens[index][0] != 'word' or not tokens[index][1].plain or tokens[index][1].text != 'do':
        raise Unreadable('for')
    return index + 1


# ---- Judging the sites (docs/specs/afk-hook-tokenizer.md B) ------------------------------------------------------------

SHELLS = {'sh', 'bash', 'zsh', 'dash', 'ksh', 'mksh', 'fish', 'csh', 'tcsh'}
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
SHELL_VALUED = {'-o', '+o', '-O', '+O'}
DIRECTORY_CHANGES = {'cd', 'pushd', 'popd', 'chdir'}
# Programs that build a command or pick its files from data that exists only at run time (stdin, a match): the hook
# cannot know what they run, so a command holding one is never read.
RUNTIME_PROGRAMS = {'xargs'}
RUNTIME_ACTIONS = {'find': EXEC_FLAGS | {'-delete'}, 'fd': {'-x', '-X', '--exec', '--exec-batch'},
                   'fdfind': {'-x', '-X', '--exec', '--exec-batch'}}
# Decision 3: a heredoc or `<<<` body is data only for these receivers, and only when every program downstream of
# it through pipes is one too; any other receiver has its body judged line by line as commands.
DATA_READERS = {'cat', 'tee', 'wc', 'head', 'tail', 'sort', 'grep'}
# Decision 7: file operands of these readers, which execute nothing, are exempt from the base-name floor rule.
NAME_EXEMPT_READERS = {'cat', 'head', 'tail', 'wc', 'grep', 'ls', 'stat', 'file', 'sort'}
KINDS = {'<': 'read', '>': 'write', '>|': 'write', '&>': 'write', '>&': 'write', '>>': 'append', '<>': 'readwrite'}
BODIES = ('<<', '<<-', '<<<')


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
    if base in SHELLS:
        if any(w == '-s' or re.fullmatch(r'-[A-Za-z]*c[A-Za-z]*', w) for w in words):
            return True
        rest, index = [], 0
        while index < len(words):
            word = words[index]
            index += 2 if word in SHELL_VALUED else 1
            if not word.startswith(('-', '+')):
                rest.append(word)
        return not rest  # no script operand: the shell reads code from stdin, whatever its redirects are
    return False


def code_reader(program, afk):
    """True for a program that runs what it reads: a shell, an interpreter, a program of the inline-code tables, or
    `xargs`."""
    if not isinstance(program, str):
        return False
    base = os.path.basename(program)
    stem = re.sub(r'[0-9.]+$', '', base) or base
    return (base in SHELLS or base in afk.SHELLS or base in RUNTIME_PROGRAMS
            or any(name in afk.INTERPRETERS or name in afk.INLINE_FLAGS for name in (base, stem)))


def wrapper_chain(argv, afk):
    """True when a wrapper in command position (the program, then the program each wrapper runs) carries a flag the
    shared table may misread. Words after the program that runs are its arguments, so `codex exec -s` is Codex's
    subcommand, not the shell's `exec`."""
    wrappers = afk.PREFIX_WORDS | afk.FILE_PREFIXES
    index = 0
    while index < len(argv):
        base = os.path.basename(argv[index])
        if afk.ASSIGNMENT.fullmatch(argv[index]) and '/' not in argv[index].split('=', 1)[0]:
            index += 1
            continue
        if base == 'env':
            index += 1
            while index < len(argv) and afk.ASSIGNMENT.fullmatch(argv[index]):
                index += 1
            if index < len(argv) and argv[index].startswith('-'):
                return False  # `env` with options is read as the command `env`, which the floor denies
            continue
        if base == 'pnpm' and argv[index + 1:index + 2] == ['exec']:
            index += 2
            continue
        if base in RUNTIME_PROGRAMS:
            return True  # `xargs` runs a command built from run-time data
        if base not in wrappers:
            return False
        if base in afk.FILE_PREFIXES:
            if any(w.startswith('-') for w in argv[index + 1:index + 4]):
                return True
            index += 2  # the lock or typescript file
            continue
        allowed, index = WRAPPER_FLAGS.get(base, {}), index + 1
        while index < len(argv) and argv[index].startswith('-') and argv[index] != '-':
            if argv[index] not in allowed:
                return True  # a wrapper flag `commands_of` may misread
            index += 1 + allowed[argv[index]]
        if base == 'timeout' and index < len(argv) and re.fullmatch(r'[0-9.]+[smhd]?', argv[index]):
            index += 1
        if base == 'nice' and index < len(argv) and re.fullmatch(r'-?[0-9]+', argv[index]):
            index += 1
    return False


def site_programs(argv, afk):
    """[(program, words, inline)] for every command `commands_of` reads out of one site's argv, over every reading."""
    return [(program, list(words), inline)
            for reading in afk.READINGS
            for program, words, _env, inline, _pattern in afk.commands_of(argv, full=True, split_patterns=reading)]


def reparsed(argv, afk):
    """True when one site runs code a shell parses again, changes the shell's glob options, has a program name holding
    an expansion, a glob or a brace, a wrapper flag the shared table may misread, or a program fed by run-time data
    (every reading, wrappers, inline code and a `find -exec` command included)."""
    if any(word in OPAQUE_WORDS for word in argv) or wrapper_chain(argv, afk):
        return True
    for program, words, inline in site_programs(argv, afk):
        if inline:
            continue
        if bad_program(program, words):
            return True
        base = os.path.basename(program) if isinstance(program, str) else None
        if base in RUNTIME_PROGRAMS:
            return True
        actions = RUNTIME_ACTIONS.get(base)
        if actions and any(w in actions or (w.startswith('--exec') and base != 'find') for w in words):
            return True
        for index, word in enumerate(words):
            if word in EXEC_FLAGS and index + 1 < len(words):
                rest = [w for w in words[index + 1:] if w not in {';', '\\;', '+', '{}'}]
                if rest and reparsed(rest, afk):
                    return True
    return False


def name_exempt(argv):
    """Indexes of the file operands of a data reader that executes nothing (decision 7): words after the program that
    are neither options nor a word after an option (which may be its value), the pattern of `grep` excluded."""
    if not argv or os.path.basename(argv[0]) not in NAME_EXEMPT_READERS:
        return set()
    operands, ended = [], False
    for index in range(1, len(argv)):
        word = argv[index]
        if not ended and word == '--':
            ended = True
            continue
        if not ended and (word.startswith('-') and word != '-'
                          or index > 1 and argv[index - 1].startswith('-') and argv[index - 1] not in {'-', '--'}):
            continue
        operands.append(index)
    if os.path.basename(argv[0]) == 'grep' and not any(
            w in {'-e', '--regexp', '-f', '--file'} or w.startswith(('--regexp=', '--file=')) for w in argv[1:]):
        operands = operands[1:]  # the first operand is the pattern
    return set(operands)


def floor_words(argv, paths, afk, exempt=frozenset()):
    """True when any word that is not a commit or pull request text value, or any expanded path, names a credential
    command that is a floor in every use (`printenv`, `security`, ...), or a credential command with subcommands is
    followed anywhere by one of them (`gh ... auth`), wherever it stands: a wrapper or its flags cannot hide it.
    Words at the indexes in `exempt` (decision 7) skip only the every-use rule."""
    names = {name for name, subs in afk.CREDENTIAL_COMMANDS.items() if subs is None}
    stripped, _texts = afk.open_texts(argv)
    if len(stripped) != len(argv):
        exempt = frozenset()
    words = [w for w in stripped if isinstance(w, str)]
    expanded = [os.path.basename(p) for p in paths if isinstance(p, str)]
    bases = [os.path.basename(w) for w in words]
    if any(b in names for i, b in enumerate(bases) if i not in exempt) or any(b in names for b in expanded):
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
            if position < len(pair) and base == pair[position]:
                position += 1
        if position == len(pair):
            return True
    return False


LEASE_COMMANDS = {'stop', 'log', 'review', 'effective', 'rules', 'check', 'packet-check'}
SAFE_ARGUMENT = re.compile(r'[A-Za-z0-9 ._,:=/@+%-]*')


def own_lease_command(argv, script, cwd):
    """True for `python3 [-I] <this install's afk.py> <lease command> ...` with every argument made only of letters,
    digits, spaces and `._,:=/@+%-`. The interpreter is a bare `python3` or `python` or a path to the hook's own
    interpreter; the script path is resolved against the Bash tool's `cwd`. The caller applies it only to a call with
    exactly one site and no assignments or redirects, so it never exempts a sibling site."""
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
    if len(rest) < 2 or rest[1] not in LEASE_COMMANDS:
        return False
    if not all(SAFE_ARGUMENT.fullmatch(word) for word in rest[1:]):
        return False  # a word bash could expand, redirect or split is judged like any command
    try:
        return os.path.realpath(os.path.join(cwd, rest[0])) == os.path.realpath(script)
    except (OSError, ValueError):
        return False


VARIABLE = re.compile(r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))')
HOME_IN_BODY = re.compile(r'\$(?:\{HOME\}|HOME(?![A-Za-z0-9_]))')


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
            raise Unreadable('recursive glob')  # zsh `**/` also matches no folder; never read as Python's glob
        matches = glob.glob(value) if any(c in value for c in '*?[') else [value]
        if len(matches) > limit:
            raise Unreadable('too many matches')  # the split message, never a truncated reading
        found.extend(matches)
    return found


def body_check(body):
    """Raise Unreadable for an expansion in an unquoted-delimiter heredoc body other than `$HOME`, which the shell
    expands in it as in a double-quoted word."""
    index = 0
    while index < len(body):
        c = body[index]
        if c == '\\':
            index += 2
            continue
        if c == '`':
            raise Unreadable('command substitution')
        if c == '$':
            match = HOME_IN_BODY.match(body, index)
            if match:
                if body[match.end():match.end() + 1] in (':', '['):
                    raise Unreadable('home boundary')
                index = match.end()
                continue
            nxt = body[index + 1:index + 2]
            if nxt and (nxt.isalnum() or nxt in '_{(@*#?-$![^=~+'):
                raise Unreadable('parameter')
        index += 1


def data_receiver(site):
    """True when a site reads its input as data (decision 3): no wrapper, a program of the closed list, or
    `git commit -F -`, `git tag -F -`, `gh ... --body-file -`."""
    argv = site.argv
    if not argv:
        return False
    base = os.path.basename(argv[0])
    if base in DATA_READERS:
        return True
    if base == 'git' and argv[1:2] in (['commit'], ['tag']):
        return any(w in {'-F', '--file'} and argv[i + 2:i + 3] == ['-'] or w in {'--file=-', '-F-'}
                   for i, w in enumerate(argv[1:]))
    if base == 'gh':
        return any(w == '--body-file' and argv[i + 2:i + 3] == ['-'] or w == '--body-file=-'
                   for i, w in enumerate(argv[1:]))
    return False


def data_body(sites, index):
    """True when the input of sites[index] stays data: it and every program downstream of it through pipes are data
    receivers, and no compound command takes part in the pipeline."""
    site = sites[index]
    if not data_receiver(site):
        return False
    while site.separator == '|':
        if site.next_compound or index + 1 >= len(sites):
            return False
        index += 1
        site = sites[index]
        if not data_receiver(site):
            return False
    return not site.pipes_out  # a compound command around it feeds a pipe


def judged(command, depth=0):
    """(sites, data words, list words) for a command, heredoc and here-string bodies resolved (decision 3): a data
    body's words join the data the floor reads, any other body is read line by line as commands and its sites join
    the list. Raises Unreadable for the split message."""
    if depth > 3:
        raise Unreadable('nested body')
    sites, listed = parse(command)
    words, extra = [w.text for w in listed], []
    for index, site in enumerate(sites):
        for _fd, op, target, heredoc in site.redirects:
            if op not in BODIES:
                continue
            body = target.text if op == '<<<' else heredoc['body']
            expands = op != '<<<' and not heredoc['quoted']
            if expands:
                body_check(body)
            if data_body(sites, index):
                words.extend(body.split())
                if expands:
                    words.extend(shell_expanded(w) for w in body.split())
                continue
            inner, inner_words, inner_listed = judged(body, depth + 1)
            for item in inner:
                item.body, item.repeated = True, item.repeated or site.repeated
            extra.extend(inner)
            words.extend(inner_words)
            listed.extend(inner_listed)
    return sites + extra, words, listed


READABLE = ('<', '<>', '<&') + BODIES  # every redirect that gives the program something to read


def supplies_input(fd, op):
    """True for a redirect that gives the program readable input, on stdin or on any other fd (`node /dev/fd/3
    3<x.js`): a file read (`<`, `<>`), a duplication of a descriptor that may be readable (`<&N`, and `0>&N`,
    which puts it on stdin), a heredoc and a here-string, with or without a fd prefix. The one predicate the
    code-reader rule uses (class 3 of the PR 358 checkpoint)."""
    return op in READABLE or (op == '>&' and fd == '0')


def targets_of(site):
    """[(kind, target, word)] for every redirect target that names a file (fd duplications and bodies left out)."""
    found = []
    for _fd, op, target, _heredoc in site.redirects:
        if op in BODIES:
            continue
        if op in ('<&', '>&') and (DIGITS.fullmatch(target.text) or target.text == '-'):
            if not target.plain:
                raise Unreadable('quoted descriptor')  # `>&'1'`: a fd or a file, read from the quote-removed text
            continue
        if op == '<&':
            raise Unreadable('input duplication')
        found.append((KINDS[op], target.expanded(), target))
    return found


def call_wide(sites, listed, afk):
    """True when a rule that spans commands applies (B): a directory change with an unanchored glob anywhere in the
    call (anchoring read from the word's quoting), a pipe into a shell, `xargs` or a code reader, any redirect that
    supplies input (`supplies_input`) feeding a code reader, or a bare `exec` that opens one for the rest of a call
    holding a code reader."""
    programs = [[p for p, _w, inline in site_programs(site.full, afk) if not inline] if site.full else []
                for site in sites]
    changes = any(isinstance(p, str) and os.path.basename(p) in DIRECTORY_CHANGES for found in programs for p in found)
    changes = changes or any(site.words and os.path.basename(site.words[0].text) in DIRECTORY_CHANGES for site in sites)
    if changes:
        words = [w for site in sites for w in site.assignments + site.words + [t for _f, _o, t, _h in site.redirects]]
        if any(w.globbed and not w.anchored for w in words + listed):
            return True
    readers = [any(code_reader(p, afk) for p in found) for found in programs]
    for site, reader in zip(sites, readers):
        if site.piped and reader:
            return True
        if reader and any(supplies_input(fd, op) for fd, op, _t, _h in site.redirects):
            return True
        # `exec 3<x.js` with no program keeps the descriptor open for every later site (`node /dev/fd/3`).
        if (site.argv == ['exec'] and any(readers)
                and any(supplies_input(fd, op) or fd == '0' for fd, op, _t, _h in site.redirects)):
            return True
    return False


def site_entries(sites, words, cwd, afk):
    """The `--commands-json` entries for the sites, or None when any of them, a redirect target or a data word
    touches the floor. Raises Unreadable for a recursive glob, more matches than the hook reads or an ambiguous
    redirect."""
    import glob
    entries = []
    for site in sites:
        argv = site.full
        objects = site.assignments + site.words
        # Both readings: the word's own quoting (exact), and every whitespace or operator piece of its text (wider:
        # it also reads a path inside inline code or a text value).
        exact = [[p for p in w.paths()] for w in objects]
        paths = expanded_paths(argv) + [p for found in exact for p in found]
        targets = []
        for kind, target, word in targets_of(site):
            if word.globbed:
                matches = word.paths()  # from the word's quoting: a quoted `'~'` or `*` stays literal
                if len(matches) > 1:
                    raise Unreadable('ambiguous redirect')  # bash refuses it, zsh opens every match
                targets.extend((kind, match) for match in matches or [target])
            else:
                targets.append((kind, target))
        exempt = name_exempt(argv) if not site.assignments else set()
        spared = {p for i in exempt for p in expanded_paths([argv[i]]) + exact[i]}
        named = [p for p in paths if p not in spared] + [t for _k, t in targets]
        expanded = [shell_expanded(word) for word in argv]
        quoted = [w.expanded() for w in objects]
        if ((paths and afk.floored(None, paths, cwd))
                or (targets and afk.floored(None, [t for _k, t in targets], cwd))
                or any(e != argv and afk.floored(e, None, cwd) for e in (expanded, quoted))
                or any(floor_words(e, named, afk, exempt) for e in (argv, expanded, quoted))):
            return None
        entries.append({'assignments': [w.text for w in site.assignments], 'argv': site.argv,
                        'redirects': [[kind, target] for kind, target in targets], 'repeated': site.repeated})
    if words:
        paths = expanded_paths(words)
        if afk.floored(None, words + paths, cwd) or floor_words(words, paths, afk):
            return None
    return entries


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
            sites, words, listed = judged(command)
        except Unreadable:
            deny(PARSE_MESSAGE)
            return 0
        if not sites:
            return 0
        cwd = event.get('cwd')
        if not isinstance(cwd, str) or not os.path.isdir(cwd):
            deny(UNSAFE)
            return 0
        script = here.parent / 'skills' / 'delegate' / 'scripts' / 'afk.py'
        only = sites[0]
        if (len(sites) == 1 and not only.assignments and not only.redirects
                and own_lease_command(only.argv, script, cwd)):
            return 0
        os.chdir(cwd)
        sys.path.insert(0, str(script.parent))
        import afk

        try:
            if any(reparsed(site.full, afk) for site in sites if site.full) or call_wide(sites, listed, afk):
                deny(PARSE_MESSAGE)
                return 0
            entries = site_entries(sites, words, cwd, afk)
        except Unreadable:
            deny(PARSE_MESSAGE)
            return 0
        if entries is None:
            deny(parked('floor'))
            return 0
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            afk.main(['check', '--coordinator', 'claude', '--commands-json', json.dumps(entries)])
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
