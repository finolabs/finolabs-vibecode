# Proof nudge: ask for proof when a session committed an unverified head

Status: implemented; for 0.3.2 (owner decision 2026-11-17, pack review row A2); `scripts/proof_nudge.py`, `tests/test_proof_nudge.py`; live delivery on Claude Code unverified.

## Why

The proof step is agent judgment and is almost never taken: in the usage metrics up to 2026-11-17, 703 sessions committed and 1 of them loaded `checks`. The session-start rules now carry the proof rule inline (0.3.2), but nothing reminds an agent at the moment it is about to report. A `Stop` hook runs at that moment.

## Rule it falls under

The hook prints; it never denies, blocks or edits anything, so it falls under the general hook rule of the repository instructions, which says a hook never blocks a session, exits 0 and fails closed; it needs no scoped exception. It records no metrics event, so the metadata-only rule does not apply, and it makes no network call. Its output is the Stop hook's `hookSpecificOutput.additionalContext`, which Claude Code documents as "non-error feedback": the conversation continues for one turn so the agent can act on it, unlike `decision: "block"`, which the hook never emits. The same loop guards apply (`stop_hook_active` and the host's continuation cap), and the hook prints nothing when `stop_hook_active` is true. A plain print on `Stop` does not reach the model on Claude Code (the hooks reference lists plain stdout as context only for `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart` and `PostModelSwitch`), so the JSON form is required.

## Design

- Hooks, in their own groups of the Claude Code manifest, never in the metrics group: `SessionStart` runs `proof_nudge.py start`, and `Stop` runs `proof_nudge.py`, each `2>/dev/null; exit 0` with a 5-second timeout.
- Start: `start` writes the session's mark with the current time when the session has none (a resume or compaction keeps the first start) and prints nothing. A `Stop` that finds no mark (the plugin was installed mid-session) writes one the same way and prints nothing.
- Committed this session: the working folder's checkout is found with `git_metadata.checkout_dirs` (owner-checked, no-follow, no Git process). HEAD is read from the checkout's `HEAD`, then the loose ref under the common folder or `packed-refs` (at most 1 MiB); only `refs/heads/...` refs are followed. The checkout's own HEAD reflog (`logs/HEAD`, the last 64 KiB) is read and, per entry, only the new commit id, the time and the action word before the first colon are kept; the subject is discarded. The session committed the head when an entry whose action is `commit` (including `commit (amend)`, `commit (merge)`, `commit (initial)`), `cherry-pick` or `revert` names the current HEAD with a time at or after the session's start. A head reached by checkout, reset, rebase, merge or pull does not count.
- Proof: a `checks` receipt (`<data root>/state/checks-receipts/<repository code>.json`, written by `checks.py` in local-receipt mode) or a verification receipt (`<data root>/state/verification/<dispatch id>.json`, written by `verify_claim.py` and `checks.py run --dispatch`) whose `head` is the current HEAD; a verification receipt counts only with `tests` equal to `passed` (a `failed` or `not-run` one is no proof), and a checks receipt is written only when the whole list passed. Only the `kind`, `head` and `tests` fields are compared; at most the 500 newest verification receipts (by name, which sorts by time) are read, each at most 64 KiB.
- Throttle: once per head per session. The mark is `<start> <16 hex>`, the second field the first 16 hex characters of the SHA-256 of the head the hook last reported, written atomically with mode 0600 in `<data root>/state/proof-nudge/<sha256(session id)[:16]>`, at most 200 files, oldest removed first. The mark is written before printing; if it cannot be written, nothing prints. A later commit gives a new head and may print again.
- Line, fixed: "This session committed the current head and no checks or verify_claim receipt names it. Before reporting the work as done, run the targeted tests for the change and read their output."
- Failure: any error, an unsafe or missing file, a malformed mark or input, or a working folder outside a repository prints nothing and exits 0. `FNL_PROOF_NUDGE=off` disables both modes.

## Limits

- Advisory: tests run and read without a receipt (plain test commands, or `checks` outside local-receipt mode) leave nothing the hook can read, so the line can fire once for a head that was in fact tested.
- Another writer committing in the same checkout after this session started counts as this session's commit; sessions sharing one checkout are rare and the line fires at most once per head.
- A session that commits in another repository than its working folder is not seen.
- Codex and Antigravity are not covered; Codex's `Stop` output contract is unverified.
