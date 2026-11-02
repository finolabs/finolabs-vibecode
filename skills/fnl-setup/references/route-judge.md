# Route judge

Read this only when the findings show a judge skill such as `typesafe-ai` installed.

Ask whether to use a route judge for the routing calls the rules leave open (the `fnl-delegate` skill's `references/route-judgment.md`). Recommend yes: TypeSafe's Jev, through the `typesafe-ai` skill, is the reference judge, and it settles close calls with a calibrated answer where the fallback spends extra quota. Task summaries go to that service, so the user's yes is explicit. Record the answer and its date in the host config; a no is recorded as "none".
