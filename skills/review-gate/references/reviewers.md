# Reviewers, packet and scope

Detail behind `SKILL.md` "Instruments", "Who reviews", "The reviewer packet" and "Review scope". The enforcers and triggers named in `SKILL.md` apply here unchanged.

## Routing

`review_route.py` reads canonical roles, presence, posting checks, commit authorship and quota status locally. The coordinator refreshes due candidate quota readings through `delegate` before routing; this script never starts a reading, model, process or network call.

## Engines per family

Call the selected family directly (advisory, agent judgment); no reviewer routes for another:

- **Claude Code**: `fnl-reviewer` with `/code-review`, or `fnl-security-reviewer` with `/security-review`, as the engine.
- **Codex**: a headless `codex review --base <branch>` run (or `--commit <sha>`), with the packet and the requested review kind.
- **Antigravity**: a headless `agy` run that reads the diff; `/diff` and the review pane are human tools, not AI review engines.
- **Companions**: `code-review` from [mattpocock/skills](https://github.com/mattpocock/skills) for standards and spec; `security-audit` from [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill) when `security-review-gate` triggers. Name that requirement in the brief. A cloud multi-agent review needs the owner's approval before code leaves the checkout.

Delegated runs follow `delegate` for ledger, brief and hard cap (advisory, agent judgment). A missing engine is disclosed; apply the packet and findings rules directly and tell the caller that `setup` guides installing it. Re-review resumes the same review run (advisory, agent judgment).

## Who reviews

- **Independent**: `review_route.py` chooses an assigned present family with quota before the capability fallback; posting `yes` breaks ties only after independence and a valid assignment. A role or a present CLI grants no permission, reachability or model access.
- **Both kinds on one family**: one run, one packet, two comments, each with its own marker. The low-risk lane uses the code route for both after the lane check succeeds (rule 7). These are coordinator obligations, advisory (agent judgment).
- **Tier and effort**: follow `delegate`; at least strong for code and frontier for a triggered security review. The Claude agent files keep `model: inherit`; select the allowed model through the host when supported (advisory, agent judgment).

## The reviewer packet

Build the packet with `review_route.build_packet(checkout, base, head, criteria, decisions, known_consumers)` (script). It resolves the two git commits and computes diff statistics from local objects; known consumers are a starting list supplied by the coordinator. Keep the packet outside events and receipts. Add the test results, coverage and budget below (advisory, agent judgment). The packet is self-contained, with no whole-history fork:

- acceptance criteria and the decisions the change rests on; with Spec Kit, the story's acceptance criteria and the feature's `plan.md`;
- the exact binding: base and head SHAs or the commit range, and a fixed worktree when other writers are active;
- known consumers of the changed code, as a starting list the reviewer extends;
- tests and configuration run, with their results and limits;
- the requested coverage (correctness, security, performance) and the report format: each finding with file, line, severity and a concrete failure scenario.

## Impact set

The impact set, traced from the changed symbols rather than guessed:

- consumers of each changed function, type, endpoint, event, command, configuration key, schema or column (name search, language-server references, route and handler tables);
- what the change now depends on: functions called with new arguments or new assumptions, new packages, environment;
- contracts: public APIs, serialized formats, database schema and migrations, permissions;
- the tests covering the changed code, and whether they still exercise the new behavior.
