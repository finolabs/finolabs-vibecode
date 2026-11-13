# README standard and checklist

The README of a plugin or skill repository is read by two audiences: people deciding whether to install it, and AI agents asked to install it for them. This standard fixes the sections both need, in order, and a checklist that proves the README agrees with what the repository ships. Read it on every release (`versioning` "Cadence") and in any pull request that adds, removes or renames a skill, agent, command or host.

A repository that is not a plugin or skill package (it has no host manifest) needs only the header, What you get and Install; the other sections it has keep their order. It applies the checklist items that fit and skips the skills, agents, commands and host items.

## Facts come from the repository

Never write these from memory or from another repository's README. Read each from its source at the time you write, and recheck it on every release:

| Fact | Source |
| --- | --- |
| Name and display name | the `name` and display-name fields of the plugin manifests |
| Description and one-liner | the manifests' `description`; the catalog entry; the forge's repository description |
| License | `LICENSE` (its first lines) and the manifests' `license` field (SPDX) |
| Hosts | which host manifest folders exist (see the `plugin-packaging` host table) |
| Latest release | the forge's latest release or the newest `vX.Y.Z` tag; a badge reads it live, so prose never states it |
| Install path | the manifests' `name` and `repository`, the catalog's marketplace name, each host's `--help` |
| Counts | `skills/*/SKILL.md` (minus alias folders the repository excludes), `agents/*.md`, `commands/*.md` |
| Workflows behind badges | `.github/workflows/*.yml` |
| Images | the files under the paths the README references |

A number, host or command that the repository cannot back is removed, not rounded.

## Sections, in order

Required sections appear in this order. A conditional section appears when its condition holds, in the position shown. A repository may add its own sections (examples, scope, evidence) between them; the order of the listed ones never changes. Headings may be in the README's own language: map them in the repository-local override ("Repository-local override and house style" below).

| # | Section | Default heading | When | Contents |
| --- | --- | --- | --- | --- |
| 1 | Header | (before the first `##`) | required | Icon if the repository has one (light and dark via `<picture>`, alt text that describes it); the name as the title; one bold tagline (one short promise); one sentence: what it does, for which hosts, and what is enforced versus advisory; a badge row; a banner image only if the repository has one |
| 2 | What you get | `What you get` | required | 3–4 bullets, each one outcome with the skill or command that delivers it in backticks. An evidence line with numbers only if each number is checkable, with its date range |
| 3 | Install at a glance | `Install at a glance` | required | The shortest install per host in code blocks, saying where to type each one (chat or terminal), and a link to `Install` |
| 4 | How it works | `How it works` | the repository ships a diagram or the flow is not obvious from What you get | One paragraph, plus the diagram with light and dark variants |
| 5 | Start here | `Start here` | required | Numbered plain-language steps for a person; "ask your assistant to install it" first, then the first command to type, then how to check it worked |
| 6 | For AI agents | `For AI agents` | required | Ordered steps: find the host, confirm with the user, check for an existing install, install with the host table, verify with a list command, hand over; ending with one "Done when …" line |
| 7 | Skills | `Skills` | `skills/` exists | Table `\| Name \| Use it when \|`, one row per shipped skill |
| 8 | Agents | `Agents` | `agents/` exists | Table, one row per agent definition |
| 9 | Commands | `Commands` | `commands/` exists | Table, one row per command |
| 10 | Supported platforms | `Supported platforms` | required | Operating systems, then a host table |
| 11 | Install | `Install` | required | One subsection per host whose heading names the host, the catalog it installs from, single-skill installs, trust and verification |
| 12 | Privacy | `Privacy` | the plugin runs programs, makes network calls or stores data, or `PRIVACY.md` exists | What leaves the machine, what is stored, how to turn it off; a link to `PRIVACY.md` |
| 13 | Contributing | `Contributing` | required | Links to `CONTRIBUTING.md`, the code of conduct and `SECURITY.md` that exist |
| 14 | License | `License` | required | One line with the license as `LICENSE` states it, linked |
| 15 | Acknowledgements | `Acknowledgements` | the repository builds on or credits others' work | Linked prior art with each one's license |

Headings match at level 2, or level 3 for Skills, Agents and Commands. Write them as ATX headings (`## What you get`); the script does not read underlined (setext) headings.

## Checklist

Run `python3 -I <this skill folder>/scripts/readme_check.py [repository root]`. It checks the items marked **script**, offline, and prints `FAIL <id> …` per finding and the external links for you to open; it is advisory (agent judgment decides what to fix) and exits 1 when anything failed. Then walk the items marked **agent** yourself. Report every item as PASS, FAIL, PENDING (an owner decision) or N/A with its reason.

### Structure

- **S1** (script) Every required section, and every conditional section whose condition holds, is present, in the order of "Sections, in order".
- **S2** (script) The title before the first `##` contains the manifest `name` or display name.
- **S3** (agent) The header has one bold tagline and one sentence naming the hosts and what is enforced versus advisory.
- **S4** (agent) "Start here" and "For AI agents" steps are numbered, "For AI agents" ends with a "Done when" line, and each command in them exists on the host it is given for.

### Badges

- **B1** (script) Every badge in the header has alt text, and each local or `#anchor` target resolves.
- **B2** (script) Release, license and workflow badges name the repository from the manifests' `repository`, and a workflow badge names a file in `.github/workflows/`.
- **B3** (script) One host badge per host manifest, and no host badge without its manifest.
- **B4** (agent) Each badge image renders on the forge (open the page, or the image URL).

### Counts and tables

- **C1** (script) Every "N skills", "N skill folders", "N agents" and "N commands" in the README and the manifests' descriptions equals the shipped count. A number that counts something else (skills of one kind, or another repository's) is reworded, for example "13 of the skills", or recorded in the release pull request as a false positive.
- **C2** (script) Every shipped skill, agent and command appears as a table row `` | `name` | ``, and every row in the Skills, Agents and Commands tables names one that ships. A first cell may name several, each in its own backticks (`` | `pause`, `gtg` | ``), and may carry the `/plugin:` or `$` prefix the host types.
- **C3** (agent) Each row's "Use it when" agrees with that skill's `description` or that agent's or command's frontmatter.

### Hosts and install

- **H1** (script) Every host with a manifest is named in the header and has an `Install` subsection whose heading names it.
- **H2** (script) Every `plugin install`, `plugin add`, `marketplace add`, `agy plugin install` and `skills add` command in Install at a glance, For AI agents and Install names the manifest `name`, the repository, its own marketplace or the catalog set in the override.
- **H3** (agent) Each install command still matches the host's current `--help`, and the "For AI agents" host table matches the per-host install sections.
- **H4** (agent) Since the last release tag, every added, removed or renamed skill, agent, command or host is reflected in the README tables, counts, badges and install sections: `git diff --name-status <last tag>..HEAD -- skills agents commands '.*-plugin'`.

### Description and license

- **D1** (script) The manifests' descriptions are identical, and the repository's own catalog entry for the plugin carries the same description.
- **D2** (agent) The forge's repository description (`gh repo view --json description`) and the shared catalog's entry, if the plugin is listed in one, name the same hosts as the header and contradict no count, host or feature in the manifests. Changing the forge description or a catalog entry is an outward change: propose it to the owner.
- **L1** (script) `LICENSE`, the manifests' `license` and the README's License line name the same license; an unrecognized `LICENSE` is reported for a check by hand.

### Images and links

- **I1** (script) Every image has non-empty alt text and its local file exists.
- **I2** (script) Every `<picture>` has a dark `<source>` and a light `<img>`, both files exist and are different files.
- **I3** (agent) Screenshots and diagrams show the current product; one that may lag says so in its caption.
- **K1** (script) Every relative link resolves to a file in the repository, and every `#anchor` to a heading or an `id` in the target file.
- **K2** (agent) Every external link the script lists resolves (open it, or `curl -sI`), and points at what its text says.

### Content

- **P1** (script) No placeholder text outside code blocks: `TODO`, `TBD`, `FIXME`, `XXX`, `lorem ipsum`, `coming soon`, `{{…}}`, `<your-…>`.
- **P2** (agent) Every number, date range and comparison claim has a source you can name, and is still true.
- **P3** (agent) Every product, project or person named is public and reachable by its link, or the owner has approved naming it; an unpublished product is a PENDING owner decision, not a silent edit.
- **P4** (agent) Nothing in the README contradicts `PRIVACY.md`, `SECURITY.md` or the changelog's latest released entry.

## Repository-local override and house style

A repository may keep `.github/readme-standard.json`. It adapts the standard to the repository and may add a house style; it never removes a required item. Unknown keys are ignored.

```json
{
  "sections": {"how-it-works": "How a change flows", "what-you-get": "Bạn nhận được gì"},
  "exclude_skills": ["old-*"],
  "badge_color": "1F6FEB",
  "catalog": {"repository": "example-org/plugins", "marketplace": "example"},
  "banner_follow_up": "the skill or person that makes a missing banner"
}
```

- `sections` maps a section id (`what-you-get`, `install-at-a-glance`, `how-it-works`, `start-here`, `for-ai-agents`, `skills`, `agents`, `commands`, `supported-platforms`, `install`, `privacy`, `contributing`, `license`, `acknowledgements`) to a heading regular expression matched against the whole heading text, case-insensitively.
- `exclude_skills` lists folder-name patterns that are aliases or internal and are left out of the counts and tables.
- `badge_color` makes every host badge use that colour (script).
- `catalog` is the shared catalog the README installs from; H2 accepts it, and D2 compares with its entry.
- `banner_follow_up` names who makes the banner when the repository has none: record it as a follow-up and leave the banner out; never ship a placeholder image.

A house style (colours, catalog, wording rules of an organization) belongs in that file or in the organization's own instructions, not in this skill.

## In a release

1. Run the script and walk the agent items above on the release branch.
2. Fix each FAIL in the release pull request. For an item you do not fix, write one line in the pull request body: the item id, why not, and who decides.
3. List PENDING owner decisions in the release proposal; the release waits for them only when the owner says so.
4. Rerun the script on the final commit before the tag.
