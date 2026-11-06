# Checked compaction threshold setup

Decision: 2026-11-06. Setup writes the chosen threshold after explicit approval.
Scope: one stdlib-only script, `skills/fnl-setup/scripts/compact_setup.py`;
no network, subprocess, hook invocation, environment writes or other settings.
## Verified host facts

Evidence supplied with the task, verified 2026-11-05 against Claude Code
settings documentation (code.claude.com) and installed binary, Codex configuration
reference and 0.166 binary, and Antigravity changelog and installed binary:
- Claude: `autoCompactWindow`, integer 100000–1000000 tokens, capped by the
  model window, in a config folder's `settings.json`; default account `.claude`.
  `/autocompact`, `--autocompact` and `CLAUDE_CODE_AUTO_COMPACT_WINDOW` override
  it; the variable wins over all. Native 1M models compact late by default.
- Codex: top-level `model_auto_compact_token_limit` in `config.toml`, under
  absolute `CODEX_HOME`, otherwise account `.codex`; writer range 1000–10000000.
- Antigravity: refuse with “no documented setting; /compact only”.
These sources were named in the supplied evidence, not fetched for this change.
Codex default and effect on a running session remain unverified.
## Consent and preview

Agent judgment (advisory): only a user request reaching `fnl-setup` invokes the
writer. Ask neutral Yes/No with no default via the native question tool when
available; after yes, ask a free-text token value and state the host's range.
Explain that a lower threshold compacts earlier; prescribe no value.
Run `preview --host claude|codex --tokens N`, or `--off` for a requested removal.
Claude accepts up to four absolute `--folder` arguments instead of its default.
Config folders must already exist. The script refuses symlink components,
wrong owners, group/world-writable paths and folders inside git work trees.
Preview displays only paths, existence, the selected key's old/new value or
removal, and reserved backup names, never unrelated contents.
Warn by name only when `CLAUDE_CODE_AUTO_COMPACT_WINDOW`,
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` or `DISABLE_AUTO_COMPACT` is set.
Say the new value applies to sessions started afterwards.
Resolve storage through the existing identical `data_root.py`; save only
`<data root>/state/compact/preview.json`, mode 0600, with creation time,
target content hashes, paths, modes, backup names and canonical SHA-256 digest.
Display `Digest:`. Host files are unchanged; missing private state folders may
be created. Ask a separate neutral Yes/No for this exact plan, even in quick mode.

## Apply and enforcement

Only after yes: `apply --digest <full 64-hex digest> --yes`.
The script enforces stored-plan-only application, digest integrity, 60-minute
expiry, safe paths and unchanged content/mode; it preflights every target.
Existing files get mode-preserved `.bak-YYYYMMDD` backups; preview chooses `-N`
when occupied. A collision after preview refuses; preview again, never overwrite.
Write with a same-folder temporary file, fsync and atomic replace. No unrelated
file is written; success removes the preview. I/O failure across several targets
can leave earlier targets applied; report the refusal and inspect before retrying.
Claude requires a JSON object; set/remove only `autoCompactWindow`, preserve
other keys and ordering, use 2-space indent and a trailing newline.
Codex replaces/removes the integer top-level key line, or inserts before the
first table (at end if none), preserving other bytes; validate with `tomllib`,
or report the skipped parse check when unavailable, refusing ambiguous key forms. Missing-key removal says
“No difference.” `--off` removes this override, not auto-compaction itself.
Refusals exit nonzero with one content-free line. The host enforces the threshold;
asking remains advisory. Tests cover previews, writes, backups, removals,
byte/order preservation, environment warnings and refusal boundaries.
