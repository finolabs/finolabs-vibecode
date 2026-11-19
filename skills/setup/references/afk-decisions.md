# afk: the excerpt consent

Loaded by [features/afk.md](features/afk.md) only when the user asks to change the excerpt consent. Questions follow [interview.md](interview.md) (advisory, agent judgment).

The table of what must wait for you, the deploy targets and the command and file lists went with `strict` in 0.3.3 (owner decision, 19/11/2026): afk refuses only the credential floor and the guards that are on, and anything else that must stay forbidden while you are away is a host deny rule. Ask nothing about them; a section that still holds those lines is not read (script-enforced).

Ask separately, never combined with another question: "Let excerpts of your past decisions go to the judge or another AI provider when agents decide for you?"
Yes: Save Excerpts leave the machine: yes; at most eight excerpts (decision, date, source), 8 KB in all, screened for secrets and machine paths, go with an away question to Jev or the advisor's provider.
No: Save Excerpts leave the machine: no; nothing leaves, and decisions rest on the project's goal alone.
Undo: Stop the current lease and repeat setup with this answer at no.
Choices: "Yes, let excerpts go with the question" / "No, keep my history on this computer".

This answer stays no until a clear yes; pass `--excerpts-leave-the-machine yes|no`. No other answer sets it, and `afk.py packet-check` lets no excerpt leave without it (script-enforced).
