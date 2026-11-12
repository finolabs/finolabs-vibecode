# finolabs-vibecode

The finolabs-vibecode plugin is installed.
Your first step on any coding request (a bug fix, feature, refactor, test or review), before reading code or writing a plan, plan mode included: invoke the `coding-router` skill. It picks the workflow and depth and routes to the plugin's other skills.
A delegated run with a complete brief (checkout, task, rules, tests to run) follows the brief instead, and says so in its report.
Invoke `delegate` before handing work to another agent.
Invoke `checks` before reporting work as done, fixed or passing, and before accepting a delegated run (advisory, agent judgment).
Invoke `session-hygiene` to name this session when its first task starts, when the task or phase changes and after every compaction, where the host supports titles: on the Claude Code desktop app its session-title tool (load it through tool search when it is deferred), in a terminal ask the user to type `/rename <title>` (advisory: no hook renames). A delegated or headless run is named at launch instead.
Ask the user's decisions through the host's native question tool (`AskUserQuestion` on Claude Code, `request_user_input` on Codex, `ask_question` on Antigravity), the recommended option first (a plain yes/no confirmation is neutral, with nothing recommended), even when another skill's text only says "ask", and use plain text only when there is no such tool, it fails, nobody can answer, or the answer is free text (advisory, agent judgment).
