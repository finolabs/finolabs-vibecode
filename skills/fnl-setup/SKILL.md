---
name: fnl-setup
description: Set up finos-vibe-code for this machine and repository: host config for orchestration, local file placement, and the agent-skills block in CLAUDE.md or AGENTS.md.
disable-model-invocation: true
---

# Set up finos-vibe-code

Prepare this machine and repository so the `fnl-` skills work as written. Explore, present what you found, confirm with the user, then write. Ask one section at a time, recommended answer first.

## 1. Explore

Report only what you observe:

- **Installed hosts**: `claude plugin list`, `codex plugin list`, `agy plugin list --json`. Note where `finos-vibe-code` is installed and which agent CLIs exist (`codex`, `agy`, `claude`).
- **Host config**: the file at `$ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. Present, missing, or still holding template placeholders.
- **Repository**: the git root; whether it uses Spec Kit (`.specify/` plus installed `speckit-*` skills); which of `CLAUDE.md` and `AGENTS.md` exist and whether one already has an `## Agent skills` section; whether `.orchestration/` is excluded in `.git/info/exclude`.

Done when the findings are listed for the user.

## 2. Ask

**A. Host config** (skip when complete). Offer to create it from `skills/fnl-orchestration/references/host-template.md` in this plugin and fill: which agents are available and how this machine invokes them, the parallel limit (5 or fewer), the heavy-job lock path, and the durable folder for briefs and logs. Recommend the defaults the template names; leave unknown commands as questions in the file rather than guesses.

**B. Local files**. Recommend adding `.orchestration/` to `.git/info/exclude` so briefs and logs stay out of git. The shared `.gitignore` changes only if the user asks.

**C. Agent skills block**. Offer a short `## Agent skills` section for the agent context file that already exists (prefer the one the repository uses; never create the second file). Draft:

```markdown
## Agent skills

This repository uses the finos-vibe-code skills. Start coding work with `fnl-coding-workflow`; it routes to the other `fnl-` skills. <Spec Kit line, when present: Spec Kit owns the development workflow.> Type `/fnl-ask` when unsure which skill fits.
```

## 3. Confirm and write

Show each draft and apply the user's edits. Then write only what was confirmed: the host config (outside the repository), the exclude line, and the agent-skills block (update an existing block in place). Install nothing and change no shared settings.

## 4. Report

List each file written, each item skipped and why, and anything left for the user (for example installing the plugin on another host, using the commands in the plugin's README).
