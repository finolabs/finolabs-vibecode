# Running a repository's stored checks

`fnl-setup`'s `checks_setup.py` stores each repository's checks in `## Checks` of the canonical host config: an ordered list of short names and JSON argument arrays, never shell strings. A repository cannot change that list. `scripts/checks.py` in this skill runs it.

## Commands

Run from inside the repository:

- `python3 -I <this skill folder>/scripts/checks.py run` runs every check in the stored order and stops at the first failure, printing the failed check's name and exit code. The checks' own output streams through.
- `checks.py run --changed [--base <ref>]` (default base `origin/main`) keeps only the checks the change since the base touches. A `python -m unittest` check is narrowed to the test modules `select_tests.py` names, at most two modules per command, and is skipped when no module names a changed file. Every other check (pytest, npm, make and the rest) runs whole. With no changed file every check is skipped. Each skipped check is printed with its reason. An unknown base refuses.
- `checks.py show` prints the stored list and whether the local-receipt mode is on.

Exits: 0 passed, 1 a check failed, 2 refused (no list, unknown base, outside a repository), 3 the stored section is invalid or unreadable.

## How a check runs

Each check is launched through this skill's copy of `heavy_run.py` in its canonical form, `python3 -I <path>/heavy_run.py run --label "check <name>" -- <argument array>`. That form waits for the machine-wide heavy-job lock, the load and free memory, so checks never run beside another heavy job. No shell is involved, and the environment is the allowlist from `run_env.py`. `checks.py` edits no repository file and makes no network call. The checks themselves run the repository's own code, as cloud CI does (advisory: run them only on code you are willing to run).

## The local receipt

The local receipt is off by default. The user turns it on per repository through `checks_setup.py receipt on`, which asks its own question in `/fnl-setup add checks`. When the mode is on, `checks.py run` writes a receipt only when all of these hold (script-enforced):

- the run covered the whole stored list (never `--changed`) and every check passed;
- the working tree was clean (no changed or untracked file) before and after the run;
- the head was the same before and after;
- the stored list and its mode did not change during the run.

The receipt records the repository code, the head and the digest of the list that ran. It is written atomically to `state/checks-receipts/` in the plugin's private data folder, never to a repository file. In every other case the output says `no local receipt:` and why.

The latest full run decides: `checks.py run` over the whole list removes any earlier receipt for the repository before it launches the first check, so a failed, dirty or moved rerun leaves no receipt. If the earlier receipt cannot be removed, the run is refused and nothing is run. A `--changed` run neither writes nor removes a receipt.

One full run per repository at a time (script-enforced): a whole-list `checks.py run` takes an exclusive, non-blocking lock on `state/checks-receipts/<code>.lock`, a private file beside the receipt, before it removes the old receipt and launches the first check, and holds it until the new receipt is written or declined. A second full run while it is held exits 2 with `refused: another full run of this repository's checks is in progress`. This lock is separate from the heavy-job lock and never taken inside it. `--changed` takes no lock.

`fnl-review-gate`'s `merge_check.py` reads the receipt only when the mode is on and the pull request's hosted checks are missing or not passing. It consults the receipt only when the checkout's `origin` remote names the repository given with `--repo` (a github.com https or ssh URL, compared case-insensitively); otherwise, or when the remote is missing, unparsable or ambiguous, it reports `local receipt: checkout is not <owner/name>` and blocks.
It accepts the receipt only when the repository code, the pull request head and the current list digest all match, and then reports `checks: local receipt (<head>)`. In every other case it blocks as before.
The receipt is self-reported. It proves only that this machine ran the list at that head and gives a reviewer nothing they can check, so the mode is meant for a repository one person works on.

## The pre-push hook

`checks_setup.py hook install` installs a git `pre-push` hook that runs `checks.py run --changed` before every push. Like every setup step, it previews first, then needs a digest and a yes. It is the user's own git hook, not a plugin hook, and `git push --no-verify` skips it. See `fnl-setup`'s checks feature for the preview, the backup, the refusal when `core.hooksPath` is set, and the removal.

Enforcers: `checks.py` for the order, the stop on failure, `--changed` and the receipt conditions; `heavy_run.py` for serialising; `merge_check.py` for matching the receipt; the user's git hook for running before a push. Running `checks.py run` before a push when no hook is installed is agent judgment (advisory).
