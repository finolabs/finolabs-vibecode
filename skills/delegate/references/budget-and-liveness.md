## Budget and liveness

Every dispatch carries a **budget**, written into the brief, and three numbers derived from it (below). Implementation budgets follow the grade in the decision matrix; the other kinds:

| Work | Budget |
| --- | --- |
| review | 30 minutes |
| advise | 15–30 minutes |
| committee member | 30–45 minutes |

Take the upper end of a range for runs that build or test. Once `status` shows at least five finished runs for the same agent, model and grade, set the budget to about 1.5 times their median instead.

- The **agent's own timeout** (`--print-timeout`, the agybird `--timeout`, `--max-turns`), a few minutes under the hard cap, so the agent stops and reports before it is killed.
- The **hard cap** that kills the process (the host config gives the command form): the budget plus a third, and at least 10 minutes over it.
- The **check deadline**, half the budget, when you inspect the run.

An open ledger line and its age prove only that nobody has closed it, not that the run is alive: before telling the user a run is running, check the process table and the run's recorded exit status, and use `pgrep -f` only with a quoted pattern taken from the run's own recorded id that cannot match the coordinator's own command line (it can report a false positive). Enforcer: agent judgment, advisory. Judge liveness from artifacts, never from status messages: the process and its elapsed time, growth of the log and output files, new commits or diff in the worktree, new transcript events. Two checks with no new artifact means the run has stalled: stop it, run the handover (below), then retry once with a smaller scope or switch agents, and tell the user. Each brief tells the agent to report failure rather than retry more than once.
