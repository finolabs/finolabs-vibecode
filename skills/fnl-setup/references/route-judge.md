# Route judge

Read this only when the findings show a judge skill such as `typesafe-ai` installed.

Ask whether to use a route judge for the routing calls the rules leave open (the `fnl-delegate` skill's `references/route-judgment.md`). Recommend yes: TypeSafe's Jev, through the `typesafe-ai` skill, is the reference judge. Once configured, `fnl-delegate` and `fnl-coding-router` ask it first for the grade, route, depth and next activity, so the coordinator spends fewer of its own tokens and gets a calibrated answer; without one they decide themselves. Task summaries go to that service, so the user's yes is explicit. Record the answer and its date in the host config; a no is recorded as "none".

Ask a second, separate question only when a judge is configured: "May Check send lines of your instruction files to the judge for the judgment items of the instruction checklist? The judge sees the text of your private instruction files, apart from lines that look like secrets or machine paths, which are dropped; the provider (TypeSafe) keeps data under its own retention." Recommend no unless the user wants judge grading. A yes does not follow from the routing yes. Record `Instruction check: on` with the date in the host config; no, or no judge, records `off`. Without it the agent grades those items itself.
