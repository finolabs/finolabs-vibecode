# Agent levels (part of `add delegation`)

Writes the canonical `## Agent levels` section: which of five task levels each helper takes (1 easy, 2 medium, 3 hard, 4 very hard, 5 ultra hard, the grades of `fnl-delegate`). Questions follow [interview.md](interview.md): native question tool, neutral Yes and No, none preselected.

For each present agent family, and for each extra Claude Code command the user names (a program or shell function such as `claudework`; ask only for its command name), ask as free text: "Which task levels can <helper> take? 1 easy, 2 medium, 3 hard, 4 very hard, 5 ultra hard; answer like 3-5, or leave blank for all five." A blank answer writes no line for that helper. Never run or inspect the command or read a shell startup file; the coordinator checks that it exists with `whence -w <name>` before the first dispatch (advisory).
Preview with `python3 -I <this skill folder>/scripts/levels_setup.py preview --install <name>:<L-H> ...` (repeat per helper; `--off` removes the entries) and show its lines.
Ask: "Save these task levels, and let task briefs and repository files go to the account each listed command is logged into?"
Yes: Write the shown Agent levels lines in local host.md after a backup. A command that is a shell function starts through your own zsh behind the same environment filter as other helpers, so a setting you declined stays out; your startup file runs and what it exports is yours. One of them can belong to another organization's account. Saving sends nothing; later helper work uses that account.
No: Leave the section unchanged; ask later.
Undo: Preview with `--off` and approve it, or edit the lines.
Choices: "Yes, save these levels" / "No, keep the current levels".
After a clear yes run `levels_setup.py apply --digest <printed Digest prefix, at least 12 hex> --yes`, then `levels_setup.py show`; exit 0 alone proves nothing. Routing uses the levels by agent judgment (advisory); the script enforces the format only.
