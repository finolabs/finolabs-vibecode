---
name: trigger-none-ui-sql-migration
tags: [trigger, negative]
runs: 3
max_turns: 5
timeout_seconds: 180
allowed_tools: [Skill]
---

Fix the SQL migration that adds the orders.status column: it fails on an existing table because the column is NOT NULL without a default.
