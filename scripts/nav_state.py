#!/usr/bin/env python3
"""Collect current navigator anchors and metadata; screen payloads and verify reports."""
import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_root as dr

MAX_FILE_BYTES = 512 * 1024
MAX_CRITERIA = 200
MAX_LEDGER_IDS = 200
STATUS_WORDS = ('draft', 'accepted', 'in progress', 'implemented', 'released', 'deferred', 'unknown')
OUTCOME_WORDS = ('accepted', 'rejected', 'timeout', 'stalled', 'error', 'blocked',
                 'needs-permission', 'quota', 'cancelled')
CONTROL = re.compile(r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]')
# Length alone does not identify a secret: preserve long words and identifiers.
# Unprefixed base64 candidates need padding to distinguish them from prose.
PRIVATE = re.compile(r'(?:/(?:Users|home)/[^\s`"<>]+|[A-Za-z]:[\\/][^\s`"<>]+|'
                     r'\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]+|'
                     r'\b[0-9a-fA-F]{32,}\b|'
                     r'(?<![\w/+=-])[A-Za-z0-9+/]{40,}={1,2}(?![\w/+=-]))')
SAFE_ID = re.compile(r'[A-Za-z0-9._:-]{1,80}\Z')
SAFE_REF = re.compile(r'(?:[A-Za-z0-9#._:/-]{1,120}|[A-Za-z0-9._:-]{1,80}:in progress)\Z')
PR_IN_SUBJECT = re.compile(
    r'(?:^Merge pull request #([0-9]{1,8}) from \S.*|'
    r'\bpull request #([0-9]{1,8})|\bPR #([0-9]{1,8})|\(#([0-9]{1,8})\))\Z', re.I)


def has_control_chars(text):
    return not isinstance(text, str) or CONTROL.search(text) is not None


def sanitize_text(text, max_len=300):
    return ' '.join(PRIVATE.sub('[removed]', CONTROL.sub(' ', text)).split())[:max_len]


def validate_since(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('invalid --since date')
    date.fromisoformat(value)
    return value


def read_safe_file(path, limit=MAX_FILE_BYTES):
    """One bounded reader: no symlink components, regular file, current owner."""
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, part in enumerate(path.parts[1:]):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(path.parts) - 2:
                flags |= os.O_DIRECTORY
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > limit:
            raise ValueError('unsafe or oversized file')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('oversized file')
        return raw.decode('utf-8')
    finally:
        os.close(fd)


def reader_lines(text):
    fence = None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if match:
            token, tail = match.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not tail.strip():
                fence = None
        elif fence is None and len(line) <= 4096:
            yield line


def parse_criteria_from_markdown(text, prefix='C', spec_ref=None,
                                 sections=('work tracking', 'goal and acceptance',
                                           'success criteria', 'measurable outcomes')):
    criteria, active, section, depth = [], False, '', 0
    for line in reader_lines(text):
        heading = re.match(r'^(#{1,6})\s+(.+?)\s*$', line)
        if heading:
            level, title = len(heading[1]), heading[2].lower()
            if title in sections:
                section, depth = title, level
                active = title != 'work tracking'
            elif level <= depth:
                section, active = '', False
            continue
        outcome = re.match(r'^(?:[-*]\s*)?(?:\*\*)?Outcome(?:\*\*)?(?:\s*\([^)]*\))?\s*:\s*(.*)$', line.strip(), re.I)
        if outcome and section == 'work tracking':
            active, wording = True, outcome[1]
            default_id = 'OUTCOME-1'
        else:
            bullet = re.match(r'^\s*(?:[-*]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.+)$', line)
            if not active or not bullet:
                if line.strip() and section == 'work tracking':
                    active = False
                continue
            wording, default_id = bullet[2], f'{prefix}-{len(criteria) + 1}'
        explicit = re.match(r'^(?:\*\*([A-Za-z]{1,12}-?\d{1,4})\*\*|([A-Za-z]{1,12}-?\d{1,4}))(?:\s*[:.—-]\s*|\s+)(.+)$', wording)
        cid = (explicit[1] or explicit[2]) if explicit else default_id
        wording = explicit[3] if explicit else wording
        if not wording.strip() or re.fullmatch(r'\s*<[^<>]*>\s*', wording):
            continue
        criteria.append({'id': cid, 'criterion': sanitize_text(wording),
                         'evidence_refs': [spec_ref] if spec_ref else []})
    return criteria[:MAX_CRITERIA]


def collect_repo_specs_and_criteria(repo, anchors):
    specs, criteria = [], []
    if repo is None:
        return specs, criteria
    paths = set(repo.glob('specs/*/spec.md'))
    for pattern in ('docs/specs/*.md', 'docs/spec/*.md', 'specs/*.md'):
        paths.update(repo.glob(pattern))
    for path in sorted(paths):
        if len(specs) >= 80 or 'archive' in path.relative_to(repo).parts:
            continue
        try:
            text = read_safe_file(path, 64 * 1024)
        except (OSError, ValueError):
            continue
        lines = list(reader_lines(text))
        kit = path.name == 'spec.md' and path.parent.parent == repo / 'specs'
        headings = {line.strip() for line in lines if line.startswith('## ')}
        if not kit and not (len(headings & {'## Goal and acceptance', '## Plan', '## Tasks', '## Evidence'}) >= 2
                            and any(re.match(r'^(?:\*\*)?Status(?:\*\*)?:', s) for s in lines[:40])):
            continue
        sid = path.parent.name if kit else path.stem
        if not SAFE_ID.fullmatch(sid):
            continue
        status = 'unknown'
        for line in lines[:40]:
            match = re.match(r'^(?:\*\*)?Status(?:\*\*)?:\s*(.*)', line, re.I)
            if match and match[1].split(';')[0].strip().lower() in STATUS_WORDS:
                status = match[1].split(';')[0].strip().lower()
        specs.append({'id': sid, 'status': status})
        if path != anchors:
            sections = ('success criteria', 'measurable outcomes') if kit else ('goal and acceptance',)
            criteria.extend(parse_criteria_from_markdown(text, sid, f'{sid}:{status}', sections))
    return specs, criteria


def collect_git_evidence(repo_root, since):
    since = validate_since(since)
    git = shutil.which('git')
    if repo_root is None or git is None:
        return [], [], []
    env = {'PATH': os.defpath + os.pathsep + str(Path(git).parent),
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_TERMINAL_PROMPT': '0'}
    try:
        proc = subprocess.run(
            [git, '-c', 'log.showSignature=false', '-c', 'core.fsmonitor=false',
             '-C', os.path.abspath(repo_root), 'log', '--no-show-signature', '--no-color',
             '--no-ext-diff', '--no-textconv', '--format=%H%x09%s', f'--since={since}'],
            capture_output=True, env=env, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return [], [], []
    commits, prs, subjects = [], [], []
    if proc.returncode == 0:
        for line in proc.stdout[:256 * 1024].decode('utf-8', 'replace').splitlines()[:500]:
            sha, sep, subject = line.partition('\t')
            if not sep or not re.fullmatch(r'[a-f0-9]{40,64}', sha):
                continue
            short = sha[:12]
            commits.append(short)
            # Match the actual end before capping; truncated subjects cannot invent PRs.
            match = PR_IN_SUBJECT.search(subject.rstrip())
            pr = '#' + next(g for g in match.groups() if g) if match else None
            if pr and pr not in prs:
                prs.append(pr)
            subjects.append((short, sanitize_text(subject, 120), pr))
    return commits, prs, subjects


def collect_ledger_evidence(since, project=None):
    absent = {'status': 'absent', 'ids': [], 'counts': {}}
    if not project:
        return absent
    try:
        root = dr.consent_root()
        if root is None:
            return absent
        raw = read_safe_file(root / 'ledger.jsonl', 16 * 1024 * 1024)
    except (OSError, ValueError):
        return absent
    starts, finishes = {}, {}
    for line in raw.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not SAFE_ID.fullmatch(row['id']):
            continue
        if row.get('event') == 'start':
            starts[row['id']] = row
        elif row.get('event') == 'finish':
            finishes[row['id']] = row
    ids, counts = [], Counter()
    for rid, start in starts.items():
        finish = finishes.get(rid, {})
        ts = (finish or start).get('ts', '')
        if start.get('project') != project or not isinstance(ts, str) or ts[:10] < since:
            continue
        if len(ids) == MAX_LEDGER_IDS:
            break
        ids.append(rid)
        if finish.get('outcome') in OUTCOME_WORDS:
            counts[finish['outcome']] += 1
    return {'status': 'present', 'ids': ids, 'counts': dict(counts)}


def collect(anchors_path, since, repo=None, project=None):
    since = validate_since(since)
    anchors = Path(os.path.abspath(anchors_path))
    text = read_safe_file(anchors)
    root = Path(os.path.abspath(repo)) if repo else next(
        (p for p in anchors.parents if (p / '.git').exists()), None)
    specs, extra = collect_repo_specs_and_criteria(root, anchors)
    criteria = parse_criteria_from_markdown(text) + extra
    criteria = list({(c['id'], c['criterion']): c for c in criteria}.values())[:MAX_CRITERIA]
    commits, prs, subjects = collect_git_evidence(root, since)
    ledger = collect_ledger_evidence(since, project)
    for item in criteria:
        pattern = re.compile(r'(?<![A-Za-z0-9])' + re.escape(item['id']) + r'(?![A-Za-z0-9])')
        for sha, subject, pr in subjects:
            if pattern.search(subject):
                item['evidence_refs'].extend([sha] + ([pr] if pr else []))
        item['evidence_refs'] = list(dict.fromkeys(item['evidence_refs']))[:200]
    return {'since': since, 'criteria': criteria, 'evidence': {
        'commits': commits, 'pull_requests': prs, 'specs': specs, 'ledger': ledger,
        'counts': dict(zip(('commits', 'pull_requests', 'specs', 'ledger_runs'),
                           map(len, (commits, prs, specs, ledger['ids']))))}}


def require(condition, message='invalid schema'):
    if not condition:
        raise ValueError(message)


def fields(obj, keys):
    require(isinstance(obj, dict) and set(obj) == set(keys.split()))


def refs(values):
    require(isinstance(values, list) and len(values) <= 200, 'invalid references')
    for ref in values:
        require(isinstance(ref, str) and SAFE_REF.fullmatch(ref) and not ref.startswith(('/', '\\'))
                and not re.match(r'^[A-Za-z]:', ref) and '..' not in ref.split('/'), 'invalid reference')


def safe_text(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 300
            and not has_control_chars(value), 'invalid text')
    return sanitize_text(value)


def validate_payload(payload):
    """Screen criterion/question text in place; accept only fixed collection or question fields."""
    require(isinstance(payload, dict))
    if 'criteria' in payload:
        fields(payload, 'since criteria evidence')
        validate_since(payload['since'])
        require(isinstance(payload['criteria'], list) and len(payload['criteria']) <= MAX_CRITERIA)
        for item in payload['criteria']:
            fields(item, 'id criterion evidence_refs')
            require(isinstance(item['id'], str) and SAFE_ID.fullmatch(item['id']))
            item['criterion'] = safe_text(item['criterion'])
            refs(item['evidence_refs'])
        ev = payload['evidence']
        fields(ev, 'commits pull_requests specs ledger counts')
        for key, pattern, cap in (('commits', r'[a-f0-9]{12}', 500), ('pull_requests', r'#[0-9]{1,8}', 500)):
            require(isinstance(ev[key], list) and len(ev[key]) <= cap)
            require(all(isinstance(v, str) and re.fullmatch(pattern, v) for v in ev[key]))
        require(isinstance(ev['specs'], list) and len(ev['specs']) <= 80)
        for spec in ev['specs']:
            fields(spec, 'id status')
            require(isinstance(spec['id'], str) and SAFE_ID.fullmatch(spec['id']) and spec['status'] in STATUS_WORDS)
        ledger = ev['ledger']
        fields(ledger, 'status ids counts')
        refs(ledger['ids'])
        require(all(SAFE_ID.fullmatch(v) for v in ledger['ids']))
        require(ledger['status'] in ('present', 'absent') and isinstance(ledger['counts'], dict))
        require(all(k in OUTCOME_WORDS and type(v) is int and 0 <= v <= len(ledger['ids'])
                    for k, v in ledger['counts'].items()))
        require(sum(ledger['counts'].values()) <= len(ledger['ids']))
        require(ledger['status'] != 'absent' or not (ledger['ids'] or ledger['counts']))
        expected = dict(zip(('commits', 'pull_requests', 'specs', 'ledger_runs'),
                            map(len, (ev['commits'], ev['pull_requests'], ev['specs'], ledger['ids']))))
        require(ev['counts'] == expected)
    else:
        fields(payload, 'id criterion restated_criterion question evidence_refs')
        require(isinstance(payload['id'], str) and SAFE_ID.fullmatch(payload['id']))
        for key in ('criterion', 'restated_criterion', 'question'):
            payload[key] = safe_text(payload[key])
        refs(payload['evidence_refs'])
    return True


def check_report(report, collected):
    validate_payload(collected)
    fields(report, 'anchors unmatched_items options')
    ev = collected['evidence']
    known = set(ev['commits'] + ev['pull_requests'] + ev['ledger']['ids'])
    known.update(f"{s['id']}:{s['status']}" for s in ev['specs'])
    known.add('ledger:' + ev['ledger']['status'])
    anchor_ids = {c['id'] for c in collected['criteria']}
    require(isinstance(report['anchors'], list) and bool(report['anchors']))
    seen = set()
    for anchor in report['anchors']:
        fields(anchor, 'id status judge_answers evidence_refs')
        require(isinstance(anchor['id'], str) and anchor['id'] in anchor_ids and anchor['id'] not in seen)
        seen.add(anchor['id'])
        require(anchor['status'] in ('on course', 'drifting', 'abandoned', 'no drift'))
        require(isinstance(anchor['judge_answers'], list) and bool(anchor['judge_answers']))
        for answer in anchor['judge_answers']:
            fields(answer, 'answer quote_ok')
            require(answer['answer'] in ('yes', 'no', 'insufficient') and type(answer['quote_ok']) is bool)
            require(answer['answer'] != 'yes' or answer['quote_ok'])
        refs(anchor['evidence_refs'])
        require(bool(anchor['evidence_refs']) and set(anchor['evidence_refs']) <= known, 'uncollected evidence reference')
    refs(report['unmatched_items'])
    require(set(report['unmatched_items']) <= known, 'uncollected evidence reference')
    require(isinstance(report['options'], list) and len(report['options']) <= 3)
    for option in report['options']:
        fields(option, 'option cost')
        safe_text(option['option'])
        safe_text(option['cost'])
    return True


def read_json(path):
    def unique(pairs):
        result = dict(pairs)
        require(len(result) == len(pairs), 'duplicate JSON key')
        return result
    raw = read_safe_file(path) if path else sys.stdin.read(MAX_FILE_BYTES + 1)
    require(len(raw.encode('utf-8')) <= MAX_FILE_BYTES, 'input too large')
    return json.loads(raw, object_pairs_hook=unique)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    collector = sub.add_parser('collect')
    collector.add_argument('--anchors', required=True)
    collector.add_argument('--since', required=True)
    collector.add_argument('--repo')
    collector.add_argument('--project', help='required for ledger evidence; otherwise ledger is absent')
    for name in ('validate-payload', 'check-report'):
        command = sub.add_parser(name)
        command.add_argument('--file')
        if name == 'check-report':
            command.add_argument('--collected', required=True)
    args = parser.parse_args(argv)
    try:
        if args.cmd == 'collect':
            result = collect(args.anchors, args.since, args.repo, args.project)
        elif args.cmd == 'validate-payload':
            result = read_json(args.file)
            validate_payload(result)
        else:
            check_report(read_json(args.file), read_json(args.collected))
            result = {'ok': True}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TypeError) as error:
        print('Navigator state refused: ' + sanitize_text(str(error), 120), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
