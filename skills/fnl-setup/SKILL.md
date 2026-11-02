---
name: fnl-setup
description: Set up finolabs-vibecode for this machine and repository through a short interview: host config for delegation, local file placement, the agent-skills block in CLAUDE.md or AGENTS.md, and a pointer to user-scoped instructions. Run only when the user asks for it.
disable-model-invocation: true
---

# Set up finolabs-vibecode

Prepare this machine and repository so the `fnl-` skills work as written. Explore, grill the user to settle each choice, confirm, then write.

## 1. Explore

Report only what you observe:

- **Installed hosts**: `claude plugin list`, `codex plugin list`, `agy plugin list --json`. Note where `finolabs-vibecode` is installed and which agent CLIs exist (`codex`, `agy`, `claude`).
- **Route judge**: whether a semantic evaluator skill such as `typesafe-ai` is installed (skill listing only; never look for its credentials).
- **Host config**: the file at `$ORCHESTRATION_HOST_CONFIG`, else `${XDG_CONFIG_HOME:-~/.config}/finolabs-vibecode/host.md`. Present, missing, or still holding template placeholders.
- **Repository**: the git root; whether it uses Spec Kit (`.specify/` plus installed `speckit-*` skills); which of `CLAUDE.md` and `AGENTS.md` exist and whether one already has an `## Agent skills` section; whether `.orchestration/` is excluded in `.git/info/exclude`.
- **Memory and knowledge base**: where the user keeps durable decisions that agents write to: the host's memory feature, or a notes vault or knowledge-base server their user-scoped instructions name, with the access those instructions approve.
- **User-scoped instructions**: whether `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` (or `$CODEX_HOME/AGENTS.md`) and `~/.gemini/GEMINI.md` (or `~/.gemini/AGENTS.md`) exist, and whether they already point coding work at `fnl-coding-router`.

A check that cannot run here (a command or path is unavailable) is listed as **unverified** in one line, and the interview goes on.

Done when the findings are listed for the user.

## 2. Grill

Settle sections A–D. Sections whose findings are verified are ready first; a section that depends on an unverified item waits until the user supplies that fact.

Interview by the rules in [references/interview.md](references/interview.md): map the decisions, look up facts yourself, ask every ready decision in one numbered round with a recommended answer, and finish with a read-back and a yes.

**A. Host config** (skip when complete). Skip this section when the `fnl-delegate` skill is not installed. Offer to create the config from that skill's `references/host-template.md` and fill: which agents are available and how this machine invokes them, the allowed models per agent, which agents may coordinate and which delegates each can reach, the parallel limit (5 or fewer), the heavy-job lock path, and the durable folder for briefs and logs. When Antigravity is a delegate, list this repository's test and check commands and ask which to grant it as remembered allow-rules; say that a granted test command runs whatever code the tests contain. After the user names the commands, with `agybird`, the first run that needs one reports `needs_permission` and the user picks "allow and remember" (`--grant-scope remember`); without it, the user adds the literal rules to Antigravity's own settings. The host config only records the answer. When more than one agent coordinates, recommend a host config and ledger path every coordinator's sandbox can read and write.

When the findings show a judge skill such as `typesafe-ai` installed, read [references/route-judge.md](references/route-judge.md) and settle the route judge with it; otherwise record "none" without asking, since routing works without one. Recommend the defaults the template names; leave unknown commands as questions in the file rather than guesses.

**B. Local files**. Recommend adding `.orchestration/` to `.git/info/exclude` so briefs and logs stay out of git. The shared `.gitignore` changes only if the user asks.

**C. Agent skills block**. Offer a short `## Agent skills` section for the agent context file that already exists (prefer the one the repository uses; never create the second file). Draft:

```markdown
## Agent skills

This repository uses the finolabs-vibecode skills. Start coding work with `fnl-coding-router`; it routes to the other `fnl-` skills. <Spec Kit line, when present: Spec Kit owns the development workflow.> Pull requests merge only after a code review and a security review are posted on them, as `fnl-review-gate` says; reviewers may post those comments. <Optional, when the user wants it: Pull requests may take the low-risk lane of `fnl-review-gate`.> Type `/fnl-ask` when unsure which skill fits.
```

Offer the optional lane line for repositories with one maintainer. The lane covers edits to the root documents written for people (README, changelog, contributing, conduct, security, privacy, terms) and version bumps in the three plugin manifests, never agent context files, skills, agents or rules; its script decides which pull requests qualify. A README's install steps are in the lane: the one reviewer reads them as text agents follow, and an outside author still needs the owner's approving review.

**D. User-scoped instructions**. When the findings show no user-scoped instructions, or ones that restate coding rules the plugin now covers, recommend that the user type `/fnl-setup-instructions` after this setup. That skill interviews them and writes their working contract for every host; this one only points to it.

## 3. Confirm and write

Show each draft and apply the user's edits. Then write only what was confirmed: the host config (outside the repository), the exclude line, and the agent-skills block (update an existing block in place).

When the findings show a memory or knowledge base, also record the settled decisions there as `fnl-knowledge` says (the route judge and the date of consent, which agents coordinate, the parallel limit, the host config path), through the access the user's instructions approve. Write to the one knowledge base those instructions name, plus a pointer in native memory when an agent needs it at startup, and report any write that failed. Install nothing and change no shared settings.

## 4. Report

List each file written, each item skipped and why, and anything left for the user (for example installing the plugin on another host, using the commands in the plugin's README).
