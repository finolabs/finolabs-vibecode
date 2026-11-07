# Feature: quota (user scope)

Needs: the agent scan (`scan.md`), asked as its own consent; declining it ends this feature. Optional, off by default. Offer only agents the scan recorded present.

Every question follows [interview.md](../interview.md): native question tool, neutral approvals, explicit yes; fallback only as stated there (advisory, agent judgment).

Ask as a separate consent, with neutral Yes and No, none preselected or recommended: "When the coordinator is about to delegate, and a reading is older than 15 minutes, it runs each agent's own read-only usage command (`agy`, `claude`, `codex`) once; those programs contact their providers with your own accounts, and the plugin sends nothing about you." For Claude add:
"The probe starts each Claude Code install with its usual configuration; the default install runs without `CLAUDE_CONFIG_DIR` and listed extra folders with it set; its hooks, plugins and servers run." A default or timeout is not consent; a No leaves probing off. Asking is advisory (agent judgment).

After interest, run `python3 -I <this skill folder>/scripts/quota_setup.py preview --agents <present commands>` with names from `agy claude codex`. Add each extra Claude folder as `--claude-config 'label:/absolute/folder'`; the default install counts toward four. Show the section with every confirmed executable path, its resolved target, interpreter and config folder, then ask: "Do you confirm these exact executable paths?" The preview saves its plan, creation time and digest privately in `<data root>/state/quota/preview.json` (mode 0600).
Apply only that stored preview with `quota_setup.py apply --digest <full Digest> --yes`; a successful apply removes it. The script refuses previews older than 60 minutes and enforces the digest, current host content, canonical root, owner/mode/ancestor checks and folder validation; it resolves executables only in preview and runs no usage command. Resolution searches the session `PATH`; the confirmed path's basename must equal the agent name, and the preview shows its resolved target (possibly a versioned filename) for the user to confirm.
Both paths are recorded and execution uses the checked target. To withdraw, preview `--off` and confirm its apply the same way.

Enforcers: the on-demand reader enforces the separate opt-in, the 15-minute minimum age and backoff; `FNL_QUOTA_PROBE=off` disables it. Before routing the coordinator runs `quota_probe.py read --family <agy|claude|codex>`; with neither cache nor backoff the first reading starts at once. The command reserves a 30-minute retry before invoking each install and waits for its own commands. Hooks start no reading.
Claude Code alone has a StopFailure hook that records only the family and time of an exact `rate_limit` error when probing is on; this advisory marker is overridden by a newer successful reading and the user's statement wins. Scan and Check show cached readings, not runtime proof.
