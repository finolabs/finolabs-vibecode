# Run hygiene: keep credentials out of delegated runs (release 0.2.0)

Status: draft; owner direction recorded on 2026-11-07; implementation after package B (`agent-roles.md`) lands.

## Why

On 2026-11-07 a delegated Codex run fixed a failing test with an assertion that printed the whole process environment.
Every variable the run inherited (cloud, source-hosting, package-registry, model-provider and admin keys) reached the
run's log and the provider's model context. The log could be redacted afterwards; the provider's copy could not, and the
keys had to be rotated. Nothing in the plugin made this harder: briefs did not forbid it, the dispatch command inherited
the coordinator's full environment, and no one scanned a finished run's log. Vibe coders who delegate to agents hit the
same hole, so the practice belongs in the plugin, with scripts as enforcers where a script can enforce it.

## Rules and enforcers

Each rule names its enforcer. Anything marked advisory is agent judgment.

1. **The brief forbids it.** Every brief names, under Constraints: never print, dump, log or assert on the process
   environment or any credential; tests build a synthetic environment and compare only variable names. Enforcer: the
   `fnl-handoff` template carries the line, and `brief_check.py <brief>` refuses a brief without it, without the
   other required headings, or containing a secret-shaped value. The host-config command forms call it before a
   dispatch. Writing the brief is advisory; the refusal is the script's.
2. **A delegate starts with an allowlisted environment.** `delegate_env.py` runs the agent command with only the
   variables a run needs: `PATH`, `HOME`, `LANG`, `TMPDIR`, `FNL_DISPATCH_ID`, and the names listed in a
   `## Delegate environment` section of the host config for that agent family (names only, confirmed by the user in
   `fnl-setup`, empty by default; a family that logs in through its own login store needs none). A variable the
   section names but the coordinator lacks is skipped. The coordinator's other variables never reach the child.
   Enforcer: the script; the host config only holds names.
3. **Test commands in a checkout use an allowlisted environment too.** Already built for `verify_claim.py` in package
   B; this spec adds that the same helper is the only way the plugin starts an untrusted command.
4. **A finished run's log is scanned.** `log_scan.py <log>...` looks for secret-shaped values (known key prefixes,
   private-key blocks, long high-entropy tokens after a name containing KEY, TOKEN, SECRET, PASSWORD or CREDENTIAL)
   and for environment dumps (many `NAME=value` or `'NAME': 'value'` pairs). It prints only file, line and the variable
   name or pattern kind, never the value. `log_scan.py redact <log>` previews and, with `--yes --digest`, replaces the
   values with `[REDACTED]` through an atomic write, keeping the file's owner-only mode. The coordinator runs it
   after every run and before reading or quoting a log (advisory); `ledger.py finish` prints a warning when the run's
   log has findings (script) and records `log_clean: false` without any content.
5. **A leak is reported by name, never chased.** When a finding shows a credential reached a log or a model, the
   coordinator tells the user the variable names and what could not be undone, redacts local copies, and does not look
   for the credential's source or read credential stores; rotation is the owner's (advisory, matching the user-scope
   rule that credentials are never hunted).
6. **The lesson is kept.** The incident is stored as a lesson in the user's knowledge base and summarized in
   `fnl-session-hygiene` "Remember or recall" as an example of a corrected lesson (advisory).

## Changes

- `fnl-handoff`: Constraints line and a short "Secrets and environments" paragraph; the template check by
  `brief_check.py`.
- `fnl-delegate`: dispatch forms in `references/agents.md` go through `delegate_env.py`; the host template gains
  `## Delegate environment`; "Accept" gains the log scan; `ledger.py finish` warning and `log_clean` field.
- `fnl-setup`: `delegation` feature asks, per present agent family, whether any variable must pass through (default
  none), with a neutral Yes and No; names only.
- `fnl-verification`: states that the environment helper is the only way to start an untrusted command.
- `PRIVACY.md`: the log scan and redaction are local; `log_clean` is a boolean.
- `CHANGELOG.md`, README, `fnl-ask` map: current-surface wording.
- No change to `CLAUDE.md`: no network call, no new class of command (the helper starts the same agent commands the
  dispatch already starts).

## Acceptance

- `brief_check.py` refuses a brief lacking the environment rule or containing a secret-shaped value (tests).
- `delegate_env.py`: a child started through it sees only the allowlisted names; an extra variable in the
  coordinator's environment is absent (test compares names, never prints the environment); a name from the host
  config passes; an invalid name or a duplicate is refused.
- `log_scan.py`: finds a planted fake key, a private-key block and a dumped synthetic environment; output holds no
  value (test asserts the planted values do not appear); `redact` previews, requires `--yes` and the digest, and
  leaves no value in the file.
- `ledger.py finish` records `log_clean` and warns without reproducing content.
- Setup consent for pass-through names is a separate neutral Yes and No; none preselected.
- Every touched skill file respects the size limits of `setup-restructure.md`.

## Open decisions

None. Names of the scripts and the `log_clean` field may change in review.
