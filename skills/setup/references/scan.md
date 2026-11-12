# Scan agents (`/setup scan`)

Script: preview, atomic section-only writes, no symlinks. Offer neutral Yes and No choices with none preselected or marked recommended; a default, a timeout or an auto-selected option never counts as the yes. `interview.md` governs questions (advisory).

1. Run `python3 -I <this skill folder>/scripts/agent_scan.py --host <claude|codex|antigravity|zcode>` (ask host if unknown). Checks each CLI's PATH/`--version` (no shell, 3s), canonical config/cache; shows root/source, quota times/pools. No network/probe; read refusals even at exit 0. Versions prove no access; quota over eight hours is unverified; user wins.
2. Show coordinator/all rows (absent too). Confirm full model IDs (free text; recorded or `delegate` tier seeds, never availability proof); missing dependency/confirmation stays unverified. Pass repeated quoted `--models '<family>=<models>'` arguments.
3. Ask: "Save this list of AI helpers and models for future tasks?"
Yes: Replace only Agents on this machine in local host.md; nothing sent.
No: Keep saved list; ask later.
Undo: Approve a rescan or restore prior section.
Choices: "Yes, save it" / "No, keep it unchanged".
After clear yes repeat with confirmed IDs, `--yes --digest <printed Digest prefix, at least 8 hex>`. Mismatch writes nothing. Only canonical `## Agents on this machine` changes; preview coordinator changes. Overrides/legacy settings read this inventory.
4. Report changes/limits; suggest present families for reach, confirm separately; never write `Coordinators and reach`. Refresh after CLI changes; stale after 30 days.
