# Routing and posting interface

## Host sections

Enforcer: `review_config.py`, read-only. Only `fnl-setup` writes settings after the user confirms the shown lines (advisory, agent judgment). Read from canonical `host.md` under the resolved data root; repository config and `ORCHESTRATION_HOST_CONFIG` never supply these sections. Fenced examples are ignored. Duplicate headings or keys, unknown keys, malformed lines and sections over ten lines discard that whole section.

`## Agent roles` has one line per optional key:

```markdown
## Agent roles
- code review: antigravity
- security review: codex
- navigator: claude
- judge: host
```

Role values must name a family recorded in `## Agents on this machine`; `judge` permits only `host` or `jev` and defaults to `host`. An assignment to an absent family is skipped for that review kind; an unknown or unrecorded family invalidates the whole role section, so routing uses the capability order among present families. The presence table remains a restriction even when its check dates are stale. Presence and roles do not grant model access or permission.

`## Review posting` uses a checked date on each family line:

```markdown
## Review posting
- claude: unverified (checked 2026-11-07)
- codex: yes (checked 2026-11-07)
- antigravity: no (checked 2026-11-07)
```

Only `yes`, `no`, `unverified`, a valid non-future date, and the three family keys are accepted. Invalid or absent sections mean no verified posting preference. A date records the observation, not a permission grant or an expiry policy. The coordinator verifies the marker and expected comment identity before setup records `yes` (advisory, agent judgment; `post_review.posting_verified` checks the supplied evidence).

## Route

```text
python3 -I <skill folder>/scripts/review_route.py [--kind code|security|both] [--lane] [--security-trigger]
```

Enforcer: `review_route.py`. Run in the checkout being reviewed. It resolves HEAD and its final `Co-Authored-By` trailers from local Git objects, including packed objects and linked worktrees, without invoking git. Without a unique trailer family, only a ledger record bound to that exact `head` can identify the author; old task or project labels are insufficient. Unknown or ambiguous authorship exits 2, never a guessed independent review.

The router imports `quota_probe.status_lines`, the implementation of `quota_probe.py status`, in process. It never calls `read`, launches a CLI or starts a model. The coordinator uses `fnl-delegate` to refresh due candidate readings before routing (advisory, agent judgment). A current rate-limit marker excludes its family; a cache older than eight hours excludes nothing. Claude installs use `week-all` separately: one available install keeps the family eligible. Other families are excluded when a relevant pool is below ten percent with a future reset. `agy` in quota status maps to `antigravity` in roles. The user's own quota statement takes precedence (advisory, agent judgment).

Selection: a valid assigned independent family first; otherwise present, available independent families in code capability order (Claude, Codex, Antigravity), with posting `yes` preferred between otherwise valid fallback candidates; otherwise the available author's family. A blocked or absent author is not a fallback. An unknown presence section or no available family exits 2.

Output has no heading: one `family form reason` line per kind, code then security by default. `form` is `agent` for Claude or `headless` for Codex and Antigravity. Reasons start with `assigned`, `capability` or `same-family`; `-lane` and `-one-run-two-comments` describe combined coverage. Exit 0 means routed; exit 1 with `--security-trigger` and `same-family` means stop for the user's decision; exit 2 means invalid input or unavailable evidence. Do not dispatch after exits 1 or 2 (advisory, agent judgment).

Enforcers: `merge_check.py --lane` decides lane eligibility; invoking it before `review_route.py --lane` is advisory (agent judgment). The lane uses the code route for both kinds. The coordinator makes one run with one packet when both lines name the same family and obtains two comments, not two runs (advisory, agent judgment).

## Packet

Enforcer: `review_route.build_packet(checkout, base, head, criteria, decisions, known_consumers)`. The coordinator calls this Python function when assembling a brief. It resolves refs to full OIDs and computes per-file additions/removals, binary changes and mode changes from local Git trees and blobs. This is the local-object equivalent of the packet's `git diff --stat`; it runs no subprocess. Unsupported or oversized objects fail closed. The return value contains `base`, `head`, `diff_stat`, `known_consumers`, `acceptance_criteria` and `decisions`. Criteria, decisions and starting consumers come from the coordinator, never inferred by the script. Keep it in the review brief; no packet content enters an event or receipt (advisory, agent judgment).

Add test results and limits, requested coverage, the hard budget and the triggered security-audit requirement before dispatch. Re-review resumes the same run (advisory, agent judgment). Reading the diff and extending the known-consumer list remain the reviewer's work.

## Post

Enforcer: `post_review.py`. In the authorized checkout:

```text
python3 -I <skill folder>/scripts/post_review.py 31
```

This creates an owner-only run folder under the canonical data root and an empty `body.md`, and prints that absolute filename. Fill the created file with the finished report. A read-only reviewer that cannot create or fill the file returns `cannot-post: no-permission` with its report; do not broaden its tools silently (advisory, agent judgment). Then:

```text
python3 -I <skill folder>/scripts/post_review.py 31 --body-file <created body.md>
```

The PR number is the only positional argument and `--body-file` the only accepted option. The script derives the repository from the checkout's `origin` GitHub remote; `--repo`, `--web`, `--edit-last` and abbreviated flags are rejected. GitHub SSH and HTTPS remotes are accepted; other hosts and credential-bearing URLs are refused. Its internal fixed argv pins `github.com` even when the environment names another host or repository.

The body must be a regular owner-only file, at most 64 KiB, inside its private run folder. Descriptor traversal refuses symlinks and resolved-path escapes. Its exact first line must be:

```text
<!-- fnl-review kind=code head=0123456789abcdef0123456789abcdef01234567 verdict=APPROVE -->
```

`kind` is `code` or `security`, the head is forty hex digits, the verdict is `APPROVE` or `REWORK`, with optional ` lane=yes` immediately before ` -->`. Content beyond that first line is not inspected. A comment in a public repository is public. Keep report content out of telemetry (advisory, agent judgment).

Only `gh pr view` and `gh pr comment` run, with fixed argv and no shell. The wrapper checks the current PR head, passes already checked bytes on stdin (never asks gh to reopen the body path), posts once and observes the body afterward. Exit 0 means prepared or observed posted; exit 1 prints exactly `cannot-post: no-cli|no-network|no-auth|no-permission|other`, choosing one reason; exit 2 refuses invalid input. After an uncertain post, do not retry automatically: inspect the PR first (advisory, agent judgment). The wrapper stores no token, host setting, event or receipt. Its private draft is report content, not a metadata receipt.

Enforcers: the coordinator's relay policy and `record.py` for its metadata receipt (advisory, agent judgment for invoking and counting once). A cannot-post report may be relayed only once per run when the repository's existing approval authorizes that kind of relay. Explain the exact missing capability and the `fnl-setup` repair to the user. Relay never verifies the reviewer's own posting identity and never becomes the normal path. The wrapper grants no posting or relay authority; approved host permissions and the repository's adoption govern that authority.
