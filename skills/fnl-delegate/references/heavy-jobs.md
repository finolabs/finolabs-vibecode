## Heavy jobs

Heavy jobs (container-backed suites, scale measurements, end-to-end runs; the host config lists them) run one at a time per machine through `scripts/heavy_run.py` ([references/dispatch.md](dispatch.md) "Heavy-job lock"); light targeted tests may overlap. Test scope follows the `fnl-verification` skill.
