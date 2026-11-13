# afk: what waits for you, deploy targets and excerpts

Loaded by [features/afk.md](features/afk.md) before the Merge question. Questions follow [interview.md](interview.md) (advisory, agent judgment).

Show this table of what must wait for you. `stop` waits for a person; `decide` lets the agents choose among allowed options while you are away (`afk` "Decide"). Fixed rows never move and get no question.

| Category (key) | Starts | What could go wrong at `decide` |
| --- | --- | --- |
| Production or a live environment (Production) | stop, fixed | |
| Real users or real customer data (Real users and customer data) | stop, fixed | |
| Deletion that cannot be recovered (Unrecoverable deletion) | stop | data lost for good |
| A message to a person outside the repository (Messages outside the repository) | stop | someone gets a message you did not write |
| Tags and releases (Tags and releases) | stop | a version you did not choose is tagged or released |
| Publishing to your own catalog or package (Publishing) | stop | others install a version you did not approve |
| Shared repository settings, such as CI and defaults (Shared settings) | stop | checks or defaults change for everyone |
| Deleting local or recoverable things (Recoverable deletion) | decide | work you wanted must be restored |
| Comments on the repository's own pull requests and issues (Repository comments) | decide | a comment you would not have posted |

Ask: "Keep the table as shown? Agents decide recoverable deletion and repository comments; everything else waits for you."
Yes: Keep every row as its Starts column says.
No: Pick the rows to change next.
Undo: Repeat setup to change the rows.
Choices: "Yes, keep the table" / "No, change some rows".

On No, ask the seven changeable rows in two multi-select questions, in table order (four rows, then three). Each option's label is the row's key in the user's language; its description is the category text. Ask: "Tick each kind of work the agents may decide while you are away. Unticked kinds wait for you, including Recoverable deletion and Repository comments, which the agents decide now."

A ticked row that started at stop ends at decide only after the confirmation below. Every unticked row, and every row of a question left unanswered or answered unclearly, ends at stop; read a free-text answer back before counting it as ticks.

Then for each row moved from stop to decide: "Let the agents decide this kind of work while you are away?"
Yes: Save that key as decide; first name the row and state its "What could go wrong". A decision is never permission: the action is still checked.
No: Keep it at stop; the agents park that work for you.
Undo: Stop the current lease and repeat setup with the row at stop.
Choices: "Yes, let the agents decide it" / "No, keep it waiting for me".

No move has a default. Pass `--decide <key>` for each row ending at decide, the two rows that start at decide included unless the user changed them; every row not passed, and any missing answer, is saved as stop, and a fixed row is refused (script-enforced). Changing a row back to stop needs no separate question.

Optionally collect `Non-production targets` as free text: the exact deploy commands that reach only a development or test environment, one `--non-production-target '<command>'` each, default none. An entry matches a deploy command only when it equals its words joined by single spaces; a production or live word still parks, and every other deploy waits for you (script-enforced). Agents never add an entry during a lease.

Ask separately, never combined with another question: "Let excerpts of your past decisions go to the judge or another AI provider when agents decide for you?"
Yes: Save Excerpts leave the machine: yes; at most eight excerpts (decision, date, source), 8 KB in all, screened for secrets and machine paths, go with an away question to Jev or the advisor's provider.
No: Save Excerpts leave the machine: no; nothing leaves, and decisions rest on the project's goal alone.
Undo: Stop the current lease and repeat setup with this answer at no.
Choices: "Yes, let excerpts go with the question" / "No, keep my history on this computer".

This answer stays no until a clear yes; pass `--excerpts-leave-the-machine yes|no`. No other answer sets it (script-enforced).
