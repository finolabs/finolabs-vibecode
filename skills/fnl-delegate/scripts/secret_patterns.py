"""Rule 4 thresholds and locatable spans, shared by brief lint and log scanning."""
import re
from bisect import bisect_right
from array import array

MAX_BYTES = 8 * 1024 * 1024
NAME = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
SENSITIVE = re.compile(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL', re.I)
ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))')
TOKEN = r'[A-Za-z0-9+/_=.-]'
PREFIX = re.compile(r'(?:sk-ant-|sk-|ghp_|gho_|ghu_|ghs_|github_pat_|glpat-|xoxb-|xoxp-|npm_|AKIA|ASIA|AIza)' + TOKEN + r'{16,}')
PRIVATE = re.compile(r'-----BEGIN[^\r\n]*PRIVATE KEY[^\r\n]*-----')
# Keep the complete candidate name, so an attacker cannot cause a valid suffix to be printed.
PAIR = re.compile(r'''(?<![^\s=:,'"{}\[\]])(?P<quote>['"]?)(?P<name>[^\s=:,'"{}\[\]]+)(?P=quote)[ \t]*[=:][ \t]*(?:"(?P<double>(?:\\.|[^"\\\r\n])*)"|'(?P<single>(?:\\.|[^'\\\r\n])*)'|(?P<bare>[^\s,}\]'" ]*))''')


def value_group(match):
    return next(group for group in ('double', 'single', 'bare') if match[group] is not None)

DUMP_MIN = 10
DUMP_LINES = 200


def normalized(text):
    """Strip ANSI while retaining an index back to every original character."""
    chunks, offsets, pos = [], array('I'), 0
    for match in ANSI.finditer(text):
        chunks.append(text[pos:match.start()])
        offsets.extend(range(pos, match.start()))
        pos = match.end()
    chunks.append(text[pos:])
    offsets.extend(range(pos, len(text)))
    return ''.join(chunks), offsets


def safe_name(name):
    return name if NAME.fullmatch(name) and not PREFIX.search(name) else None


def findings(text):
    clean, offsets = normalized(text)
    hits = []
    newlines = [i for i, char in enumerate(clean) if char == '\n']
    def add(kind, start, end, name=None):
        if end > start:
            hits.append(dict(kind=kind, line=bisect_right(newlines, start) + 1,
                             name=safe_name(name) if name else None,
                             start=offsets[start], end=offsets[end - 1] + 1))
    for match in PREFIX.finditer(clean):
        add('key', *match.span())
    private_end = 0
    for match in PRIVATE.finditer(clean):
        if match.start() < private_end:
            continue
        end_match = re.search(r'-----END[^\r\n]*PRIVATE KEY[^\r\n]*-----', clean[match.end():])
        end = match.end() + end_match.end() if end_match else len(clean)
        add('private_key', match.start(), end)
        private_end = end
    pairs = list(PAIR.finditer(clean))
    named = []
    for match in pairs:
        name = match['name']
        line = bisect_right(newlines, match.start()) + 1
        group = value_group(match)
        token = re.match(TOKEN + r'{16,}', match[group])
        if SENSITIVE.search(name) and token:
            start = match.start(group)
            add('named_token', start, start + token.end(), name)
        if NAME.fullmatch(name):
            named.append((line, match))
    # Union every qualifying window, including values before the tenth pair.
    left = 0
    windows = []
    for right, (line, _) in enumerate(named):
        while line - named[left][0] >= DUMP_LINES:
            left += 1
        if right - left + 1 >= DUMP_MIN:
            if windows and left <= windows[-1][1] + 1:
                windows[-1] = (windows[-1][0], right)
            else:
                windows.append((left, right))
    for index in (i for start, end in windows for i in range(start, end + 1)):
        match = named[index][1]
        # Remove the complete pair so a redacted dump is not itself a new dump.
        add('environment_dump', *match.span(), match['name'])
    return sorted(hits, key=lambda h: (h['line'], h['start'], h['kind']))


def redacted(text, hits):
    spans = []
    for hit in hits:
        start, end = hit.get('start'), hit.get('end')
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text):
            raise ValueError('unlocatable finding')
    for start, end in sorted((h['start'], h['end']) for h in hits):
        if spans and start <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(end, spans[-1][1]))
        else:
            spans.append((start, end))
    pieces, previous = [], 0
    for start, end in spans:
        pieces.extend((text[previous:start], '[REDACTED]'))
        previous = end
    pieces.append(text[previous:])
    return ''.join(pieces)
