# Core path

Unavailable checks stay unverified; reads grant nothing. Enforcers: scripts, otherwise advisory (agent judgment).

## User scope

Find hosts/knowledge base; resolve canonical `host.md` via `scripts/data_root.py`.

1. **Data root.** Show root/source: "Move this plugin’s saved settings and records to another folder?"
Yes: Choose a folder; a separate copy approval precedes any file/pointer change. Nothing is sent.
No: Keep this folder; ask later.
Undo: Use this step to move back.
Choices: "Yes, choose a folder" / "No, keep it here".
Move: absolute/non-git. Preview: `python3 -I <this skill folder>/scripts/data_location.py preview --to <path>`; show files/digest; ask separately: "Copy the saved settings and records to the folder shown?"
Yes: Copy locally, switch the pointer; source kept. Nothing is sent.
No: Keep the files and location; ask later.
Undo: Switch back to the retained source.
Choices: "Yes, copy and switch" / "No, keep it here".
After yes: `data_location.py apply --to <path> --yes --digest <full 64-hex preview digest>`. Script checks digest/target; private copy, no symlinks; pointer last, source kept. Invalid pointer blocks consent writes.
2. **Scan.** `references/scan.md`.
3. **Mode/Routing.** `references/mode.md`.
4. **Knowledge base.** Save judge/date, coordinators/limit/host path through the access those instructions approve; follow `session-hygiene` "Remember or recall". It asks nothing new; no consent row; report any write that failed.
5. **Read-back.** Quick confirms inert defaults once; Advanced asks each inert item. Nothing that grants something is in it. Both scopes ask:
"Save only the notes shown about this setup?"
Yes: Save shown inert notes at listed local targets; saving sends nothing.
No: Keep notes unchanged; answer later.
Undo: Restore prior notes.
Choices: "Yes, save these notes" / "No, keep current notes".
6. **Report.** Writes/skips/pending/reasons. **After your first result**: offer instructions (before Codex coding), missing-companion reminders (questions in `companions`, after core), `/setup check`; ask what to build.

## Project scope

Find git root/context/excludes; [work-tracking.md](work-tracking.md).

1. **Local files.** Ask: "Hide this plugin’s local working files from Git’s untracked-file list?"
Yes: Add .finolabs/ and .orchestration/ to this repository’s local .git/info/exclude; nothing is sent.
No: Keep the list; ask later.
Undo: Remove those entries.
Choices: "Yes, hide these files" / "No, keep the list".
Exclude legacy `.orchestration/`; shared `.gitignore` needs request.
2. **Agent skills block.** Existing context only; offer per file in `AGENTS.md` and `CLAUDE.md` (skip a `CLAUDE.md` that imports it):

```markdown
## Agent skills

This repository uses the finolabs-vibecode skills. Routing on: use `coding-router`. <Spec Kit line, when present: use Spec Kit.> <Work-record line, when adopted: use work records.> Pull requests follow `review-gate` "Pull requests"; reviewers may post code/security reviews. <Single-owner option: Pull requests may take the low-risk lane of `review-gate`.> Help: `/ask`.
```

   Include only the confirmed workflow line, neither when none. `python3 -I <this skill folder>/scripts/instructions_write.py preview --target <file> --content-file <draft> --block "Agent skills"`; show diff/full digest. Ask: "Save these plugin rules for AI sessions in this repository?"
Yes: Save only Agent skills in the shown file with backup; future sessions use their AI provider.
No: Keep the file; ask later.
Undo: Restore the backup.
Choices: "Yes, save the rules" / "No, keep the file".
After yes: `instructions_write.py apply --digest <full digest> --yes`. Read back. Script checks target/digest/expiry; no symlinks; atomic backup/block.
3. **Workflow detection.** Ask: "How does this repository keep its building plan and task progress?"
Description: Choose Spec Kit (plan/task files), work records (goals/evidence), or neither. Undecided keeps notes; choose/correct later. Nothing sent; separate write approval.
Folders prove no integration; instructions owns Work tracking/open questions.
4. **Read-back and report.** Inert facts; report as user step 6. Dashboard settings/label: `project` feature, separate metrics/progress prerequisites.
