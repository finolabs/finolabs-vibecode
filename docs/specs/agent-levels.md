# Agent levels

Status: implemented; the writer, strict reader and candidates command are merged (#189, #191); routing by levels is advisory and unverified on a live host.

Owner decisions, 2026-11-09: the declaration belongs to `delegation` setup. When the user adds an agent, setup asks which of five difficulty levels it can take and saves the answer in the host config so delegation routes well later. A Claude Code command the user already has, such as `claudework` or `claudeomni`, is declared the same way, by its command name and levels; nothing else is asked per command. The user confirms once, at setup, that task briefs and repository files may go to the account each listed command is logged into (it can belong to another organization); routing then uses the agent inside its level range without asking again per task. A declared agent is preferred to the default `claude` install for a task in its range while it has quota; otherwise the default install takes the task.

Levels are the grades of `fnl-delegate`: 1 easy, 2 medium, 3 hard, 4 very hard, 5 ultra hard.

## Goal and acceptance

- AC1: `/fnl-setup add delegation` asks, per present agent family and for any extra Claude Code command the user names, "Which task levels can it take?" (free text `L-H`; for a family blank means all five and writes no line, for an extra command blank records `1-5` so the declaration is kept; with nothing to write the step is skipped), previews and, after a clear yes, writes one `## Agent levels` section in the canonical `host.md` with backup, digest and 60-minute expiry like the other setup writers.
- AC2: An entry name is `claude`, `codex`, `antigravity` or a command `claude<suffix>` (lowercase letters and digits, 1 to 24 after `claude`); a range is `L-H` with 1 <= L <= H <= 5; at most 8 entries, no duplicate names.
- AC3: `show` reads the section strictly: absent prints `none`; valid prints JSON; a duplicate section, a duplicate or unknown line or a bad range prints `unreadable` and exits 3.
- AC4: The consent line is `- Consent: yes (<date>)`; `--off` writes `- Consent: no` and no entries. Entries without consent `yes` are unreadable.
- AC5: Routing says how the section is used (advisory, agent judgment): an agent with a line takes only grades inside its range, an agent without a line takes any grade; a review takes the grade of the work reviewed plus one, at most 5; a declared command replaces `claude` in the headless form; a shell function starts through the user's zsh behind `delegate_env.py`, so the allowlist and the approved or declined names of `Delegate environment` still apply (tested with synthetic names), and it exists only where the user's zsh startup file defines it; quota is read under a label only when `add quota` lists that install.
- AC7: `candidates` prints one JSON line of names only: `claude*` programs on absolute `PATH` entries (executable regular files, the bare name `claude` excluded) and the labels of `~/.claude-<label>` folders (real directories, not links); at most 20 of each, no paths, nothing run. Shell functions are never listed; the user names them.
- AC6: The writer runs no command, reads no shell startup file and stores no environment value or credential.

## Contract

```text
## Agent levels

- Consent: yes (2026-11-09)
- claudework: levels 3-5
- claudeomni: levels 1-2
- codex: levels 1-5
```

Whether a declared command exists is checked by the coordinator in the user's shell (`whence -w <name>`), advisory. The writer and reader enforce only the format.

## Tasks

- [x] T1 Writer and reader script with tests.
- [x] T2 Level questions in the `delegation` feature file.
- [x] T3 Routing, dispatch and host template text in `fnl-delegate`.
- [x] T4 Changelog and index; targeted tests and reference check.

## Evidence

`tests/test_levels_setup.py` and the reviews on #189 and #191; no live-host proof.
