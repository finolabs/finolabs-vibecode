# Core path

Explore scope; unavailable checks stay unverified. Reads grant no writes/opt-ins. Enforcers: scripts, otherwise advisory (agent judgment).

## User scope

Find hosts, canonical `host.md` (`scripts/data_root.py`), knowledge base.

1. **Data root.** Show root/source: "Keep this data root, or move it to a folder you name?" Recommend keeping; moves: absolute/non-git. Run `python3 -I <this skill folder>/scripts/data_location.py preview --to <path>`; show files/digest. Ask separately: "Copy the existing data to that folder?" After yes run `data_location.py apply --to <path> --yes --digest <full 64-hex preview digest>`. Script validates digest/target, copies privately without symlinks; pointer last, source kept. Invalid pointer blocks consent writes.
2. **Scan.** Follow `references/scan.md`.
3. **Delegation mode and Routing.** Follow `references/mode.md`.
4. **Knowledge base.** Save judge/date, coordinators/limit/host path through the access those instructions approve; follow `fnl-session-hygiene` "Remember or recall". It asks nothing new; no consent row; report any write that failed.
5. **Read-back.** Confirm inert notes. Nothing that grants something is in it.
6. **Report.** List writes/skips/pending/reasons. **After your first result**: instructions (before coding on Codex), missing [companions.md](companions.md), `/fnl-setup check`; ask what to build.

## Project scope

Find git root, `.specify/`/`speckit-*`, context blocks, excludes, and [work-tracking.md](work-tracking.md).

1. **Local files.** Ask: "Add `.finolabs/` to `.git/info/exclude`?" Exclude legacy `.orchestration/`; shared `.gitignore` needs request.
2. **Agent skills block.** Existing context only:

```markdown
## Agent skills

This repository uses the finolabs-vibecode skills. Routing on: use `fnl-coding-router`. <Spec Kit line, when present: use Spec Kit.> <Work-record line, when adopted: use work records.> Pull requests follow `fnl-review-gate` "Pull requests"; reviewers may post code/security reviews. <Single-owner option: Pull requests may take the low-risk lane of `fnl-review-gate`.> Help: `/fnl-ask`.
```

   Include only the confirmed workflow line, neither when none. Run `python3 -I <this skill folder>/scripts/instructions_write.py preview --target <file> --content-file <draft> --block "Agent skills"`; show diff/full digest. Ask: "Write this `## Agent skills` block?" Only after yes run `instructions_write.py apply --digest <full digest> --yes`. Read back. Script: target/digest, no symlinks, expiry, atomic backup/block. Low-risk: `merge_check.py`; README adoption: reviewer.
3. **Workflow detection.** Ask: "Does this repository use Spec Kit, work records or none?" Folders prove no integration; instructions owns Work tracking/open questions.
4. **Read-back and report.** Confirm inert facts; report as user step 6. Dashboard settings/label: `project` feature, separate metrics/progress prerequisites.
