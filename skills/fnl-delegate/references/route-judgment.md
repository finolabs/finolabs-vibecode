# Route judgment

When the host config names a judge, the judge makes the grade and route calls, and the coordinator spends no reasoning of its own on them. Without a judge, the coordinator decides with the rules and the conservative fallback in `SKILL.md`, which gives the same quality at a higher cost in quota.

## When to ask

With a judge configured, ask it first, before reasoning the call out yourself:

- the **grade** of every delegated task, unless the user stated it;
- the **route** whenever two or more candidates remain after the deterministic filters.

The filters are checks you apply yourself, and they never go to the judge: the agent or model the user named, project rules, reachability, quota and the strength overrides. A route left with one candidate needs no question.

## Which judge

The host config names it under "Route judgment" (`/fnl-setup` asks). Use it only through the user's installed skill for that service, for example `typesafe-ai` for TypeSafe's Jev: the skill owns the API, credentials and current docs, and this plugin holds no key. When the host config names none, or the skill or its access is missing, decide yourself with the fallback and record `--route-by table`.

Sending task data to a judge sends it to that service. The user approves the service in setup; send only the fields below, and keep the judge skill's own spend guard on.

## What to send

Batch both questions for one task into one call where the judge supports it.

- **Task**: the brief's goal and acceptance criteria in at most five lines, the touched areas (folders or modules, no file contents), and the risk flags (security, migration, concurrency, contract, permission).
- **Grade question**: which grade fits, from `easy`, `medium`, `hard`, `very-hard`, `ultra-hard`, with each grade's definition from `SKILL.md`, plus `need-evidence` for "the summary does not say enough".
- **Route question**: which candidate fits best, with each candidate's tier line and strengths from `models.md`, quota state, and whether the user is away; plus `none-fits`.

Never send code, secrets, personal data or customer records.

## Reading the answer

- A clear winner (the top answer well ahead of the next): take it and record `--route-by judge`.
- Close answers, `need-evidence` or `none-fits`, or a judge that is unavailable: decide yourself with the fallback in `SKILL.md`, record `--route-by table`, and note the judge's answer in the ledger finish note. Never record `judge` without a validated response.
- Reuse an answer only for the same task and brief. A rewritten brief or changed quota is a new question.

The judge advises; the coordinator decides and owns the outcome. Its answer never overrides a user's choice, a project rule or the authority limits in `SKILL.md`.
