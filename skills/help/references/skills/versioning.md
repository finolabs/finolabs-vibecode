# versioning

Typed by the user, or loaded by the agent when the task matches.

**What it does.** Versions and tags releases by SemVer: `0.y.z` until you declare a stable release, one bump per release, immutable annotated `vX.Y.Z` tags, a Keep a Changelog file and release notes.

**When to use it.** Before any version bump, release tag, changelog entry, release notes, pre-release or manifest version change, and when adopting the scheme in a repository that already has versions.

**Type:** Claude Code `/finolabs-vibecode:versioning` or `/versioning`; Codex `$versioning`; Antigravity `/versioning`.

## Tips

- An agent never cuts a release on its own: it proposes one when a spec is merged and you decide.
- In phase 0, compatible changes bump the last digit; MINOR only when something breaks.
- Between releases, builds report the next version with `-dev` (`0.4.0-dev`).
- Published tags are never moved, deleted or reused; a bad release is superseded by a new version.
