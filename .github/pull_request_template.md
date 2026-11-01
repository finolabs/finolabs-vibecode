## Summary

<!-- What changes, and why. Link the issue for a change to a rule. -->

## Verification

- [ ] `claude plugin validate .` passes.
- [ ] A changed `description` passes its trigger case in `evals/` (`claude plugin eval . --tag trigger --ablation none`).
- [ ] A change to a rule has a `CHANGELOG.md` entry under `## [Unreleased]`.
- [ ] Both manifests carry the same version.
- [ ] No credentials, transcripts, private names, machine paths or user data are included.
