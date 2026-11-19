# Start: wake the coordinators, check merge blockers, build the queue

`<script>` is `afk.py` from `delegate`, as in `SKILL.md`. These steps follow a successful `start` on the user's own `/afk start`; that invocation is the authority to message other sessions, for this one start only. Everything here is advisory (agent judgment) except the script answers it names.

## Wake the coordinators

1. List the host's sessions with its session tools. Which tools and which fields belong to the host facts in `delegate` `references/agents/<host>.md`.
2. Candidates: sessions that are not archived, were not started by another session, and whose working folder lies in a repository's main checkout or one of its worktrees. Never message a child session; its coordinator hands it work.
3. Keep a repository only when it is set up for afk: run `python3 -I <script> effective` in its folder and keep it when the output holds `Project settings: recorded` (script). Never write the list of repositories or sessions anywhere; rebuild it at each start.
4. One session per repository: the one whose title marks it as the coordinator (`tidy` titles), else the most recently active candidate. Two or more marked coordinators in one repository: message none and list the repository as ambiguous.
5. Send each kept session this message, filling in only the repository's folder name, nothing else:

   > afk start for repository `<name>`. If this session coordinates `<name>`, check whether an away lease is live (`afk.py effective`). Only if `afk.py goal` accepts your queue: load the afk lease rules, set the host goal to the line it prints, start a self-paced loop, settle every question through afk "Decide", and end a turn only through `afk.py log --kind idle`. If `<name>` is not your repository, ignore this message.

6. In the start summary report each repository messaged and its session, each ambiguous repository, each candidate repository not set up for afk, and the line "repositories with no open session are not covered".
7. Build this session's own queue the same way (below).

Where the host has no tool that lists and messages sessions (Codex and Antigravity today), print the message once with "this repository" in place of the name, for the user to paste into each coordinator session they want covered, and say that no other session was seen.

The message is a notification, never a grant: it carries no task data, lease time or authority. A receiving session acts only when `goal` accepts, which needs a live lease (script), and ignores a message naming another repository.

## Merge-blocker preflight

Before the user leaves, for each covered repository, check the open pull requests its queue names for what would park a merge, and report each cause once with its fix. Fix nothing in another repository without the user's answer.

- Run `merge_check.py <n> --repo <owner/name>` (from `review-gate`) for each, adding `--independent` where the lease merges by independent review (script). Report each `BLOCK` cause once:
  - no checks reported and no local receipt mode: "turn on local receipts with `/setup add checks` in that repository";
  - an author family it cannot tell;
  - a missing review marker.
- Read the repository's instruction files for a rule that keeps merges for the owner's own session. When one exists and no afk overlay is in force, report: "add an override entry with `/setup instructions` in that repository".

## Queue

Gather the repository's work before running `goal`: its open pull requests, the open tasks of the current spec, open review findings and the steps after a merge. Leave out work the lease does not allow and work that waits on the owner. Write a JSON list of at most 30 items, each `{"label": "<short task label>", "kind": "pr|review|merge|task|fix|release-step|other", "minutes": <1..480>}`, to a file under `.finolabs/briefs/`, and run `python3 -I <script> goal --items-file <file>` (an empty list when there is no work). Labels are plain words: no task data, paths or secrets (script).

`goal` refuses without a live lease and outside a repository (script). It prints the goal line for the host's goal command, the numbered queue with the minutes left, and a warning when the queue is short or longer than the lease; when it is short, add the next work with another `goal` call, which appends. Each change to the queue raises its revision, so an `idle` record made before someone added an item no longer ends a turn.
