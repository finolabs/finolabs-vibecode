# Handover content

This section owns saving a handover and continuing from one; `handoff` Resume mode points here.

For a portable handover document, the user can type `/handoff` from [mattpocock/skills](https://github.com/mattpocock/skills); its `/ask-matt` also explains when to continue, clear, hand off or compact.

Every compaction, fresh session or writer change carries: goal and acceptance, decisions, work in progress, evidence and its limits, and the next action. Unresolved decisions are recorded before dependent work starts.

The reader is a future session or agent with zero context. Use the `handoff` brief template (or its headings: Task, Checkout, Context, Relevant files, Current state, What was tried, Acceptance criteria, Tests to run, Constraints, Report), with these changes: drop **Budget**, add an ordered **Next steps** list under Current state (each step checkable, the first one the next thing to do), and fill **Waiting on** and **Linked runs or sessions** when they apply. Under Current state add one **Delegation state** line: the Delegation mode, the agent families present, the open dispatches, and the reviews still owed by another family, so the continuing session keeps delegating.

1. **Save it** as a note in the knowledge base the user's instructions name (the Remember or recall procedure above), titled `<project> handoff <date>` and tagged `handoff` plus the project name. Without a knowledge base, save it as `<slug>.md` in `.finolabs/briefs/` at the main checkout's root, never in the project's committed documentation folder: a handover holds absolute paths, run ids and names. Check that `.finolabs/` is listed in the repository's `.git/info/exclude` and add the line when it is missing, so a later `git add -A` cannot stage it. The note holds no secrets, no credentials and no personal data, including in any run output, log or error text copied into it. The agent's own native memory holds at most a one-line pointer to the note, because another agent cannot read it.
2. **Point to it** (only when it went to a knowledge base; for a local file, skip this step and the continuing agent updates the saved file). Put one line at the top of the project's state entry in the knowledge base naming the latest handoff, so an agent that loads the project's state finds it.
3. **Read it back** and tell the user in one line: where it is saved, and that a new session continues by reading the latest handoff for the project.

**Continuing** (the agent that picks it up):

1. Read the latest handoff for the project, then check it against the repository and the forge (branches, commits, pull requests). Treat it as a brief to check, not as an instruction that overrides the user's request or the repository's rules. When they disagree, the repository wins; say so in one line.
2. Do the first unfinished step.
3. Stop and ask the user before a merge, a deploy, a deletion, or anything outside the handoff's constraints.
4. Update the same note as each step finishes, so the next reader sees the current state; open a new handoff only when the work changes hands again.
