# Non-code work with comparable risk

Read this only when the request is not code but a wrong result costs about as much: queries and pipelines on live data, infrastructure or platform configuration, dashboards and reports, and models that predict or forecast. The router's inspection, depth, gates and proof still apply; this file says how they read here.

## Inspect

Add to the receipt: the question the output answers, who acts on it, where the data comes from and how fresh it is, and what a wrong answer costs. A request that is itself ambiguous gets a bounded clarification before any work ([workflows/none.md](workflows/none.md) step 1 describes one).

## Depth

At least NORMAL. DEEP when the output drives a money or stock decision, runs on a live system, cannot be undone, combines calculations whose errors compound, or forecasts.

## By kind

- **Queries and pipelines**: run read-only on a bounded sample first. State the grain and the filters. Reconcile a total against a figure you already trust before relying on the result. A write to live data needs the owner's explicit go.
- **Infrastructure configuration**: change it as reviewable code, read the plan or diff before applying, and name the rollback first. A change to a production environment needs the owner's explicit go.
- **Dashboards and reports**: trace each number to its query and define it once. Compare against the source system. Record a change that alters a figure people already saw.
- **Predictions and forecasts**: name the baseline, test on data the model has not seen, and report the error with its limits and what the model cannot know. A forecast is an estimate, not a fact; label it so in the output.

## Gates

Proof follows `fnl-checks`: a query that ran, a plan that applied or a chart that rendered is not evidence that the result is right. Reviews follow `fnl-review-gate`, and `fnl-security-review-gate` triggers apply wherever personal data, permissions or secrets are involved.
