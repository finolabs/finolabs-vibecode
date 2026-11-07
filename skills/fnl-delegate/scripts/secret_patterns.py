"""Rule 4 thresholds and locatable spans, shared by brief lint and log scanning."""
import re
import unicodedata
from bisect import bisect_right
from array import array

MAX_BYTES = 8 * 1024 * 1024
NAME = re.compile(r'^[A-Z][A-Z0-9_]{0,63}$')
SENSITIVE = re.compile(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PASS|AUTH|COOKIE|SESSION|PRIVATE', re.I)
ANSI = re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\))')
TOKEN = r'[A-Za-z0-9+/_=.-]'
PREFIX = re.compile(r'(?:sk-ant-|sk-|sk_live_|sk_test_|ghp_|gho_|ghu_|ghs_|github_pat_|glpat-|xoxb-|xoxp-|npm_|AKIA|ASIA|AIza)' + TOKEN + r'{16,}')
BEARER = re.compile(r'Authorization[ \t]*:[ \t]*Bearer[ \t]+' + TOKEN + r'{16,}', re.I)
SECRET_NAME = re.compile(r'(?:[A-F0-9]{20,}|[A-Z2-7]{20,})')
MAX_MATCHES = 1000
# Fixed header windows bound work at each marker on hostile single-line input.
PRIVATE = re.compile(r'-----BEGIN[^\r\n]{0,80}PRIVATE KEY[^\r\n]{0,80}-----')
PRIVATE_END = re.compile(r'-----END[^\r\n]{0,80}PRIVATE KEY[^\r\n]{0,80}-----')
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
    return name if NAME.fullmatch(name) and not PREFIX.search(name) and not SECRET_NAME.fullmatch(name) else None


class MatchLimit(Exception):
    pass


def findings(text):
    # Unknown escapes and invisible format characters cannot be shown safely.
    pos = 0
    for match in ANSI.finditer(text):
        if '\x1b' in text[pos:match.start()]:
            raise ValueError('unsupported escape')
        pos = match.end()
    if '\x1b' in text[pos:] or any(0x80 <= ord(c) <= 0x9f or unicodedata.category(c) == 'Cf'
                                  for c in text):
        raise ValueError('unsupported control')
    hits, seen = [], set()
    # Lines always refer to raw input, even when an OSC contains newlines.
    newlines = [i for i, char in enumerate(text) if char == '\n']
    count = 0

    def scan(clean, offsets):
        nonlocal count
        def matches(pattern):
            nonlocal count
            for match in pattern.finditer(clean):
                count += 1
                if count >= MAX_MATCHES:
                    raise MatchLimit()
                yield match

        def add(kind, start, end, name=None):
            if end <= start:
                return
            start, end = offsets[start], offsets[end - 1] + 1
            name = safe_name(name) if name else None
            identity = (kind, start, end, name)
            if identity not in seen:
                seen.add(identity)
                hits.append(dict(kind=kind, line=bisect_right(newlines, start) + 1,
                                 name=name, start=start, end=end))
        for pattern, kind in ((PREFIX, 'key'), (BEARER, 'bearer')):
            for match in matches(pattern):
                add(kind, *match.span())
        private_end = 0
        for match in matches(PRIVATE):
            if match.start() < private_end:
                continue
            end_match = PRIVATE_END.search(clean, match.end())
            end = end_match.end() if end_match else len(clean)
            add('private_key', match.start(), end)
            private_end = end
        named = []
        for match in matches(PAIR):
            name = match['name']
            line = bisect_right(newlines, offsets[match.start()]) + 1
            group = value_group(match)
            # Prefer false positives; quoted values may include spaces or punctuation.
            if SENSITIVE.search(name) and len(match[group]) >= 16:
                add('named_token', *match.span(group), name)
            if NAME.fullmatch(name):
                named.append((line, match))
        left, windows = 0, []
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
            add('environment_dump', *match.span(), match['name'])

    try:
        scan(text, range(len(text)))
        if '\x1b' in text:
            clean, offsets = normalized(text)
            scan(clean, offsets)
    except MatchLimit:
        # The unexamined tail must never reach show/redact as apparently safe text.
        return [dict(kind='match_limit', line=1, name=None, start=0, end=len(text))]
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
