#!/usr/bin/env python3
"""Build the status dashboard's data from the usage events and the dispatch ledger.

  run      write data.js and dashboard.html into the state folder (--open shows the page,
           --throttle SECONDS skips the work when data.js is newer than that). One rebuild runs at
           a time and a run waits its turn, so the files never go back to an older snapshot.
  consent  record the user's consent and retention (30, 90 or 365 days)
  purge    delete the recorded events, data.js and dashboard.html (needs --yes)
  antigravity-hook  add (or --remove) the plugin's hook group in the user's own Antigravity hooks.json,
           with an absolute path to the script and a backup of the file (needs --yes)

The page reads data.js; a browser will not read local JSON from a page, but it loads a
sibling script. Nothing is sent anywhere. Dates are the machine's local dates.
"""

import argparse
import fcntl
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import sys
import time
import threading
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # -I leaves the script folder off the path
import fnl_metrics as fm  # noqa: E402
import agent_processes as ap  # noqa: E402
import project_progress as pp  # noqa: E402

SKILLS = HERE.parent.parent
PAGE = HERE.parent / "assets/dashboard.html"
LEDGER = SKILLS / "fnl-delegate/scripts/ledger.py"
WEEKS = 12
REVIEWS_SHOWN = 12
NO_CONSENT = "consent not given (run fnl-setup)"
NO_EVENTS = "no events recorded yet"
ROUTER_SKILL = "fnl-coding-router"
HOOK_GROUP = "finolabs-vibecode"
AGY_TOOLS = "run_command|write_to_file|replace_file_content|multi_replace_file_content"


def local_date(ts):
    return datetime.fromisoformat(ts).astimezone().date()


def load_ledger():
    if not LEDGER.exists():
        return None
    spec = importlib.util.spec_from_file_location("fnl_ledger", LEDGER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def week_of(day, start):
    """Index 0..WEEKS-1 of the week a date falls in, counted from the period start, or None."""
    index = (day - start).days // 7
    return index if 0 <= index < WEEKS else None


def ratio(num, den):
    return num / den if den else None


def ledger_metrics(ledger, start, usage_start=None):
    """(delegation rows, overall first pass, weekly first pass with None for empty weeks, finished runs, runs handed off)."""
    rows = ledger.summary_rows(keys=("agent", "model", "grade"), since=start.isoformat())
    delegation = [{"agent": r["agent"], "model": r["model"], "grade": r["grade"], "runs": r["n"], "first_pass": r["first_pass"],
                   "quota": r["quota"], "error": r["error"], "median_min": round(r["median_min"]), "rework": round(r["rework"], 1)}
                  for r in rows]
    runs = sum(r["n"] for r in rows)
    starts, finishes = ledger.load()
    done, good = [0] * WEEKS, [0] * WEEKS
    for dispatch_id, s in starts.items():
        f = finishes.get(dispatch_id)
        w = week_of(local_date(s["ts"]), start) if f else None
        if w is not None:
            done[w] += 1
            good[w] += f["outcome"] == "accepted" and f["rework_rounds"] == 0
    handoff_start = max(start, usage_start) if usage_start is not None else start
    handed_off = sum(s["kind"] == "implement" and s["agent"] != "subagent" and s["reason"] != "fallback-failure"
                     and local_date(s["ts"]) >= handoff_start for s in starts.values())
    return delegation, ratio(sum(r["first_pass"] * r["n"] for r in rows), runs), [ratio(g, d) for g, d in zip(good, done)], runs, handed_off


def kept_metrics(events, by_sid, handed_off):
    """Tasks coordinators kept, beside implementation runs handed off (None when the ledger is unread); None when neither exists."""
    groups = defaultdict(lambda: [0, 0])
    for e in events:
        if e["event"] == "kept":
            host = next((x["host"] for x in by_sid[e["sid"]] if x["event"] == "session_start"), "unknown")
            group = groups[(host, e["reason"], e["route_by"])]
            group[0] += 1
            group[1] += e["tasks"]
    if not groups and not (handed_off and events and fm.enabled()):  # with nothing recording, no receipt does not mean nothing was kept
        return None
    rows = [{"coordinator": c, "reason": r, "route_by": b, "receipts": n, "tasks": t} for (c, r, b), (n, t) in sorted(groups.items())]
    return {"receipts": sum(r["receipts"] for r in rows), "tasks": sum(r["tasks"] for r in rows), "handed_off": handed_off, "rows": rows}


def judge_metrics(events, route_rows, has_judge_route, ledger_note):
    """Closed receipt counts and a separate ledger association; never join a site to a file or run."""
    receipts = [e for e in events if e["event"] == "judge"]
    if not receipts and not has_judge_route:
        return None
    block = {"receipts": len(receipts), "outcome_association": route_rows,
             "note": "" if receipts else "No receipts were recorded.",
             "outcome_note": "" if route_rows else ledger_note}
    if receipts:
        uses = Counter((e["site"], e["grader"]) for e in receipts)
        answers = [e for e in receipts if e["grader"] == "judge"]
        validated = [e for e in answers if e["result"] == "validated"]
        followed = sum(e["followed"] == "yes" for e in validated)
        block.update({
            "use": [{"site": site, "grader": grader, "count": count}
                    for (site, grader), count in sorted(uses.items())],
            "usable_answers": {"validated": len(validated), "calls": len(answers),
                               "share": ratio(len(validated), len(answers))},
            "followed": {"yes": followed, "validated": len(validated), "share": ratio(followed, len(validated))},
        })
    return block


def newer_ledger(target):
    """A ledger write bypasses the throttle; a missing or unreadable ledger does not."""
    try:
        root = fm.dr.consent_root()
        return root is not None and (root / "ledger.jsonl").stat().st_mtime_ns > target.stat().st_mtime_ns
    except OSError:
        return False


def freshness(events, generated):
    current = datetime.fromisoformat(generated)

    def age(ts):
        try:
            return max(0, int((current - datetime.fromisoformat(ts)).total_seconds()))
        except (ValueError, TypeError):
            return None

    hosts = {e["sid"]: e["host"] for e in events if e["event"] == "session_start"}
    latest = {}
    for e in events:
        host = hosts.get(e["sid"])
        if host is not None and (host not in latest or datetime.fromisoformat(e["ts"]) > datetime.fromisoformat(latest[host])):
            latest[host] = e["ts"]
    ledger_age = quota_age = None
    try:
        lines = fm.dr.read_data("ledger.jsonl", 16 * 1024 * 1024).decode("utf-8").splitlines()
        for line in reversed(lines):
            try:
                ledger_age = age(json.loads(line)["ts"])
            except (ValueError, TypeError, KeyError):
                continue
            if ledger_age is not None:
                break
    except (OSError, ValueError):
        pass
    try:
        cache = json.loads(fm.dr.read_data("state/quota/quota.json"))
        ages = [age(entry["measured"]) for labels in cache.values() for entry in labels.values()]
        quota_age = min((a for a in ages if a is not None), default=None)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return {"built_at": generated, "latest_event": latest, "ledger_age_seconds": ledger_age, "quota_age_seconds": quota_age}


def recent_snapshot():
    """Reuse the page's last bounded snapshot for ten seconds, even on a ledger rebuild.

    The file is data, never authority for consent or a command. Reconstruct only
    the fixed snapshot schema so a tampered page cannot supply process names.
    """
    try:
        path = fm.state_dir() / 'data.js'
        fd = os.open(path, os.O_RDONLY | fm.NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o022 or info.st_size > 16 * 1024 * 1024):
                return None
            with os.fdopen(os.dup(fd), 'r') as stream:
                raw = stream.read(16 * 1024 * 1024 + 1)
        finally:
            os.close(fd)
        previous = json.loads(raw.removeprefix('window.FNL_DATA = ').removesuffix(';\n'))['running']
        snap = previous['snapshot']
        age = (fm.now() - datetime.fromisoformat(snap['time'])).total_seconds()
        if not 0 <= age < 10 or snap['reason'] not in ('', 'ps unavailable', 'ps failed', 'ps timed out', 'ps output too large'):
            return None
        result = ap.empty(snap['reason'], snap['time'])
        def count(value):
            if type(value) is not int or value < 0:
                raise ValueError('count')
            return value
        result['apps'] = {key: count(value) for key, value in snap['apps'].items() if key in ap.APPS}
        for row in previous['processes']:
            if row['family'] not in ap.ROOTS:
                return None
            result['processes'].append(dict(family=row['family'], elapsed_seconds=count(row['elapsed_seconds']),
                descendants={key: count(value) for key, value in row['descendants'].items() if key in ap.CHILDREN or key == 'other'}))
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def live_sessions(events, generated):
    """Counts only: recent event activity, not a process or session inventory."""
    current = datetime.fromisoformat(generated)
    families = ('claude', 'codex', 'antigravity')
    hosts = {e['sid']: e['host'] for e in events if e['event'] == 'session_start'}
    active = {family: set() for family in families}
    for event in events:
        host = hosts.get(event['sid'])
        at = pp.timestamp(event['ts'])
        if host in active and at is not None and 0 <= (current - at).total_seconds() < 900:
            active[host].add(event['sid'])
    return dict(window_minutes=15, **{family: min(99, len(active[family])) for family in families})


def quota_meters():
    """Project bounded pool metadata, preserving all three family placeholders."""
    try:
        cache = json.loads(fm.dr.read_data('state/quota/quota.json', 262144))
    except (OSError, ValueError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    meters = []
    current = fm.now()
    for family in ('claude', 'codex', 'agy'):
        entries = cache.get(family, {})
        pools = []
        for entry in list(entries.values())[:4] if isinstance(entries, dict) else []:
            if not isinstance(entry, dict):
                continue
            measured = pp.timestamp(entry.get('measured'))
            groups = entry.get('groups')
            if measured is None or not isinstance(groups, list):
                continue
            for group in groups[:64]:
                if len(pools) >= 8:
                    break
                if not isinstance(group, dict):
                    continue
                name, value = group.get('name'), group.get('remaining_fraction')
                if (not isinstance(name, str) or not name or len(name) > 80
                        or any(ord(c) < 32 or ord(c) == 127 for c in name)
                        or type(value) not in (int, float) or not 0 <= value <= 1):
                    continue
                reset = pp.timestamp(group.get('reset_time'))
                window = group.get('window')
                # The closed output shape carries the window in the pool display name.
                if window in ('5h', 'weekly') and not (name.startswith('week') or name in ('session', 'five-hour')):
                    name += ' / ' + window
                pools.append(dict(name=name, remaining_fraction=value,
                    resets=reset.isoformat() if reset else None, measured=measured.isoformat(),
                    unverified=not 0 <= (current - measured).total_seconds() <= 28800))
        meters.append(dict(agent=family, pools=pools))
    return meters


def previous_projects():
    """Read the last page as data only, bounded and owner-checked like the snapshot.

    Closed metadata keys and leaf values prevent a tampered file carrying free text
    forward. Labels are always resolved again from canonical host configuration.
    The active strip is never carried over: each refresh reconstructs its closed
    schema from validated events, even when repository snapshots are retained.
    """
    try:
        path = fm.state_dir() / 'data.js'
        fd = os.open(path, os.O_RDONLY | fm.NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_mode & 0o022 or info.st_size > 16 * 1024 * 1024):
                return {}
            with os.fdopen(os.dup(fd), 'r') as stream:
                raw = stream.read(16 * 1024 * 1024 + 1)
        finally:
            os.close(fd)
        repositories = json.loads(raw.removeprefix('window.FNL_DATA = ').removesuffix(';\n'))['progress']['repositories']
        keys = {'source', 'recognition', 'ledger_join', 'work', 'ordinal', 'stages', 'stage', 'artifacts',
                'spec', 'plan', 'design', 'verify', 'ship', 'status_hint', 'review_counts', 'code_final',
                'security_final', 'packages', *pp.STATES, 'features', 'feature', 'tasks', 'total', 'done',
                'phases', 'phase', 'stories', 'story', 'priority',
                'state', 'runs', 'sessions', 'id', 'host', 'first', 'last', 'agent', 'model', 'start', 'finish',
                'outcome', 'rework_rounds', 'elapsed_seconds', 'in_progress', 'labels_without_feature',
                'unlinked_runs', 'outcomes', 'sessions_without_task', 'active_24h', 'idle', 'running_now',
                'reviews', 'code', 'security', 'version', 'updated', 'reason', 'skipped', *pp.OUTCOMES, 'open', 'other'}
        enums = {'source': pp.SOURCES, 'stage': pp.STAGES, 'status_hint': pp.HINTS,
                 'recognition': ('index', 'status', 'artifacts', 'checkbox', 'ledger', 'none'),
                 'ledger_join': ('configured', 'configured-empty', 'folder', 'none')}
        def clean(value, key='', depth=0):
            if depth > 9:
                raise ValueError('depth')
            if key in enums:
                if isinstance(value, str) and value in enums[key]:
                    return value
                raise ValueError('metadata')
            if isinstance(value, dict):
                return {k: clean(v, k, depth + 1) for k, v in value.items() if k in keys}
            if isinstance(value, list):
                if len(value) > 200:
                    raise ValueError('rows')
                return [clean(v, key, depth + 1) for v in value]
            if value is None or type(value) is bool or type(value) is int and 0 <= value <= 10**12:
                return value
            if isinstance(value, str):
                if key in ('first', 'last', 'start', 'finish', 'updated') and pp.timestamp(value):
                    return value
                if key == 'model' and pp.TOKEN.fullmatch(value):
                    return value
                if key == 'id' and pp.IDENT.fullmatch(value):
                    return value
                if key == 'story' and re.fullmatch(r'US[0-9]{1,3}', value):
                    return value
                if key == 'version' and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-dev)?', value):
                    return value
                if value in (*pp.AGENTS, *pp.HOSTS, *pp.OUTCOMES, *pp.STATES, 'other', 'unknown', 'open', 'todo', 'done', 'active',
                             'in progress', 'accepted, not ticked', 'APPROVE', 'REWORK', '', 'task file skipped',
                             'spec file skipped', 'unsafe task path', 'file limit', 'entry limit', 'feature limit', 'ledger unavailable'):
                    return value
            raise ValueError('metadata')
        return {code: clean(row) for code, row in list(repositories.items())[-5:]
                if re.fullmatch(r'[0-9a-f]{8}', code) and isinstance(row, dict)}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def running_metrics(generated, events=()):
    snapshot = ap.empty('snapshot off')
    if fm.enabled() and ap.enabled():
        snapshot = recent_snapshot() or ap.snapshot()
    available = snapshot['reason'] == ''
    processes = snapshot.pop('processes')
    rows, note = [], ''
    ledger = load_ledger()
    if ledger is None:
        note = 'fnl-delegate is not installed'
    else:
        try:
            starts, finishes = ledger.load()
            for dispatch_id, start in starts.items():
                if dispatch_id in finishes:
                    continue
                try:
                    age = max(0, (datetime.fromisoformat(generated) - datetime.fromisoformat(start['ts'])).total_seconds() / 60)
                    budget = start.get('budget_min')
                    if type(budget) is not int or budget <= 0:
                        budget = None
                    family = {'claude': 'claude', 'codex': 'codex', 'antigravity': 'agy'}.get(start['agent'])
                    rows.append({**{key: start[key] for key in ('agent', 'model', 'project', 'task', 'ts')},
                        'id': dispatch_id, 'age_min': round(age, 1), 'budget_min': budget,
                        'check_due': budget is not None and age >= budget / 2,
                        'liveness': 'unverified',
                        'no_process_found': available and family is not None and not any(p['family'] == family for p in processes)})
                except (ValueError, TypeError, KeyError):
                    continue
        except (OSError, ValueError, TypeError):
            note = 'ledger could not be read'
    families = {'antigravity': 'agy', 'claude': 'claude', 'codex': 'codex'}
    for process in processes:
        process['not_started_by_coordinator'] = not any(families.get(row['agent']) == process['family'] for row in rows) if not note else False
    return {'open': rows, 'processes': processes, 'snapshot': snapshot, 'ledger_note': note, 'quota': quota_meters(), 'live': live_sessions(events, generated)}


def progress_metrics(events, running, cwd=None):
    if not fm.enabled():
        return None
    # collect owns the wall timer, including configuration and repo_code's local reads.
    # Replace the current repository and retain four other last-written snapshots.
    with_progress = pp.collect(cwd or os.getcwd(), None, events=events, records=load_ledger, repo_code=fm.repo_code)
    if with_progress['reason'] == 'progress off':
        return None
    code = with_progress.pop('repo', None)
    repositories = previous_projects()
    notice = False
    if code is not None:
        with_progress['running_now'] = len(running['processes']) if not running['snapshot']['reason'] else None
        reviews = {}
        for event in sorted(events, key=lambda e: e['ts']):
            if event['repo'] == code and event['event'] == 'review':
                reviews[event['kind']] = event['verdict']
        with_progress['reviews'] = reviews
        with_progress['version'] = pp.installed_version()
        with_progress['updated'] = fm.now().isoformat()
        repositories.pop(code, None)
        repositories[code] = with_progress
        repositories = dict(list(repositories.items())[-5:])
        notice = pp.notice('dashboard', with_progress['version'])
    labels = canonical_labels()
    for key, row in repositories.items():
        row['label'] = labels.get(key, '')
    result = {'current': code, 'repositories': repositories,
              'active': pp.active_projects(events, repositories, labels, fm.now()),
              'in_progress': sum(row.get('in_progress', 0) for row in repositories.values()), 'notice': notice}
    if code is None:
        result['reason'] = with_progress['reason']
    return result


def canonical_labels():
    try:
        labels = pp.registered_projects()
        labels.update(pp.project_labels(fm.dr.read_data('host.md', 262144).decode('utf-8')))
        return labels
    except (OSError, ValueError, UnicodeError):
        return pp.registered_projects()


def build(days=WEEKS * 7, cwd=None):
    today = datetime.now().astimezone().date()
    start = today - timedelta(days=days - 1)
    consent = fm.read_consent()
    recorded_events = fm.read_events()[0]
    events = [e for e in recorded_events if local_date(e["ts"]) >= start]
    by_sid = defaultdict(list)
    for e in events:
        by_sid[e["sid"]].append(e)
    why = None if events else (NO_EVENTS if consent else NO_CONSENT)

    covered = missed = excluded = unclassified = with_edits = 0
    cov_week, eligible_week = [0] * WEEKS, [0] * WEEKS
    sessions_week, calls_week = [0] * WEEKS, [0] * WEEKS
    for evs in by_sid.values():
        evs.sort(key=lambda e: e["ts"])
        w = week_of(local_date(evs[0]["ts"]), start)
        if w is not None:
            sessions_week[w] += 1
        # A commit proves a change too: agents often write files through the shell, which no edit hook sees.
        edit = next((e["ts"] for e in evs if e["event"] in ("first_edit", "commit")), None)
        if edit is None:
            continue
        with_edits += 1
        starts = [e for e in evs if e["event"] == "session_start"]
        if any(e["dispatch"] for e in starts):
            excluded += 1
        elif not starts:
            unclassified += 1
        else:
            routed = next((e["ts"] for e in evs if e["event"] == "router" or (e["event"] == "skill" and e["name"] == ROUTER_SKILL)), None)
            hit = routed is not None and routed <= edit
            covered, missed = covered + hit, missed + (not hit)
            w = week_of(local_date(edit), start)
            if w is not None:
                eligible_week[w] += 1
                cov_week[w] += hit
    eligible = covered + missed

    uses = Counter((e["event"], e["name"]) for e in events if e["event"] in ("skill", "agent"))
    for e in events:
        if e["event"] in ("skill", "agent"):
            w = week_of(local_date(e["ts"]), start)
            if w is not None:
                calls_week[w] += 1
    use = [{"name": n, "kind": k, "count": c} for (k, n), c in sorted(uses.items(), key=lambda x: (-x[1], x[0][1]))[:10]]

    skill_names = {n for (k, n) in uses if k == "skill"}
    sizes = {n: (SKILLS / n / "SKILL.md").stat().st_size // 4 for n in skill_names if (SKILLS / n / "SKILL.md").is_file()}
    loads = Counter({n: c for (k, n), c in uses.items() if k == "skill" and n in sizes})
    sessions_loading = len({e["sid"] for e in events if e["event"] == "skill" and e["name"] in sizes})
    load = None
    if loads:
        top = sorted(loads, key=lambda n: -sizes[n] * loads[n])[:6]
        load = {"estimate": True, "avg_tokens_per_session": round(sum(sizes[n] * loads[n] for n in loads) / max(sessions_loading, 1)),
                "top": [{"name": n, "tokens": sizes[n], "loads": loads[n]} for n in top]}

    verdicts = defaultdict(list)
    for e in events:
        if e["event"] == "review":
            verdicts[(e["repo"], e["pr"])].append((e["ts"], e["verdict"]))
    groups = {key: sorted(v) for key, v in verdicts.items()}
    newest = sorted(groups.items(), key=lambda x: x[1][0][0], reverse=True)
    labels = canonical_labels()
    reviews = [{"repo": "repo-" + repo, "label": labels.get(repo, "repo " + repo[:4]),
                "pr": pr, "verdicts": [v for _, v in vs]} for (repo, pr), vs in newest[:REVIEWS_SHOWN]]
    review_stats = {"total": len(groups), "reworked": sum(any(v == "REWORK" for _, v in vs) for vs in groups.values())}
    depth = {d: [0, 0] for d in fm.DEPTHS}
    for e in events:
        if e["event"] != "router":
            continue
        after = [(vs[0][0], vs) for (repo, _), vs in groups.items() if repo == e["repo"] and vs[0][0] >= e["ts"]]
        if after:
            vs = min(after)[1]
            depth[e["depth"]][0] += 1
            depth[e["depth"]][1] += any(v == "REWORK" for _, v in vs)
    depth_rows = [{"depth": d, "receipts": r, "reworked": w} for d, (r, w) in depth.items() if r]

    per_day = Counter(local_date(e["ts"]).isoformat() for e in events)
    activity = [{"date": (start + timedelta(days=i)).isoformat(), "count": per_day.get((start + timedelta(days=i)).isoformat(), 0)} for i in range(days)]

    delegation, first_pass, fp_week, runs, handed_off = None, None, [None] * WEEKS, 0, None
    ledger_note = "fnl-delegate is not installed"
    route_rows, has_judge_route = [], False
    if LEDGER.exists():
        try:
            usage_start = min((local_date(e["ts"]) for e in events), default=None)
            ledger = load_ledger()
            delegation, first_pass, fp_week, runs, handed_off = ledger_metrics(ledger, start, usage_start)
            starts, _ = ledger.load()
            has_judge_route = any(s.get("route_by") == "judge" and s["ts"][:10] >= start.isoformat()
                                  for s in starts.values())
            route_rows = [{"route_by": r["route_by"], "runs": r["n"], "first_pass": r["first_pass"], "small": r["n"] < 5}
                          for r in ledger.summary_rows(keys=("route_by",), since=start.isoformat())
                          if r["route_by"] in ("judge", "table")]
            ledger_note = "%d runs" % runs if runs else "no finished runs in this period"
        except Exception:
            delegation, ledger_note = None, "ledger could not be read"

    missing = {}
    for key in ("activity", "router", "use", "load"):
        if why:
            missing[key] = why
    if events and not eligible:
        missing["router"] = "no session with an edit in this period"
    if events and not use:
        missing["use"] = "no fnl- skill or agent used in this period"
    if events and not load:
        missing["load"] = "no fnl- skill loaded in this period" if not skill_names else "skill files not found beside fnl-status (install the whole plugin)"
    if not depth_rows:
        missing["depth"] = why or "no router receipt followed by a pull request review yet"
    if not reviews:
        missing["reviews"] = why or "no review comment recorded yet"
    if not delegation:
        missing["delegation"] = ledger_note

    generated = fm.now().isoformat(timespec="seconds")
    running = running_metrics(generated, recorded_events)
    return {
        "progress": progress_metrics(events, running, cwd),
        "generated": generated,
        "freshness": freshness(events, generated),
        "running": running,
        "period": {"from": start.isoformat(), "to": today.isoformat(), "days": days},
        "sessions": {"total": len(by_sid), "with_edits": with_edits, "dispatch": excluded, "unclassified": unclassified},
        "errors": fm.errors_count(), "missing": missing,
        "kpi": {"router_coverage": ratio(covered, eligible), "sessions": len(by_sid) if events else None,
                "calls": sum(uses.values()) if events else None, "first_pass": first_pass,
                "spark": {"router_coverage": [ratio(c, n) for c, n in zip(cov_week, eligible_week)] if eligible else None,
                          "sessions": sessions_week if events else None, "calls": calls_week if events else None,
                          "first_pass": fp_week if first_pass is not None else None}},
        "router": {"covered": covered, "missed": missed, "excluded": excluded, "unclassified": unclassified, "eligible": eligible} if eligible else None,
        "use": use or None, "load": load, "depth": depth_rows or None, "delegation": delegation or None, "kept": kept_metrics(events, by_sid, handed_off),
        "judge": judge_metrics(events, route_rows, has_judge_route, ledger_note),
        "reviews": reviews or None, "review_stats": review_stats if groups else None, "activity": activity if events else None,
        "sources": [
            {"name": "hooks", "ok": bool(events), "note": "%d events" % len(events) if events else (why or "")},
            {"name": "consent", "ok": consent is not None,
             "note": "given %s, kept %d days" % (consent["date"], consent["retention_days"]) if consent else "not given"},
            {"name": "ledger", "ok": bool(runs), "note": ledger_note},
        ],
    }


def js_text(data):
    """data.js: one assignment, ASCII only, with characters that could end or break a script escaped."""
    body = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return "window.FNL_DATA = " + body + ";\n"


LOCK_WAIT = 3.0  # seconds a run waits for a rebuild in progress; under the hook's 4 s (tool call) and 8 s (stop) timeouts
LOCK_POLL = 0.05


def take_lock(path, wait=None):
    """The descriptor holding the rebuild lock, or None when it stays held for `wait` seconds or cannot be used.

    The operating system owns the lock and drops it when the process ends, so a killed rebuild leaves nothing to
    clean up. The file is created with NOFOLLOW and mode 0600, must be a regular file, and is never removed (not
    even by purge): removing it while a holder has it would let a second process lock a new file. Windows has no
    fcntl and uses msvcrt; that path is untested."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | fm.NOFOLLOW | getattr(os, "O_NONBLOCK", 0), 0o600)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        deadline = time.monotonic() + (LOCK_WAIT if wait is None else wait)
        while True:
            try:
                try:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except ImportError:
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return fd
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(LOCK_POLL)
    except OSError:
        os.close(fd)
        return None


def cmd_run(args):
    """Rebuild one run at a time. A run waits for one in progress and then rebuilds, so the run that reads the events last
    publishes last and the files never go back to an older snapshot. A throttled run skips when data.js is fresh once it
    holds the lock, which is also how two hooks that both passed the cheap age check end up rebuilding once."""
    folder = fm.ensure_dir(fm.state_dir(), follow=True)
    held = take_lock(folder / "refresh.lock")
    if held is None:
        if args.open and (folder / "dashboard.html").exists():  # a rebuild is under way; the page still opens
            print("dashboard %s · a rebuild is already running" % (folder / "dashboard.html"))
            webbrowser.open((folder / "dashboard.html").as_uri())
        return
    try:
        # Hooks supply --cwd/--throttle and never request registration. Register
        # before the throttle so an explicit status invocation names the repo.
        if getattr(args, "register_here", False) is True and not getattr(args, "cwd", None) and fm.enabled():
            pp.register_here(os.getcwd())
        if args.throttle is not None and (folder / "data.js").exists() and \
                fm.now().timestamp() - (folder / "data.js").stat().st_mtime < args.throttle and not newer_ledger(folder / "data.js"):
            return
        publish(folder, args)
    finally:
        os.close(held)  # closing the descriptor releases the lock


def publish(folder, args):
    target = folder / "data.js"
    data = build(cwd=args.cwd) if getattr(args, "cwd", None) else build()
    fm.atomic_write(target, js_text(data))
    fm.atomic_write(folder / "dashboard.js", PAGE.with_suffix(".js").read_bytes())
    fm.atomic_write(folder / "dashboard.html", PAGE.read_bytes())
    miss = sorted(data["missing"])
    last = fm.errors_last()
    print("dashboard %s · %s to %s · sessions %d · unclassified %d · writer errors %d%s%s" % (
        folder / "dashboard.html", data["period"]["from"], data["period"]["to"], data["sessions"]["total"],
        data["sessions"]["unclassified"], data["errors"], " (latest: %s)" % last if last else "",
        " · missing: " + ", ".join(miss) if miss else ""))
    if args.open:
        webbrowser.open((folder / "dashboard.html").as_uri())


def cmd_consent(args):
    if args.revoke:
        if not args.yes:
            sys.exit("consent: pass --yes once the user has confirmed")
        try:
            with fm.dr.data_folder("state") as folder:
                os.unlink("consent.json", dir_fd=folder)
        except FileNotFoundError:
            pass
        except ValueError:
            sys.exit("consent: invalid data root; nothing recorded")
        print("consent withdrawn: nothing is recorded until consent is given again")
        return
    if args.retention is None:
        sys.exit("consent: pass --retention DAYS, or --revoke")
    try:
        fm.write_consent(args.retention)
    except ValueError:
        sys.exit("consent: invalid data root; nothing recorded")
    print("consent recorded: events kept %d days" % args.retention)


def cmd_purge(args):
    if not args.yes:
        sys.exit("purge: pass --yes once the user has confirmed")
    removed = fm.purge_store()
    for name in ("data.js", "dashboard.html", "dashboard.js"):
        path = fm.state_dir() / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
            removed += 1
    try:
        with fm.dr.data_folder("state") as folder:
            fcntl.flock(folder, fcntl.LOCK_EX)
            os.unlink("projects.json", dir_fd=folder)
            removed += 1
    except (OSError, ValueError):
        pass
    print("purge: removed %d files" % removed)


def is_plugin_root(folder):
    """True when folder holds the finolabs-vibecode manifest and the hook script, so a path in some other tree is never written to the user's config."""
    try:
        manifest = json.loads((folder / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(manifest, dict) and manifest.get("name") == "finolabs-vibecode" and (folder / "scripts/metrics_hook.py").is_file()


def reject_constant(name):
    raise ValueError("%s is not valid JSON" % name)


def antigravity_group(script):
    def command(event):
        return "python3 -I %s --host antigravity --event %s" % (shlex.quote(str(script)), event)
    return {"SessionStart": [{"type": "command", "command": command("session_start"), "timeout": 10}],
            "PostToolUse": [{"matcher": AGY_TOOLS, "hooks": [{"type": "command", "command": command("post_tool_use"), "timeout": 5}]}]}


def cmd_antigravity_hook(args):
    """Merge one hook group into the user's Antigravity hooks.json, keeping every other group and a backup of the file."""
    if not args.yes:
        sys.exit("antigravity-hook: pass --yes once the user has confirmed the change to their hooks file")
    script = HERE.parents[2] / "scripts/metrics_hook.py"
    if not args.remove and not is_plugin_root(script.parent.parent):
        sys.exit("antigravity-hook: this skill is not inside the finolabs-vibecode plugin (no .claude-plugin/plugin.json named finolabs-vibecode "
                 "beside scripts/metrics_hook.py); install the whole plugin. Nothing changed.")
    path = Path(args.config).expanduser().resolve()  # a symlinked file is edited in place, not replaced by a regular file
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant) if path.exists() else {}
    except (OSError, ValueError) as error:
        sys.exit("antigravity-hook: cannot read %s as JSON (%s); nothing changed" % (path, error))
    if not isinstance(data, dict):
        sys.exit("antigravity-hook: %s is not a JSON object; nothing changed" % path)
    if args.remove:
        if HOOK_GROUP not in data:
            print("antigravity-hook: no %s group in %s" % (HOOK_GROUP, path))
            return
        data.pop(HOOK_GROUP)
    else:
        data[HOOK_GROUP] = antigravity_group(script.resolve())
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        text.encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate escape in the user's file cannot be written as UTF-8
        text = json.dumps(data, indent=2) + "\n"
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".finolabs-backup-" + fm.now().strftime("%Y%m%d-%H%M%S-%f")))
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fm.atomic_write(path, text)
    os.chmod(path, mode)
    print("antigravity-hook: %s the %s group in %s" % ("removed" if args.remove else "set", HOOK_GROUP, path))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="write data.js and dashboard.html")
    run.add_argument("--register-here", action="store_true", help="name this repository locally after metrics consent")
    run.add_argument("--open", action="store_true", help="show the page in the default browser")
    run.add_argument("--throttle", type=float, metavar="SECONDS", help="skip when data.js is newer than this")
    run.add_argument("--cwd", help="repository working folder supplied by a session hook")
    run.set_defaults(func=cmd_run)
    consent = sub.add_parser("consent", help="record consent and retention")
    consent.add_argument("--retention", type=int, choices=fm.RETENTIONS)
    consent.add_argument("--revoke", action="store_true", help="withdraw consent; recording stops, recorded events stay until purge")
    consent.add_argument("--yes", action="store_true", help="confirm consent withdrawal")
    consent.set_defaults(func=cmd_consent)
    purge = sub.add_parser("purge", help="delete recorded events and the dashboard files")
    purge.add_argument("--yes", action="store_true")
    purge.set_defaults(func=cmd_purge)
    agy = sub.add_parser("antigravity-hook", help="add or remove the hook group in the user's Antigravity hooks.json")
    agy.add_argument("--config", default="~/.gemini/config/hooks.json")
    agy.add_argument("--remove", action="store_true")
    agy.add_argument("--yes", action="store_true")
    agy.set_defaults(func=cmd_antigravity_hook)
    args = parser.parse_args()
    if args.command == "run":
        # Detached hooks have no parent timeout. This wall-clock watchdog also
        # covers lock waits and blocked I/O; process exit releases the OS lock.
        cap = threading.Timer(20, os._exit, args=(0,))
        cap.daemon = True
        cap.start()
        try:
            args.func(args)
        finally:
            cap.cancel()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
