#!/usr/bin/env bash
set -e
# Run only in an empty directory, as `claude plugin eval --scaffold` does.
[ -z "$(ls -A .)" ] || { echo "scaffold.sh: run it in an empty directory" >&2; exit 1; }
git init -q .
mkdir -p .specify/memory specs/004-csv-filename .claude/skills/speckit-tasks .claude/skills/speckit-implement src tests
printf '# Constitution\n\nTests first for behavior changes. No other process rules.\n' > .specify/memory/constitution.md
for s in tasks implement; do printf -- '---\nname: speckit-%s\ndescription: Spec Kit %s step.\n---\n\nRun the Spec Kit %s step.\n' $s $s $s > .claude/skills/speckit-$s/SKILL.md; done
cat > specs/004-csv-filename/plan.md <<'MD'
# Plan: CSV export file name

Status: accepted by the owner.

Change: `export_filename()` in `src/export.py` returns `report-<YYYY-MM-DD>.csv` instead of `report.csv`.
Consumers: only `src/routes.py` calls it; no API contract, no data, permissions or dependencies change.
Acceptance: the download is named with the export date; a unit test covers it.
MD
printf 'def export_filename():\n    return "report.csv"\n' > src/export.py
printf 'from src.export import export_filename\n\ndef download():\n    return export_filename()\n' > src/routes.py
git add -A && git -c user.email=demo@example.com -c user.name=Demo commit -qm "Accept plan for 004"
