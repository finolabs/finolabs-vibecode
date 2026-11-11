# A cheaper cloud workflow and what the minutes cost

Hosted CI on a free plan has a monthly minute allowance. Most minutes go to runs nobody needed: every push to every branch, a run a newer push has already superseded, and changes that touch only documents. This page describes a GitHub Actions workflow that avoids those runs, and how to count the minutes a repository spends.

## The workflow

`fnl-setup`'s `checks_setup.py ci preview` writes it from the repository's stored checks (see [checks.md](checks.md)); the setup feature asks its own question first. The workflow:

- runs on `pull_request`, and on `push` only to the default branch (`--branch <name>` when it is not `main`);
- cancels a run superseded by a newer push: `concurrency` with `group: ${{ github.workflow }}-${{ github.ref }}` and `cancel-in-progress: true`;
- skips changes that touch only documents: `paths-ignore` with `**/*.md`, `docs/**` and `LICENSE`;
- caches dependencies only when the stored checks name a known ecosystem and its lockfile is at the repository root: `actions/setup-python` with `cache: pip` and an install step for `requirements.txt`, or `actions/setup-node` with `cache: npm` and `npm ci` for `package-lock.json`; with an unknown ecosystem it sets up and caches nothing;
- runs the whole stored list every week on a `schedule` and by hand through `workflow_dispatch`, so a document-only change cannot hide a break for long;
- reads the repository with `permissions: contents: read` and checks out without keeping the token (`persist-credentials: false`).

Each check becomes one step whose `run:` line is the stored argument array joined with shell quoting (`shlex.join`). The cloud runner runs that line through its shell, unlike `checks.py`, which never uses a shell. A check holding an Actions expression (`${{`) or unprintable text is refused, because Actions would expand it before the shell sees it.

The writer (script-enforced):

- builds the YAML text from a fixed template and never parses an existing workflow;
- writes one file, `.github/workflows/fnl-checks.yml` by default or `--path .github/workflows/<name>.yml` with a name of lowercase letters, digits and dashes, and refuses a link anywhere on the path inside the repository;
- refuses to overwrite an existing file without `--replace-existing`, keeps a backup of it in the plugin's private state folder, and refuses when the file or the stored list changed after the preview, or when a dependency file appeared or disappeared so that the generated workflow would differ. A lockfile's contents are not part of the workflow, so editing one does not void the preview;
- publishes a new file with a hard link that fails if a file appeared since;
- never edits another workflow, never commits and never pushes. The user reviews the file and commits it.

## Limits

- A required status check on a skipped document-only pull request stays pending on GitHub unless the repository's rules allow it. Before relying on `paths-ignore`, make that check not required, or use a ruleset that accepts skipped checks.
- The workflow names actions by major version tag (`actions/checkout@v4`). Pinning action versions to a commit is the user's choice.
- A workflow runs the repository's code in the cloud, including for a pull request from a fork when the repository allows it.
- GitHub runs the weekly schedule on the default branch only, so it does not check other long-lived branches.
- Other hosts get pointers only. GitLab CI has `interruptible: true` with auto-cancel for superseded pipelines, `rules: changes:` to skip document-only changes, `cache:` keyed on a lockfile and scheduled pipelines. Bitbucket Pipelines has `condition: changesets: includePaths:` per step, `caches:` and scheduled pipelines. Write those by hand from the stored list.

## What the minutes cost

`checks.py usage` counts minutes from a run list the agent produced with the host's own command, so the script makes no network call and starts no process. For GitHub:

```text
gh run list --limit 500 --json databaseId,event,headBranch,conclusion,createdAt,updatedAt,startedAt,workflowName > runs.json
python3 -I <this skill folder>/scripts/checks.py usage --from runs.json [--files-from paths.json] [--limit-minutes N]
```

It prints the run count, the total minutes (each run from `startedAt` to `updatedAt`, rounded up to a whole minute; GitHub bills each job that way, so a run with parallel jobs costs more), and the minutes per workflow and per event.

`--files-from` takes a JSON object mapping each run id to its changed paths, built with the host's own command (for a pull request run, `gh pr view <number> --json files`). The output then gives the share of minutes spent on runs whose changed paths are all documents by the same `paths-ignore` rule as the workflow. A run missing from the map is counted as having no paths.

`--limit-minutes N` takes a number of minutes the user gives; the plugin never assumes one. It subtracts every minute in the file and prints the minutes left and the days left at the rate the file shows (spread over at least one day). This is a projection from that sample, not a billing balance: for a month's remaining minutes, export only the current billing period, with `gh run list --created` and a `--limit` high enough that nothing is cut off.

Input is capped at 5 MB and 5,000 runs. Times must be ISO 8601 UTC (`2026-11-01T10:00:00Z`). A run with no workflow name is grouped as `(unnamed workflow)`. Duplicate JSON keys and non-canonical run ids are malformed. Malformed input exits 3 with a one-line reason; an unreadable file exits 2.

Enforcers: `checks_setup.py` for the writer's template, path, preview, digest, backup and no silent overwrite; `checks.py usage` for the caps and the strict input. Offering the workflow and building the run list are agent judgment (advisory).
