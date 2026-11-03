#!/usr/bin/env python3
"""Build the status dashboard's data from the usage events and the dispatch ledger.

  run      write data.js and dashboard.html into the state folder (--open shows the page,
           --if-older MINUTES skips the work when data.js is newer than that)
  consent  record the user's consent and retention (30, 90 or 365 days)
  purge    delete the recorded events, data.js and dashboard.html (needs --yes)

The page reads data.js; a browser will not read local JSON from a page, but it loads a
sibling script. Nothing is sent anywhere. Dates are the machine's local dates.
"""

import argparse
import importlib.util
import json
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # -I leaves the script folder off the path
import fnl_metrics as fm  # noqa: E402

SKILLS = HERE.parent.parent
PAGE = HERE.parent / "assets/dashboard.html"
LEDGER = SKILLS / "fnl-delegate/scripts/ledger.py"
WEEKS = 12
REVIEWS_SHOWN = 8
NO_CONSENT = "consent not given (run fnl-setup)"
NO_EVENTS = "no events recorded yet"
ROUTER_SKILL = "fnl-coding-router"


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


def ledger_metrics(ledger, start):
    """(delegation rows, overall first pass, weekly first pass with None for empty weeks, finished runs)."""
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
    return delegation, ratio(sum(r["first_pass"] * r["n"] for r in rows), runs), [ratio(g, d) for g, d in zip(good, done)], runs


def build(days=WEEKS * 7):
    today = datetime.now().astimezone().date()
    start = today - timedelta(days=days - 1)
    consent = fm.read_consent()
    events = [e for e in fm.read_events()[0] if local_date(e["ts"]) >= start]
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
        edit = next((e["ts"] for e in evs if e["event"] == "first_edit"), None)
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
    reviews = [{"repo": "repo-" + repo, "pr": pr, "verdicts": [v for _, v in vs]} for (repo, pr), vs in newest[:REVIEWS_SHOWN]]
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

    delegation, first_pass, fp_week, runs = None, None, [None] * WEEKS, 0
    ledger_note = "fnl-delegate is not installed"
    if LEDGER.exists():
        try:
            delegation, first_pass, fp_week, runs = ledger_metrics(load_ledger(), start)
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

    return {
        "generated": fm.now().isoformat(timespec="seconds"),
        "period": {"from": start.isoformat(), "to": today.isoformat(), "days": days},
        "sessions": {"total": len(by_sid), "with_edits": with_edits, "dispatch": excluded, "unclassified": unclassified},
        "errors": fm.errors_count(), "missing": missing,
        "kpi": {"router_coverage": ratio(covered, eligible), "sessions": len(by_sid) if events else None,
                "calls": sum(uses.values()) if events else None, "first_pass": first_pass,
                "spark": {"router_coverage": [ratio(c, n) for c, n in zip(cov_week, eligible_week)] if eligible else None,
                          "sessions": sessions_week if events else None, "calls": calls_week if events else None,
                          "first_pass": fp_week if first_pass is not None else None}},
        "router": {"covered": covered, "missed": missed, "excluded": excluded, "unclassified": unclassified, "eligible": eligible} if eligible else None,
        "use": use or None, "load": load, "depth": depth_rows or None, "delegation": delegation or None,
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
    body = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return "window.FNL_DATA = " + body + ";\n"


def cmd_run(args):
    folder = fm.ensure_dir(fm.state_dir(), follow=True)
    target = folder / "data.js"
    if args.if_older is not None and target.exists() and (folder / "dashboard.html").exists():
        if fm.now().timestamp() - target.stat().st_mtime < args.if_older * 60:
            return
    data = build()
    fm.atomic_write(target, js_text(data))
    fm.atomic_write(folder / "dashboard.html", PAGE.read_bytes())
    miss = sorted(data["missing"])
    print("dashboard %s · %s to %s · sessions %d · unclassified %d · writer errors %d%s" % (
        folder / "dashboard.html", data["period"]["from"], data["period"]["to"], data["sessions"]["total"],
        data["sessions"]["unclassified"], data["errors"], " · missing: " + ", ".join(miss) if miss else ""))
    if args.open:
        webbrowser.open((folder / "dashboard.html").as_uri())


def cmd_consent(args):
    fm.write_consent(args.retention)
    print("consent recorded: events kept %d days" % args.retention)


def cmd_purge(args):
    if not args.yes:
        sys.exit("purge: pass --yes once the user has confirmed")
    removed = fm.purge_store()
    for name in ("data.js", "dashboard.html"):
        path = fm.state_dir() / name
        if path.is_file() and not path.is_symlink():
            path.unlink()
            removed += 1
    print("purge: removed %d files" % removed)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="write data.js and dashboard.html")
    run.add_argument("--open", action="store_true", help="show the page in the default browser")
    run.add_argument("--if-older", type=int, metavar="MINUTES", help="skip when data.js is newer than this")
    run.set_defaults(func=cmd_run)
    consent = sub.add_parser("consent", help="record consent and retention")
    consent.add_argument("--retention", type=int, required=True, choices=fm.RETENTIONS)
    consent.set_defaults(func=cmd_consent)
    purge = sub.add_parser("purge", help="delete recorded events and the dashboard files")
    purge.add_argument("--yes", action="store_true")
    purge.set_defaults(func=cmd_purge)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
