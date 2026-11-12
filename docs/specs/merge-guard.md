# Merge guard through host permission rules

Status: deferred; the release 0.2.0 record moves the backlog target to 0.2.1 with autopilot; no permission-rule writer is built in 0.2.0. The accepted design remains below; implementation and unresolved host decisions still need owner approval.

Originally deferred to 0.2.0 (owner, 2026-11-06), now a 0.2.1 backlog target: the hosts already ask before a merge in their default modes, and the owner
authorizes merges in chat; the remaining gap is unattended runs, which autopilot settles (`autopilot.md`).
The design below stays for that use.

Decision: 2026-11-06, owner agreed (harness synthesis, step 1). Goal: add a host prompt on the
common merge and publish commands, so "merge, tag and publish need the owner" is more than advice there,
with no new blocking plugin hook and so no new `CLAUDE.md` exception. It is a prompt, not a complete
guard (see "What it does not cover"). `setup` writes the rule after a
separate consent, a stored preview and a digest, like `compaction-threshold.md`.

## What the hosts document (not yet run by us; the writers must verify with the host's own checker)

- Claude Code: `permissions.ask` in a config folder's `settings.json` holds rules such as
  `Bash(gh pr merge *)`; precedence deny > ask > allow, so an `ask` rule outranks any broader
  `allow`. Managed settings can preempt user settings. Matching of shell commands is best-effort
  (wrapped commands can escape it).
- Codex: `prefix_rule(pattern=["gh","pr","merge"], decision="prompt")` in a `*.rules` file under
  `<CODEX_HOME>/rules/`; the most restrictive decision wins; `codex execpolicy check --rules <file>
  -- <command>` tests a rule. It governs commands that leave the sandbox. Restart needed.
- Antigravity: permission rules `action(target)` with Deny > Ask > Allow, stored in the user's own
  settings; the exact file and key for a remembered `ask` rule are unverified. Out of scope for
  this version (see Not in scope).

## Parts

### `skills/setup/scripts/merge_guard_setup.py` (stdlib; no network, no subprocess)

Pattern: `compact_setup.py` (stored private preview 0600 at `<data root>/state/merge-guard/preview.json`,
digest, 60-minute expiry, owner/mode/symlink/git-work-tree refusals, backups
unique backups (below), atomic writes, fixed content-free errors).

- `preview --host claude|codex [--folder <abs>]... [--rules <names>] | --remove`: shows, per target,
  the exact lines to add or remove and the digest. Writes only the preview.
- `apply --digest <64 hex> --yes`: applies only the stored preview, re-checking target hashes.
- Rule set, each selectable, all recommended: `gh pr merge`, `gh release create`, `git push --force`,
  `git push -f`, `git push --delete`. Fixed list in the script (tag pushes are left out: too noisy); the
  user picks a subset; no free-text patterns.
- Target checks, as in `compact_setup.py`: every path is absolute; each folder (`--folder`, `CODEX_HOME`
  or the account default) and each file is owned by the user, not a symlink, not group- or
  world-writable, and outside every git work tree; otherwise refuse.
- Backups: a unique name per run (`<file>.bak-YYYYMMDD-HHMMSS-N`, never overwriting an existing
  backup), created with the source file's mode and never wider than 0600, because `settings.json` may hold
  tokens.
- Claude: adds the matching `Bash(...)` entries to `permissions.ask` of each listed config folder's
  `settings.json` (default `~/.claude`; extra folders as `--folder`, at most four). Parses JSON with
  duplicate-key and non-finite refusal, keeps every other key, adds only missing entries, never
  touches `allow`/`deny`, preserves unrelated formatting as far as `compact_setup.py` does.
- Codex: writes a dedicated file `<CODEX_HOME>/rules/finolabs-vibecode.rules` (never `default.rules`),
  `prefix_rule` per selected rule, decision `prompt`, with a one-line justification. The file is
  owned wholly by the script (removal deletes it). Warn that Codex must be restarted and that
  commands that do not leave the sandbox are not covered.
- Both: print the host's own test where one exists (`codex execpolicy check ...`) as a command for the
  user; the script runs nothing.
- Removal is manifest-based: apply records in `<data root>/state/merge-guard/installed.json` (0600) exactly
  the entries it added that were not already present, and the target file's hash after the write.
  `--remove` takes out only those entries (an `ask` rule the user already had stays) and, for the Codex
  file, deletes it only when its first line is the script's marker comment and its hash matches the
  recorded one; a changed file is left and reported.
- Antigravity: refuse with a fixed message ("not supported in this version").

### Skill and doc text

`setup` gets one optional step (after the compaction steps): a separate neutral Yes/No consent
(none preselected), the list of rules with the recommended set, the preview, then apply. Advisory
(agent judgment) that the question is asked and the preview shown; the script enforces digest,
expiry and file safety; the host enforces the prompt. State that a prompt asks the human, that
it applies to the agent's own merges too, and that matching is best-effort. `review-gate` "Pull
requests" and `delegate` say the merge prompt is a prompt on those commands where the guard
is installed, and still advisory where it is not. `PRIVACY.md`: the script writes only to the
named settings/rules files and the private preview; nothing is sent. README row, CHANGELOG
`Unreleased`, `docs/specs/index.md`.

## What it does not cover

Tag pushes, `gh api .../merge`, `git push +main` and `--force-with-lease`, `git -C <dir> push`, `gh -R
<repo> pr merge`, `npm publish` and anything run through a wrapper. Claude matching is best-effort;
Codex covers only commands that leave the sandbox; behaviour in non-interactive and bypass modes is
unverified. A prompt does not check that a review exists. The only non-bypassable gate is the
repository's server-side rules. The skill text says all of this.

## Not in scope

- Antigravity (storage unverified); server-side branch protection (the only non-bypassable gate;
  mention it in the skill text as the complement).
- Deny rules, allow rules, or any broader permission change; `requirements.toml`/managed settings.
- A hook of any kind.

## Acceptance

1. Preview writes only the private preview; apply refuses a short or wrong digest, an expired preview,
   a changed target, a symlink, wrong owner, group/world-writable file or folder, a git work tree.
2. Claude: entries added once (idempotent), other keys and other `ask`/`allow`/`deny` entries unchanged,
   duplicate keys refused, `--remove` removes only ours, multiple folders, dedupe by identity.
3. Codex: dedicated file created 0600, `default.rules` never touched, content exactly the selected
   `prefix_rule` lines, `--remove` deletes it only when its marker and recorded hash match.
4. Antigravity refused; unknown rule names refused; no free-text pattern accepted.
5. Verification before the recommended set ships, recorded in this spec: Claude with a throwaway config
   folder (`claude -p` asked to run `gh pr merge --help` prompts), Codex with `codex execpolicy check`.
6. Removal: a pre-existing identical `ask` rule survives `--remove`; a changed Codex file is left; backups
   never overwrite and are not wider than 0600; a symlink, wrong owner or work-tree target is refused.
7. Docs updated; `check-references.py`, `claude plugin validate .`, targeted tests pass under a
   world-writable `/tmp`; no hook file changed.

## Open

- Behaviour of `ask`/`prompt` in non-interactive and bypass modes.
- Whether `permissions.ask` entries survive `/permissions` edits and plugin updates.
- Antigravity rule storage and a writer, in a later version.
