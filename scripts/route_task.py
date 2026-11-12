#!/usr/bin/env python3
"""Print the route for one task from the decision matrix of `delegate`.

Takes the task's kind and grade and prints one line: the tier, effort, budget
and how it runs, plus the agent order to pick from. Grading the task is the one
judgment; this applies the table to it. The script runs no model, reads no
file and makes no network call: which families are present, the user's allowed
models and quota stay with the coordinator, who reads them from the host config
and `quota_probe.py status`, so the line says `model=coordinator`.

Usage:
  route_task.py --kind implement|review|advise|committee --grade easy|medium|hard|very-hard|ultra-hard

Exits 0 with the line, 2 on an invalid argument.
"""

import argparse
import sys

KINDS = ("implement", "review", "advise", "committee")
GRADES = ("easy", "medium", "hard", "very-hard", "ultra-hard")
TIERS = ("fast", "strong", "frontier")

# `delegate` "Decision matrix": grade -> (tier, effort, budget, runs as).
MATRIX = {
    "easy": ("fast", "medium", "20", "headless"),
    "medium": ("strong", "medium", "30-45", "headless"),
    "hard": ("frontier", "medium", "60-90", "headless"),
    "very-hard": ("frontier", "high", "90-per-sub-run", "session"),
    "ultra-hard": ("frontier", "xhigh", "90-per-sub-run", "session"),
}
# "A run that fell short at its level is retried one level up"; only ultra hard names it.
RETRY_EFFORT = {"ultra-hard": "max"}
# `delegate` "Budget and liveness" for the other kinds.
BUDGET = {"review": "30", "advise": "15-30", "committee": "30-45"}
# `delegate` "Route", step 3: the capability order for code.
CODE_ORDER = "claude-code>codex>antigravity"


def route(kind, grade):
    """The fields of the route line, in print order."""
    tier, effort, budget, runs_as = MATRIX[grade]
    fields = {"kind": kind, "grade": grade}
    if kind == "implement":
        fields["tier"] = tier
        if grade == "hard":
            fields["tier-alt"] = "strong-with-clear-acceptance-tests"
    else:
        # Reviews take the tier above the work they review; every review, advice
        # or committee seat runs at least on the strong tier.
        rank = TIERS.index(tier)
        if kind == "review":
            rank += 1
        fields["tier"] = TIERS[min(max(rank, TIERS.index("strong")), len(TIERS) - 1)]
        budget = BUDGET[kind]
        runs_as = "fresh-context"
    fields["effort"] = effort
    if grade in RETRY_EFFORT:
        fields["retry-effort"] = RETRY_EFFORT[grade]
    fields["budget-min"] = budget
    fields["runs-as"] = runs_as
    # Fast-tier work goes to the agent with the most quota left.
    fields["agents"] = "most-quota-left" if fields["tier"] == "fast" else CODE_ORDER
    if kind != "implement":
        fields["agent-rule"] = "not-the-implementer"
    fields["model"] = "coordinator"
    return fields


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--grade", required=True, choices=GRADES)
    args = parser.parse_args(argv)
    print("route " + " ".join(f"{key}={value}" for key, value in route(args.kind, args.grade).items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
