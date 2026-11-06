---
name: fnl-status
description: Open the finolabs-vibecode usage dashboard, a local page with how often the router and skills fired, what they cost to load, and how delegated runs and reviews went. Refreshes its numbers from the usage events and the dispatch ledger first, and lists dispatches still open. Run only when the user asks for it, or to delete the recorded usage data.
argument-hint: "[purge]"
disable-model-invocation: true
---

# Usage dashboard

The dashboard is a static page, `dashboard.html`, in the resolved data root's `state/` folder. An absolute `FNL_STATE_DIR` remains a dashboard/events override; before relocation, an existing `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` is used while the default state folder is absent. It loads its numbers from a `data.js` beside it. This skill never writes or edits the page; a script rebuilds the data and copies the shipped page.

The page has five tabs: Overview (activity, router coverage, skill and agent use, depth vs outcome and load cost), Agents (Running now), Project (task progress), Delegation (delegation and Judge), and Reviews (the review gate). Agents and Project show "not available yet" placeholders until their data sources exist.

The scripts are in this skill's base directory: `scripts/refresh.py` builds the dashboard data, and the `fnl-delegate` skill beside this one holds `scripts/ledger.py`. Without `fnl-delegate`, the dashboard still shows the usage events and names the ledger as a missing source.

**Arguments:** $ARGUMENTS

## Steps

1. Run `python3 -I <refresh.py> run --open`. It rebuilds `data.js`, copies the page and opens it in the default browser. Done when it prints its one-line summary. While its tab is visible the page reloads `data.js` every 5 seconds, and the hooks rebuild it during a session, so the user can leave it open.
2. Report that line, then name each missing source it lists and what fixes it: consent not given means `fnl-setup`; no events means the plugin's hooks need the whole plugin installed and a session started after consent; a missing ledger means `fnl-delegate` "Ledger".
3. Run `python3 -I <ledger.py> open`. It prints each open dispatch's age against its budget. For each one past its check deadline (half the budget), check liveness from artifacts as `fnl-delegate` "Budget and liveness" says and mark it **running**, **stalled** or **ended without a finish line**. A coordinator closes a record only when its log or the repository shows how the run ended, with that outcome and a note that it was closed late; otherwise list it and ask the user.
4. Read the `Review by` date (ISO, `YYYY-MM-DD`) at the top of `references/models.md` in the `fnl-delegate` folder. When today is past it, the capability map is stale: say so, with the date, since routing still reads it.

The page marks a delegation group of fewer than five runs with an open ring and passes no judgment on it. A group of five or more is judged by first-pass acceptance below 60%.

## Purge

Questions below ask through the host's native question tool when the session has one. Ask in text when the session has no such tool, the tool is refused or fails, nobody can answer (a delegated or headless run records the open decision and never assumes or invents an answer), or the decision is free text. The enforcer is agent judgment, so this is advisory.

**Advisory (agent judgment):** Talk to the user in the language they are using, including questions and option labels; keep command names, flags, file paths, skill names and other technical names unchanged. Script output stays English; report it to the user in their language (advisory, agent judgment).

When the argument is `purge`, skip the steps above and ask the user through the host's native question tool when the session has one to confirm deleting the recorded events, `data.js` and `dashboard.html`. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes. Only after a clear yes, run `python3 -I <refresh.py> purge --yes`, and report how many files it removed. Never run it unasked.

Their consent record stays, so recording continues; to stop it as well, ask separately whether to withdraw consent, through the host's native question tool when the session has one. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes. Only after a second yes run `python3 -I <refresh.py> consent --revoke --yes` (or the user sets `FNL_METRICS=off`).

## What is recorded

Only when the user consented in `fnl-setup`: the plugin's hooks append metadata to `events-YYYY-MM.jsonl` in the state folder (a time, a session id, a short repository code, a skill or agent name, a depth, a review verdict, a kept-task count with its reason and who settled it, judge receipt site, grader, result and followed status), never prompts, code, command text or file paths. Nothing is sent anywhere.
