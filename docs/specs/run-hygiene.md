# Run hygiene: keep credentials out of delegated runs (release 0.2.0)

Status: implemented; release 0.2.0 brief lint, environment allowlists, guarded log scan/redaction and ledger states have local tests; real-host dispatch remains unverified and private HOME is deferred.

## Why

On 2026-11-07 a delegated Codex run fixed a failing test with an assertion that printed the whole process environment.
Every variable the run inherited (cloud, source-hosting, package-registry, model-provider and admin keys) reached the
run's log and the provider's model context. The log could be redacted afterwards; the provider's copy could not, and the
keys had to be rotated. Nothing in the plugin made this harder: briefs did not forbid it, the dispatch command inherited
the coordinator's full environment, and no one scanned a finished run's log. Vibe coders who delegate to agents hit the
same hole, so the practice belongs in the plugin, with scripts as enforcers where a script can enforce it.

## Rules and enforcers

Each rule names its enforcer. Anything marked advisory is agent judgment. The scope is stated plainly: these rules keep
credentials out of the **environment** and out of **logs the plugin reads or stores**. They do not claim to stop an
agent that reads credential **files** it can reach (see rule 2, residual risk).

1. **The brief forbids it.** Every brief names, under Constraints: never print, dump, log or assert on the process
   environment or any credential; tests build a synthetic environment and compare only variable names. Enforcer: the
   `fnl-handoff` template carries the line (it extends the existing bullet "never read env or credential files" instead of repeating it), and `brief_check.py <brief>` is a lint that refuses a brief without it,
   without the required headings, or containing a secret-shaped value; its message names the rule and the line number,
   never the matched text. The dispatch command forms in `fnl-delegate` `references/agents.md` call it before a dispatch. It is a lint, not a control: the
   allowlist in rule 2 is the control.
2. **A headless delegate starts with an allowlisted environment.** `delegate_env.py`, called by the dispatch command forms in `agents.md` and never by a hook (it runs only when the coordinator dispatches), reuses the `environment()` pattern of `quota_probe.py` and runs the agent command with only
   `PATH`, `HOME`, `LANG`, `TMPDIR`, `FNL_DISPATCH_ID` and the names listed in a `## Delegate environment` section of
   the host config for that agent family (empty by default), plus what the command form of a family sets explicitly
   (for example `CLAUDE_CONFIG_DIR` for a second Claude install, whose value the form chooses and the coordinator's
   environment does not supply). A family whose login lives in its own store needs no inherited variable. Scope: headless
   dispatches through the command forms, including the agybird runner; interactive sessions the user starts, desktop-app
   sessions and in-session subagents inherit the user's environment and are **not covered** (the report says so). The coordinator's other variables never reach the child. Names obey a strict pattern
   (`^[A-Z][A-Z0-9_]{0,63}$`, no wildcard, no value, no duplicate) and are refused when they are loader or
   interpreter controls (`LD_*`, `DYLD_*`, `BASH_ENV`, `ENV`, `NODE_OPTIONS`, `PYTHON*`, `PERL5*`, `RUBY*`, `GIT_*`
   command variables, `*_PROXY`, `SSL_CERT_*`, `NODE_EXTRA_CA_CERTS`, `REQUESTS_CA_BUNDLE`,
   `CURL_CA_BUNDLE`, `NODE_TLS_REJECT_UNAUTHORIZED`, `NODE_PATH`, `PERLLIB`, `SHELLOPTS`, `PS4`,
   `PROMPT_COMMAND`, `JAVA_TOOL_OPTIONS`). A name that looks secret (contains KEY, TOKEN, SECRET, PASSWORD,
   CREDENTIAL, SESSIONID or SESSID anywhere, or has PASS, PASSWD, PASSPHRASE, AUTH, COOKIE, COOKIES, SESSION or PRIVATE as an underscore-delimited name part)
   needs its own neutral Yes and No in `fnl-setup` that names the variable and the receiving agent family.
   `--claude-config-dir` is Claude-only: absolute, no `..`, a current-user-owned directory, no symlink
   components, not group/world-writable and outside git work trees (including ancestor markers); ancestors
   must be root- or user-owned and not group/world-writable, as in the quota probe.
   The wrapper exits 125 on refusal (including argument errors); child exits 0–255 pass through except
   125, which maps to 1 so it cannot look like refusal. Signal termination also maps to 1.
   Enforcer: the script; the host config only holds names.
   **Residual risk (stated, not solved):** `HOME` stays, so credential files the child can read under it
   (`~/.npmrc`, `~/.aws`, `~/.netrc`, the GitHub CLI hosts file, other agents' config folders, the plugin's data root,
   keychain-backed helpers) remain reachable. A private `HOME` for a family (a per-run folder holding only
   what that agent's login store needs) is a proposed option, not implemented or offered by current setup; the owner
   decision below remains open. A sandbox that hides the paths is the stronger option where the host has one.
   The report to the user says the current protection is environment-only.
3. **Delegates and test commands start through one helper.** `run_env.py` (new here; package B's `verify_claim.py`
   currently carries its own scrub of `TYPESAFE_API_KEY` and `GIT_*` and moves to it) builds the allowlisted
   environment for `delegate_env.py` and `verify_claim.py`. A test greps the plugin's scripts and fails when a script
   starts a delegate or a test command without it. Two commands keep their own scoped allowlists under their
   `CLAUDE.md` exceptions: the quota probe and the `ps` snapshot.
4. **A finished run's log is scanned.** `log_scan.py scan <log>...` looks for secret-shaped values in
   both raw text and ANSI-normalized text, unions their spans and reports line numbers from the raw input.
   Thresholds, fixed in `secret_patterns.py`: prefixes `sk-`, `sk-ant-`, `sk_live_`, `sk_test_`, `ghp_`,
   `gho_`, `ghu_`, `ghs_`, `github_pat_`, `glpat-`, `xoxb-`, `xoxp-`, `npm_`, `AKIA`, `ASIA`, `AIza`
   followed by at least 16 token characters (`[A-Za-z0-9+/_=.-]`); private-key blocks from their
   `-----BEGIN` line; `Authorization: Bearer` followed by at least 16 token characters; and values of
   at least 16 characters after a name containing KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, SESSIONID or SESSID, or having
   PASS, PASSWD, PASSPHRASE, AUTH, COOKIE, COOKIES, SESSION or PRIVATE as an underscore-delimited name part (case-insensitive,
   including lowercase `name=value` and quoted values with spaces or punctuation). Environment dumps
   require at least ten distinct environment-style names (uppercase, containing an underscore) in
   `NAME=value` or `'NAME': 'value'` pairs within 200 raw lines; repeating one name does not qualify.
   At 1,000 candidate hits across raw and normalized scans (known prefixes, bearer lines, private-key
   blocks, sensitive names with qualifying values, or pairs in a qualifying environment dump), stop with
   one `match_limit` finding covering the whole input; `show` and `redact` then replace the whole log.
   Harmless pairs do not count toward that cap. A separate limit of 250,000 pairs per scan pass bounds
   pair matching; exceeding it gives `not_scanned`, without a finding or redaction. Matches are iterated;
   only environment-style pairs are retained for the dump window.
   Exemptions to the sensitive-name rule (release 0.2.3, package 7), each shown not to be a credential:
   a value that fully matches an ISO-8601 timestamp (date, `T` or space, time, optional fraction and zone)
   or a decimal number, under any name; the exact lowercase names `coord_session`, `session_id`,
   `credential_expires_at`, `model_auto_compact_token_limit`, `expected_keys` and `key_end`, which hosts and
   this plugin write in their own output, when the value holds no known prefix; a name containing `|`
   with no empty alternative, which is pattern text such as `KEY|TOKEN`, not a field name; and, for the
   exact names `secret` and `key` only, a value of at least three single-space-separated words of letters,
   each with optional trailing punctuation. Other regex metacharacters (`(`, `*`, `$`, `?`, `\`) can be
   part of a real assignment and stay flagged. Values under `password`, `passwd`, `passphrase`, `token`,
   `credential` or `*_api_key` names stay flagged even with spaces, and so do bare `key` values.
   Known prefixes, bearer lines, private-key blocks and environment dumps are unchanged.
   Beyond these exemptions the stance is to prefer false positives; no other ignore list exists. `no_findings` means only that nothing
   matched these rules. This is a best-effort filter, not proof. Binary, compressed, unreadable or oversize
   (over 8 MiB or the 250,000-pair per-pass limit) logs, lone ESC, unrecognized escape forms, C1 controls and Unicode format characters
   (category Cf, including zero-width joiners and BOMs) give `not_scanned` for a log and
   `rule_1_unreadable` for a brief. One leading BOM is stripped for scanning, with raw log offsets and
   line numbers preserved; any later BOM, other Cf character or C1 control remains a refusal.
   CR/LF token wrapping and other split-value
   evasions remain outside these rules. Output contains fixed kinds, file and raw line number, and a
   variable name only if it matches rule 2 and is not itself secret-shaped: known prefixes or all-caps
   hex/base32 names of 20 or more characters are suppressed. No value, length, prefix or entropy is printed.
   `ledger.py finish` records `log_scan: no_findings | findings | not_scanned`, never `clean`.
5. **Redaction is a guarded write.** `log_scan.py redact <log>` previews and, with `--yes --digest`, rewrites only a
   regular file (lstat; no symlink, no hardlink, owner is the current user) inside the run-log folder, using a temp
   file created with `O_EXCL` in the same directory, mode copied from the original and never wider than 0600, then
   fsync and rename; no backup is made (a backup would keep the value). It refuses if mtime is under
   60 seconds and rechecks device, inode, size and mtime_ns (also owner, link count and ctime_ns) immediately
   before rename, refusing any change. The digest binds the previewed bytes. No process-descriptor query
   or new command runs: `/proc` may be inaccessible and `lsof` has no scoped command exception. An idle
   open descriptor alone is not detected; writers must finish before redaction, and a concurrent same-user
   write after the last recheck remains a race. The run-log folder is created
   0700, and an existing folder with a wider mode is refused with one fixed message on stderr that says to
   run `chmod 700` on it and prints no path (`ledger.py finish` repeats it after `ledger: log refused;`);
   the scripts never change the mode of an existing folder. All file checks (regular file, `st_nlink == 1`, owner) run
   on the opened descriptor (`O_NOFOLLOW`, then `fstat`), not on the path, for `redact`, `show` and the log-path
   argument of `ledger.py finish`. The agents' own transcript stores (for example `~/.codex/sessions`, `~/.claude/projects`) hold the same
   copy; `log_scan.py` lists them as places the user may need to clean and never touches them.
6. **Logs are read through the scan.** `log_scan.py show <log>` prints a redacted view and is the sanctioned way to
   read a delegate log; on a `not_scanned` log, or one with a finding whose value `redact` cannot locate (a finding reported by line that the redactor does not replace), it refuses and prints only
   the status. `ledger.py finish` with a new optional log-path argument (the path must be a regular file inside the run-log folder,
   else the command refuses) imports `log_scan.py` and runs the scan before it stores or prints anything about the
   run, records `log_scan` in the ledger line (a local file; the metrics `SCHEMA` is not touched and `PRIVACY.md` lists the
   field) and never copies log text. Reading a raw log first is advisory; the scripts do not read raw logs into any record.
7. **A leak is reported by name, never chased.** When a finding shows a credential reached a log or a model, the
   coordinator tells the user the variable names and what could not be undone, redacts local copies, and does not
   look for the credential's source or read credential stores; rotation is the owner's (advisory, matching the
   user-scope rule that credentials are never hunted).
8. **The lesson is kept.** The incident is stored as a lesson in the user's knowledge base and cited in
   `fnl-session-hygiene` "Remember or recall" as an example (advisory).

## Where the code lives

`fnl-delegate` owns `delegate_env.py`, `run_env.py`, `log_scan.py` and `secret_patterns.py`; `fnl-handoff` carries
`brief_check.py` with its own copy of `secret_patterns.py`, and `run_env.py` is copied into `fnl-verification`. Each copy
is listed in the CI copy groups and in the test that compares them, so each skill folder stays self-contained.

## Changes

- `fnl-handoff`: Constraints line and a short "Secrets and environments" paragraph; the template check by
  `brief_check.py`.
- `fnl-delegate`: dispatch forms in `references/agents.md` go through `delegate_env.py`; the host template gains
  `## Delegate environment`; "Accept" gains the log scan; `ledger.py finish` records `log_scan`.
- `fnl-setup`: `delegation` feature asks, per present agent family, whether any variable must pass through (default
  none), with a neutral Yes and No; names only.
- `fnl-verification`: states that the environment helper (`run_env.py`) is the only way the plugin starts a delegate or a test command; the quota probe and the `ps` snapshot keep their own scoped allowlists.
- `PRIVACY.md`: the log scan and redaction are local; `log_scan` is one of three fixed words.
- `CHANGELOG.md`, README, `fnl-ask` map: current-surface wording.
- No change to `CLAUDE.md`: no network call, no new class of command (the helper starts the same agent commands the
  dispatch already starts).

## Acceptance

- `brief_check.py` refuses a brief lacking the environment rule or containing a secret-shaped value (tests).
- `delegate_env.py`: names outside the pattern, loader/interpreter/proxy controls and duplicates are refused; a
  secret-looking name needs its own approval record; a child started through it sees only the allowlisted names; an extra variable in the
  coordinator's environment is absent (test compares names, never prints the environment); a name from the host
  config passes; an invalid name or a duplicate is refused.
- `log_scan.py`: finds a planted fake key, a private-key block, an ANSI-wrapped key and a dumped synthetic
  environment; a binary and an oversize log are `not_scanned`; output holds no value, length or prefix (test asserts
  the planted values and their parts do not appear, and that an attacker-controlled name that is not name-shaped is
  not printed); `redact` previews, requires `--yes` and the digest, refuses a symlink, a hardlink, a path outside the
  run-log folder and a log written in the last 60 seconds, creates its temp file `O_EXCL` with the original mode
  never wider than 0600, makes no backup and leaves no value in the file.
- `ledger.py finish` records `log_scan` (`no_findings`, `findings` or `not_scanned`) and warns without reproducing content.
- `log_scan.py show` refuses a `not_scanned` log; a run-log folder wider than 0700 is refused; a descriptor-level check
  fails a hardlinked or swapped file (tests).
- Setup consent for pass-through names is a separate neutral Yes and No; none preselected.
- Rule 8 (the lesson) has an acceptance line: `fnl-session-hygiene` cites the incident as a corrected-lesson example
  (a test greps the sentence).
- Every touched skill file respects the size limits of `setup-restructure.md`.

## Open decisions

- The private `HOME` decision remains open and the option is not implemented in 0.2.0; the owner needs evidence of
  what each agent's login store requires before settling the isolation design.

None other. Names of the scripts and the `log_scan` field may change in review.
