# Work tracking block

The project agent context file gets one short `## Work tracking` block, written only through `instructions_write.py` with `--block "Work tracking"` after that file's explicit yes. Use plain sentences, no machine paths, no organisation names and no text copied from repository files. Omit absent facts. The `Outcome` line is written only after the user's yes and carries the date; leave it out when the user declines.

Example with synthetic, user-confirmed values:

```markdown
## Work tracking

This repository uses work records. Specs live in `docs/specs`.
Tasks are tracked in each work record's Tasks section.
The ledger project name is `sample-project`.
Outcome (2026-11-07): ship the sample importer. Success criteria: imports a file of 10,000 rows; reports invalid rows by line; runs in CI.
```

The block describes repository facts for agents; it is not dashboard configuration, and the setup-owned `## Agent skills` block stays intact.
