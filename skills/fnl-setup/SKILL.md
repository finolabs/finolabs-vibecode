---
name: fnl-setup
description: Set up finos-vibe-code for this machine and repository through a short interview: host config for orchestration, local file placement, the agent-skills block in CLAUDE.md or AGENTS.md, and a pointer to user-scoped instructions.
disable-model-invocation: true
---

# Set up finos-vibe-code

Prepare this machine and repository so the `fnl-` skills work as written. Explore, grill the user to settle each choice, confirm, then write.

## 1. Explore

Report only what you observe:

- **Installed hosts**: `claude plugin list`, `codex plugin list`, `agy plugin list --json`. Note where `finos-vibe-code` is installed and which agent CLIs exist (`codex`, `agy`, `claude`).
- **Host config**: the file at `$ORCHESTRATION_HOST_CONFIG`, else `~/.claude/orchestration/host.md`. Present, missing, or still holding template placeholders.
- **Repository**: the git root; whether it uses Spec Kit (`.specify/` plus installed `speckit-*` skills); which of `CLAUDE.md` and `AGENTS.md` exist and whether one already has an `## Agent skills` section; whether `.orchestration/` is excluded in `.git/info/exclude`.
- **User-scoped instructions**: whether `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` and `~/.gemini/GEMINI.md` exist, and whether they already point coding work at `fnl-coding-workflow`.

A check that cannot run here (a command or path is unavailable) is listed as **unverified** in one line, and the interview goes on.

Done when the findings are listed for the user.

## 2. Grill

Settle sections A–D one at a time, starting with the first section whose findings are verified; a section that depends on an unverified item comes last, with the user asked to supply that fact. Use the `grilling` skill when it is installed; otherwise end each message with exactly one question, recommended answer first, push back on vague answers until the choice is concrete, and read back each section's decisions for a yes before the next.

**A. Host config** (skip when complete). Offer to create it from `skills/fnl-orchestration/references/host-template.md` in this plugin and fill: which agents are available and how this machine invokes them, the parallel limit (5 or fewer), the heavy-job lock path, and the durable folder for briefs and logs. Recommend the defaults the template names; leave unknown commands as questions in the file rather than guesses.

**B. Local files**. Recommend adding `.orchestration/` to `.git/info/exclude` so briefs and logs stay out of git. The shared `.gitignore` changes only if the user asks.

**C. Agent skills block**. Offer a short `## Agent skills` section for the agent context file that already exists (prefer the one the repository uses; never create the second file). Draft:

```markdown
## Agent skills

This repository uses the finos-vibe-code skills. Start coding work with `fnl-coding-workflow`; it routes to the other `fnl-` skills. <Spec Kit line, when present: Spec Kit owns the development workflow.> Type `/fnl-ask` when unsure which skill fits.
```

**D. User-scoped instructions**. When the findings show no user-scoped instructions, or ones that restate coding rules the plugin now covers, recommend that the user type `/fnl-setup-instructions` after this setup. That skill interviews them and writes their working contract for every host; this one only points to it.

## 3. Confirm and write

Show each draft and apply the user's edits. Then write only what was confirmed: the host config (outside the repository), the exclude line, and the agent-skills block (update an existing block in place). Install nothing and change no shared settings.

## 4. Report

List each file written, each item skipped and why, and anything left for the user (for example installing the plugin on another host, using the commands in the plugin's README).
