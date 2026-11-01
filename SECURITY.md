# Security policy

## Supported versions

The plugin is in phase 0 (`0.y.z`). Only the latest release receives fixes.

## Reporting a vulnerability

Report vulnerabilities privately through GitHub's **Report a vulnerability** button on this repository's Security tab. Do not open a public issue.

Include the affected skill or script, the version, the steps or prompt that reproduce the problem, and its impact. You will receive an acknowledgement, and the fix is released with a changelog entry that credits you unless you ask otherwise.

## Scope

In scope: instructions in a skill that could lead an agent to leak secrets or private data, bypass a permission or approval step, or run untrusted code, and defects in the bundled scripts (for example `skills/fnl-delegate/scripts/ledger.py`).
