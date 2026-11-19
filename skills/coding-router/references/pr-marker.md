# Router marker in a pull request

Detail behind `SKILL.md` "3. Choose the depth". Read it when the work goes into a pull request.

The pull request's body carries the same depth and trigger as the router receipt, as one line with nothing else on it: `<!-- fnl-router depth=<MIN|NORMAL|DEEP> trigger=<trigger> -->`, for example `<!-- fnl-router depth=NORMAL trigger=consumers -->`. Write it when you open the pull request and update it before merge if the depth changed; keep one such line only.

In a repository whose `CLAUDE.md` or `AGENTS.md` at the pull request's base commit has a `## Agent skills` section naming `review-gate`, that skill's merge check blocks a missing, malformed or conflicting line for every pull request, the low-risk lane and bot pull requests included (enforcer: `merge_check.py`).

Where that section also names `ui-review-gate`, the line ends with ` ui=yes` or ` ui=no` before ` -->` (does the change touch user-facing UI?), and `ui=yes` needs a posted UI review (script: `merge_check.py`).

The line states the depth for the reviewers to compare with the diff; it never changes which reviews or lane a change needs.
