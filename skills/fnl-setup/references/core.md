# Core path

Explore first and report only what you observe in the chosen scope; a check that cannot run here is listed as unverified in one line. Reading a user-scope prerequisite for a project step grants no permission to change it. Scope selection never opts into anything. Enforcers: the scripts named below; everything else is agent judgment (advisory).

## User scope

Facts to look up before asking: installed hosts (`claude plugin list`, `codex plugin list`, `agy plugin list --json`, and which of `codex`, `agy`, `claude` exist), `host.md` under the root from `scripts/data_root.py` (present, missing or holding placeholders), and the knowledge base the user's instructions name.

1. **Data root.** Show the effective root and its source from `scripts/data_root.py`. Ask: "Keep this data root, or move it to a folder you name?" (keeping it is recommended; a move needs an absolute local folder outside every git work tree). For a move run `python3 -I <this skill folder>/scripts/data_location.py preview --to <path>` and show the file list and `Digest:` (it copies only regular `host.md`, `ledger.jsonl` and files under `state/`, `logs/` and `bin/`, and skips `tmp/` and symlinks). Then ask separately: "Copy the existing data to that folder?" Only after a clear yes run `data_location.py apply --to <path> --yes --digest <full 64-hex preview digest>`. The script refuses a prefix, re-checks the digest, refuses a non-empty target, copies into private folders and writes the pointer last and atomically; the old folder stays for the user to remove. An invalid pointer disables opt-ins: report it and resolve it before any consent-bearing write.
2. **Scan.** Follow `references/scan.md`.
3. **Delegation mode and Routing.** Follow `references/mode.md`.
4. **Knowledge base.** When the user's instructions name one, record the settled decisions there (judge and consent date, which agents coordinate, the parallel limit, the host config path) as `fnl-session-hygiene` "Remember or recall" says, through the access those instructions approve. This asks nothing new, so it has no consent row. Write to the one knowledge base they name and report any write that failed.
5. **Read-back.** Read the inert items back as one list (the values kept, the notes to record, the closing list) and get one yes. Nothing that grants something is in it.
6. **Report.** List each file written, each item skipped and why, and what is left. End with **After your first result**: type `/fnl-setup instructions` to set how assistants work with you (on Codex, `$fnl-setup instructions` immediately, before the first task, so it follows the coding router); consider each missing companion in [companions.md](companions.md) whose condition the findings match, with its install commands; offer `/fnl-setup check`. The beginner path adds the skipped features to this list. Then ask the user to describe what they want to build.

## Project scope

Facts to look up: the git root; whether Spec Kit is used (`.specify/` plus installed `speckit-*` skills); which of `CLAUDE.md` and `AGENTS.md` exist and whether one has an `## Agent skills` section; whether `.finolabs/` is excluded in `.git/info/exclude`; and the signals in [work-tracking.md](work-tracking.md).

1. **Local files.** Recommend adding `.finolabs/` to `.git/info/exclude` so briefs and logs stay out of git (a repository with the older `.orchestration/` folder keeps that one excluded too). Ask: "Add `.finolabs/` to `.git/info/exclude`?" The shared `.gitignore` changes only if the user asks.
2. **Agent skills block.** Draft a short `## Agent skills` section for the context file that already exists (prefer the one the repository uses; never create the second file):

```markdown
## Agent skills

This repository uses the finolabs-vibecode skills. When Routing is on, start coding work with `fnl-coding-router`; it routes to the other `fnl-` skills. <Spec Kit line, when present: Spec Kit owns the development workflow.> <Work-record line, when adopted: This repository uses work records through the coding router.> Pull requests merge only after a code review and a security review are posted on them, as `fnl-review-gate` says; reviewers may post those comments. <Optional, single-owner repository only: Pull requests may take the low-risk lane of `fnl-review-gate`.> Type `/fnl-ask` when unsure which skill fits.
```

   Include only the confirmed workflow line, neither when none. Show the diff and ask: "Write this `## Agent skills` block?" Write it only through `scripts/instructions_write.py` with `--block "Agent skills"` (see `instructions/procedure.md` for the preview and apply steps); an existing block is replaced in place. Eligibility for the low-risk lane is enforced by `merge_check.py`; the reviewer also checks the README install instructions.
3. **Workflow detection.** From the look-first findings ask: "Does this repository use Spec Kit, work records or none?" A folder alone is not proof of a working Spec Kit integration; the decision is repository-scoped. A `## Work tracking` block or an open workflow question goes to `/fnl-setup instructions`; this path does not author that block.
4. **Read-back and report.** Read the inert items back, get one yes, then report as in user scope step 6. Work tracking settings and the project label are the `project` feature, which needs metrics consent and project progress on; ask that user-scope step first, never bundled.
