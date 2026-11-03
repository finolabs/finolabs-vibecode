---
name: fnl-setup
description: Set up finolabs-vibecode for this machine and repository through a short interview: host config for delegation, local file placement, the agent-skills block in CLAUDE.md or AGENTS.md, and a pointer to user-scoped instructions. Run only when the user asks for it.
disable-model-invocation: true
---

# Set up finolabs-vibecode

Prepare this machine and repository so the `fnl-` skills work as written. Explore, grill the user to settle each choice, confirm, then write.

Let the user choose the mode first: **detailed** interviews each section, **quick** asks every decision once with its recommended default and writes after one confirmation, except that consent to send data to a service (the route judge) is always asked on its own and never bundled. In quick mode, leave unsettled any item the findings cannot fill and name it in the report; the skill that later needs it, given the repository's context, asks the user once. Run setup again only when an agent on the machine is added or changed, or a new plugin version adds a field to the host template; it updates in place.

## 1. Explore

Report only what you observe:

- **Installed hosts**: `claude plugin list`, `codex plugin list`, `agy plugin list --json`. Note where `finolabs-vibecode` is installed and which agent CLIs exist (`codex`, `agy`, `claude`).
- **Route judge**: whether a semantic evaluator skill such as `typesafe-ai` is installed (skill listing only; never look for its credentials).
- **Review tools**: which review instruments each installed host has, from the skill listing and `--help` only: Claude Code `/code-review` and `/security-review`, Codex `codex review`, and the `security-audit` skill from Cloudflare. Antigravity has none.
- **Companion skills**: which skills in [references/companions.md](references/companions.md) are installed, from the skill and plugin listings.
- **Host config**: the file at `$ORCHESTRATION_HOST_CONFIG`, else `~/.finolabs/vibecode/host.md` (or the older `${XDG_CONFIG_HOME:-~/.config}/finolabs-vibecode/host.md` while only that file exists). Present, missing, or still holding template placeholders.
- **Repository**: the git root; whether it uses Spec Kit (`.specify/` plus installed `speckit-*` skills); which of `CLAUDE.md` and `AGENTS.md` exist and whether one already has an `## Agent skills` section; whether `.orchestration/` is excluded in `.git/info/exclude`.
- **Knowledge base**: where the user keeps durable decisions that agents write to: a notes vault or knowledge-base server their user-scoped instructions name, with the access those instructions approve.
- **Usage metrics**: whether the plugin's hooks are installed (the whole plugin, on Claude Code, Codex or Antigravity; a single skill installed alone has none) and whether `consent.json` already exists in the state folder (`${FNL_STATE_DIR:-~/.finolabs/vibecode/state}`; a machine that still has `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` and no new folder keeps using the old one). Read only its date and retention.
- **User-scoped instructions**: whether `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` (or `$CODEX_HOME/AGENTS.md`) and `~/.gemini/GEMINI.md` (or `~/.gemini/AGENTS.md`) exist, and whether they already point coding work at `fnl-coding-router`.

A check that cannot run here (a command or path is unavailable) is listed as **unverified** in one line, and the interview goes on.

Done when the findings are listed for the user.

## 2. Grill

Settle sections A–G. Sections whose findings are verified are ready first; a section that depends on an unverified item waits until the user supplies that fact.

Interview by the rules in [references/interview.md](references/interview.md): map the decisions, look up facts yourself, ask every ready decision in one numbered round with a recommended answer, and finish with a read-back and a yes.

**A. Host config** (skip when complete). Skip this section when the `fnl-delegate` skill is not installed. Offer to create the config from that skill's `references/host-template.md` and fill: which agents are available and how this machine invokes them, the allowed models per agent, which agents may coordinate and which delegates each can reach, the parallel limit (5 or fewer), the heavy-job lock path, and the durable folder for briefs and logs. When Antigravity is a delegate, list this repository's test and check commands and ask which to grant it as remembered allow-rules; say that a granted test command runs whatever code the tests contain. Grant only each exact test command, never a wildcard or a general shell, record every granted command in the host config, and keep a grant to this repository: it is not carried to another. After the user names the commands, with `agybird`, the first run that needs one reports `needs_permission` and the user picks "allow and remember" (`--grant-scope remember`); without it, the user adds the literal rules to Antigravity's own settings. The host config only records the answer. When more than one agent coordinates, recommend a host config and ledger path every coordinator's sandbox can read and write.

When the findings show a judge skill such as `typesafe-ai` installed, read [references/route-judge.md](references/route-judge.md) and settle the route judge with it; otherwise record "none" without asking, since routing works without one. Recommend the defaults the template names; leave unknown commands as questions in the file rather than guesses.

**B. Local files**. Recommend adding `.orchestration/` to `.git/info/exclude` so briefs and logs stay out of git. The shared `.gitignore` changes only if the user asks.

**C. Agent skills block**. Offer a short `## Agent skills` section for the agent context file that already exists (prefer the one the repository uses; never create the second file). Draft:

```markdown
## Agent skills

This repository uses the finolabs-vibecode skills. Start coding work with `fnl-coding-router`; it routes to the other `fnl-` skills. <Spec Kit line, when present: Spec Kit owns the development workflow.> Pull requests merge only after a code review and a security review are posted on them, as `fnl-review-gate` says; reviewers may post those comments. <Optional, when the user wants it: Pull requests may take the low-risk lane of `fnl-review-gate`.> Type `/fnl-ask` when unsure which skill fits.
```

Offer the optional lane line only for a repository with one owner, and say that the script, not an agent, decides which pull requests qualify; leave it out where several people write. The lane covers edits to the root documents written for people (README, changelog, contributing, conduct, security, privacy, terms) and version bumps in the three plugin manifests, never agent context files, skills, agents or rules; its script decides which pull requests qualify. A README's install steps are in the lane: the one reviewer reads them as text agents follow, and an outside author still needs the owner's approving review.

**D. User-scoped instructions**. When the findings show no user-scoped instructions, or ones that restate coding rules the plugin now covers, recommend that the user type `/fnl-setup-instructions` after this setup. That skill interviews them and writes their working contract for every host; this one only points to it.

**E. Review tools**. The `fnl-reviewer` and `fnl-security-reviewer` agents run these instruments as their engine, so a review meets the standard only where they are installed. For each one the findings show missing, strongly recommend installing it and give the command: for `security-audit`, `npx skills add https://github.com/cloudflare/security-audit-skill --skill security-audit`; for a host's native review, the host's own update or install path, checked against its docs. Install nothing yourself. Until a tool is installed, the reviewers work by hand and say so in each report.

**F. Usage metrics** (optional; skip when the hooks are not installed). Offer to record usage metadata so the user can see how the practice performs on their own machine. Say, in this order: what is recorded (a time, a session id, a short repository code, a skill or agent name, the router's depth, a review verdict; never prompts, code, command text or file paths), where it lives (the state folder on this machine, readable only by the user), that nothing leaves the machine and the dashboard is a local page, and that it stays off until they say yes and `FNL_METRICS=off` turns it off at any time. Then ask for consent and the retention (30, 90 or 365 days, recommend 90) as one question of its own, never bundled with another. Claude Code records skill and agent use, first edits, commits, review comments and the router's depth; Codex records sessions, first edits, commits, review comments and the router's depth (it reports no skill or agent use), and the user must also trust the plugin's hooks once, with `/hooks`, or they stay off. Antigravity records the same events as Codex, but its hook is not part of the plugin, because a plugin hook's working folder is unverified: with the user's clear yes, after showing what it adds, run `python3 -I <fnl-status folder>/scripts/refresh.py antigravity-hook --yes`. It merges one group, `finolabs-vibecode`, into `~/.gemini/config/hooks.json` with an absolute path to the script, leaves every other group alone and keeps a backup of the file; `--remove` takes it out. The command refuses unless the skill sits inside the `finolabs-vibecode` plugin, so a hook script from some other folder is not written into the user's config by mistake. That file is shared Gemini configuration, so never run it unasked. A declined or skipped section leaves everything off.

**G. Companion skills**. Read [references/companions.md](references/companions.md) and recommend each missing skill whose condition the findings match, with its install commands. Install nothing yourself.

## 3. Confirm and write

Show each draft and apply the user's edits. Then write only what was confirmed: the host config (outside the repository), the exclude line, and the agent-skills block (update an existing block in place). After a yes to section F, run `python3 -I <fnl-status folder>/scripts/refresh.py consent --retention <days>` to record the consent with its date, then `python3 -I <fnl-status folder>/scripts/refresh.py run` once so the dashboard exists; `fnl-status` must be installed beside this skill, and when it is not, say so and skip the section.

When the findings show a knowledge base, also record the settled decisions there as `fnl-knowledge` says (the route judge and the date of consent, which agents coordinate, the parallel limit, the host config path), through the access the user's instructions approve. Write to the one knowledge base those instructions name, and report any write that failed. Install nothing and change no shared settings.

## 4. Report

List each file written, each item skipped and why, and anything left for the user (for example installing the plugin on another host, using the commands in the plugin's README).
