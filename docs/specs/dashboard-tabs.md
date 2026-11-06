# Dashboard tabs

Status: implemented; splits the status page into two tabs, Overview and Now.

## Owner decisions (2026-11-06)

The static dashboard has exactly two tabs, `overview` and `now`. This decision replaces the
five-tab layout. Both buttons live in the terminal window title bar immediately after its three
dots; there is no separate tab row. Use small monospace terminal tabs, muted when inactive,
with a 2 px teal underline when active. The dark/light control stays at the right end. At 375 px
the title bar does not wrap: tab padding shrinks and the count badge stays visible.

| Tab | Panes | Bottom tables |
| --- | --- | --- |
| overview (default) | all existing Overview panes, plus a small review gate beside router coverage | existing Overview tables, delegation by agent/model/grade, kept and handed-off counts, Judge receipts and outcome association, full Reviews table |
| now | `running now`, then `projects, last 24 h`, stacked vertically, retaining the existing lanes, slots, quota and project graphics | existing running and project tables |

Delegation and full Reviews are tables only, each in the existing `show the data as tables`
disclosure at the bottom of Overview. The first-pass KPI stays. The review gate shows a large
floored first-pass approve percentage and a thin distribution of PRs with 1, 2 and 3 or more
review rounds (the newest 12 in `D.reviews`; `D.review_stats` retains the whole-period totals).
The reader supplies up to 12 recent PRs. Its rich tooltip shows them as dot chains:
approve teal, rework amber,
without repository names or hashes. Long chains retain the eight-dot cap and remaining count.
The centred path title moves into the prompt line's rich tooltip.

## Behaviour

- Use `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, and one
  `role="tabpanel"` per tab. Arrow keys, Home and End move focus; Enter and Space select.
- Only literal maps resolve fragments and remembered storage: `#agents` and `#project` select
  `now`; `#delegation` and `#reviews` select `overview`; unknown fragments select `overview`.
  Keep `hashchange`. Never write fragment input to the DOM, a selector or an attribute.
  Panel ids differ from fragment names. Storage is guarded by try/catch.
- The prompt, KPI strip and empty-state veil remain shared. `overview` has no badge; `now` has
  open dispatches plus named active projects (existing source counts). Omit the badge only when
  both sources are missing.
- The five-second local `data.js` reload preserves selection, keyboard focus, panel scroll and
  open tables. The compact freshness footer and tables remain last on the selected tab.
- Keep theme tokens, rich tooltips, local resources, safe text builders and reduced-motion rules.

## Acceptance

Tests cover exactly two title-bar tabs with labels and roles; pane order and moved tables; badge
counts; all four old links, unknown/hostile fragments and hostile storage; hashchange, keyboard
navigation, blocked storage, reload state and missing sources; the review figure, distribution and
bounded tooltip dots; no obsolete tab/panel ids; the 375 px no-wrap rule. The coordinator checks
both themes in a real browser. No new data collection, hook declaration or remote resource.
