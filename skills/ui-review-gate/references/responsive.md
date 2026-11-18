# responsive mode

Runs on every UI change. Enforcer: agent judgment, advisory.

## Widths

Check at 320, 390, 768 and 1440 CSS px, resizing the host's browser viewport (or its device emulation) for each, and take a screenshot at each width. 320 px is the WCAG 2.2 reflow check (1.4.10, the same as 1280 px at 400% zoom): content reads without scrolling in two directions.

## What to check

- **No horizontal scroll** at any width: run `scripts/overflow.js` at each width. `horizontalScroll: true` is a finding, and its `culprits` are the elements to fix. Content that needs a two-dimensional layout to be used or understood (data tables, maps, diagrams, toolbars, video) may scroll inside its own region; `scrollRegions` lists them, and the report names each one it accepts as an exception and why.
- **Target size**: run `scripts/targets.js` at 390 and 320 px; classes as `SKILL.md` "Measurements" says.
- **Data tables** become stacked cards below 768 px when the table has more columns than fit; a table kept as a table below 768 px is one of the named scroll-region exceptions.
- **Broken elements**: per width, list every element that overlaps another, is cut off, wraps into an unreadable state or disappears without an equivalent.

Severity: horizontal scroll at 320 px without an accepted exception is `blocking` (1.4.10); at the other widths `high`.

## Constraints

- The 1440 px layout does not change, unless the change is meant to change it. Proof: screenshots at 1440 before and after, compared (`SKILL.md` "Constraints and evidence").

## Output

A screenshot reference for each width, with the list of broken elements at that width, then the mode's findings table.
