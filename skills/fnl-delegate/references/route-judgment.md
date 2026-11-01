# Route judgment

An optional judge for the grade and route calls the rules leave open. The rules in `SKILL.md` settle most tasks alone; a judge adds a calibrated answer where two choices stay plausible. Without a judge, the conservative fallback in `SKILL.md` gives the same quality at a higher cost in quota.

## When to ask

Ask only when, after the grade rules, the route table and the strength overrides:

- the grade sits between two levels, or
- two or more routes still fit and the capability order alone would decide.

A task the rules settle never goes to the judge.

## Which judge

The host config names it under "Route judgment" (`/fnl-setup` asks). Use it only through the user's installed skill for that service, for example `typesafe-ai` for TypeSafe's Jev: the skill owns the API, credentials and current docs, and this plugin holds no key. When the host config names none, or the skill or its access is missing, use the fallback and record `--route-by table`.

Sending task data to a judge sends it to that service. The user approves the service in setup; send only the fields below.

## What to send

Batch both questions for one task into one call where the judge supports it.

- **Task**: the brief's goal and acceptance criteria in at most five lines, the touched areas (folders or modules, no file contents), and the risk flags (security, migration, concurrency, contract, permission).
- **Grade question**: which grade fits, from `easy`, `medium`, `hard`, `very-hard`, with each grade's definition from `SKILL.md`, plus `need-evidence` for "the summary does not say enough".
- **Route question**: which candidate fits best, with each candidate's tier line and strengths from `models.md`, quota state, and whether the user is away; plus `none-fits`.

Never send code, secrets, personal data or customer records.

## Reading the answer

- A clear winner (the top answer well ahead of the next): take it and record `--route-by judge`.
- Close answers, `need-evidence` or `none-fits`: use the fallback, and note the judge's answer in the ledger finish note.
- Reuse an answer only for the same task and brief. A rewritten brief or changed quota is a new question.

The judge advises; the coordinator decides and owns the outcome. Its answer never overrides a user's choice, a project rule or the authority limits in `SKILL.md`.
