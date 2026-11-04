# Privacy

`finolabs-vibecode` is a set of Agent Skills: Markdown instructions plus small local Python scripts. It has no server and sends nothing anywhere, and its maintainers receive nothing from your sessions. If you choose, it records usage metadata on your machine so you can see how the practice performs; that record never leaves the machine, and it is off until you consent.

## Where your data goes

The skills run inside a host agent such as Claude Code or Codex, which processes your conversation under its provider's policy. When you follow the delegation skills and delegate work to another agent (for example Codex or Antigravity), the brief, the files that agent reads and anything it produces are processed by that agent's provider under that provider's terms. Delegate only work over files you are allowed to share with that provider.

## What the plugin stores on your machine

- `~/.finolabs/vibecode/ledger.jsonl` (or the path in `ORCHESTRATION_LEDGER`; an older ledger in `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` is still used until a new one exists): one line per delegated run with a short task label, the agent, the model, timings and the outcome. It holds no prompts, code, secrets or personal data. Delete the file to clear it.
- Only after you consent in `fnl-setup`, through the plugin's hooks on Claude Code and Codex, and on Antigravity when you add its hook in setup: usage events in `~/.finolabs/vibecode/state/events-YYYY-MM.jsonl` (or under `FNL_STATE_DIR`, or in the older `${XDG_STATE_HOME:-~/.local/state}/finolabs-vibecode` folder where it already exists), one line per event. A line holds a time, a session id, a short code derived from the repository path, and a few fixed fields: the name of an `fnl-` skill or agent that ran, the coding router's depth, a review verdict with a pull request number, the number of tasks a coordinator kept with a fixed reason and who settled it, or whether a session was started by a delegated run. It never holds prompts, code, command text, file paths or review text. The same folder holds `consent.json` (the date and how long to keep events), a marker file per session, an error counter with the class name of the latest error (never its text), and the dashboard (`dashboard.html` and `data.js`), which `fnl-status` opens in your browser from your disk. Events older than the retention you chose (30, 90 or 365 days) are deleted at the start of a session, and `fnl-status purge` deletes them all at once. Set `FNL_METRICS=off`, or run `fnl-status` `consent --revoke`, to stop recording at any time. The events are best effort: they are read from tool calls and command text, so they can miss an action or count one that was only written out.
- `.finolabs/` in your repository (older versions used `.orchestration/`), when you follow `fnl-delegate` "Where files go": briefs, logs and handover notes that you or your agents write. The skill tells agents to keep this folder out of git.
- The host config file you create from `skills/fnl-delegate/references/host-template.md`, at a path you choose.

## Reporting issues

Public issues and pull requests are visible to everyone. Remove credentials, personal data and private repository content from any transcript, brief or log before you post it. Report security problems privately as described in [SECURITY.md](SECURITY.md).
