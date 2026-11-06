# finolabs-vibecode

The finolabs-vibecode plugin is installed.
Your first step on any coding request (a bug fix, feature, refactor, test or review), before reading code or writing a plan, plan mode included: invoke the `fnl-coding-router` skill. It picks the workflow and depth and routes to the other `fnl-` skills.
A delegated run with a complete brief (checkout, task, rules, tests to run) follows the brief instead, and says so in its report.
Invoke `fnl-delegate` before handing work to another agent.
Where the host supports session titles, name this session at the start, when its task or phase changes and after every compaction, as `fnl-session-hygiene` "Titles" says (advisory: no hook renames).
Ask the user's decisions through the host's native question tool (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on Antigravity), the recommended option first, even when another skill's text only says "ask", and use plain text only when there is no such tool, it fails, nobody can answer, or the answer is free text (advisory, agent judgment).
