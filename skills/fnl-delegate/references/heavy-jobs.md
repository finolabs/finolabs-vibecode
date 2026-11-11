## Heavy jobs

Heavy jobs (container-backed suites, scale measurements, end-to-end runs; the host config lists them) run one at a time per machine through `scripts/heavy_run.py` ([references/dispatch.md](dispatch.md) "Heavy-job lock"). A light targeted test (one worker, about a minute, well under 512 MB extra, no browser, container, database or large build) skips the lock and the load gate, but still waits while memory pressure is critical: `heavy_run.py status` prints the `pressure:` line on macOS. Advisory (agent judgment). Test scope follows the `fnl-checks` skill.
