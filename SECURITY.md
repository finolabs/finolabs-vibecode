# Security policy

## Supported versions

The plugin is in phase 0 (`0.y.z`). Security maintenance covers the following release lines:

| Version | Security support |
| --- | --- |
| 0.2.x | Supported; fixes ship in the latest 0.2.x release. |
| 0.1.x | Not supported; upgrade to 0.2.x. |

Development builds are not supported releases; reproduce against a supported release when possible.

## Reporting a vulnerability

Report vulnerabilities privately through GitHub's **Report a vulnerability** button on this repository's Security tab. Do not open a public issue.

Include the affected skill or script, the version, the steps or prompt that reproduce the problem, and its impact. We aim to acknowledge reports within **5 working days**. We coordinate disclosure with the reporter so users can receive a fix or mitigation before details become public, and agree on a disclosure timeline through the private report. A released fix includes a changelog entry that credits you unless you ask otherwise.

## Scope

In scope: instructions in a skill that could lead an agent to leak secrets or private data, bypass a permission or approval step, or run untrusted code, and defects in the bundled scripts (for example `skills/fnl-delegate/scripts/ledger.py`), including the usage-metrics hooks (`scripts/metrics_hook.py`), the dashboard page and the command that adds a hook to a user's Antigravity configuration (`skills/fnl-status/scripts/refresh.py`).
