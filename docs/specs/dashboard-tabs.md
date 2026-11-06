# Dashboard tabs

Idea: owner, 2026-11-06. The status dashboard is one long page and is about to gain two panels
(`running-agents.md`, `project-progress.md`). Split it into tabs so each audience finds its part.
Design only; code follows the specs it serves. The page stays one static file with no build step.

## Tabs and where today's panes go

| Tab | Holds | Source |
| --- | --- | --- |
| Overview (default) | activity, router coverage, skill and agent use, depth vs outcome, load cost | existing panes |
| Agents | Running now: command-line agent processes, open delegated runs, app-process summary | `running-agents.md` |
| Project | task progress by feature, phase and story; which agent and which session works on which task | `project-progress.md` |
| Delegation | the delegation pane and the Judge pane | existing panes |
| Reviews | the review gate pane | existing pane |

A tab whose sources are missing shows the existing "missing" message for each pane, not an empty tab.

## Behaviour

- Markup: `role="tablist"`, `role="tab"` buttons with `aria-selected` and `aria-controls`, one
  `role="tabpanel"` per tab; arrow keys, Home and End move between tabs; Enter and Space select.
- The location hash selects a tab (`#agents`, `#project`, ...) by lookup in a fixed own-property table (a
  `Map`) of the five names; an unknown hash falls back to Overview, and the hash is never put into a
  selector, `innerHTML` or an attribute. Panel ids differ from the hash names (`panel-agents` for
  `#agents`), so the browser's fragment scroll cannot target an arbitrary element. The last tab is
  remembered in `localStorage` inside try/catch and checked against the same table when read; with
  storage blocked or throwing, the page renders normally.
- Above the tab strip and shown on every tab: the prompt line, the KPI strip, the theme switch and the
  empty-state veil (when there is no data at all).
- The existing 5-second reload of `data.js` re-renders panes but keeps the selected tab, the scroll position
  of the panel and every open table; a reload never switches tabs.
- Tab labels carry a small count where it means something: Agents shows running processes plus open
  runs; Project shows tasks in progress. No count when its source is missing.
- Narrow width: the tab strip scrolls horizontally inside itself; the page gets no horizontal scroll.
  Colours come from the existing theme tokens in light and dark; no remote font, script or stylesheet; no
  inline event handlers; all dynamic text through `textContent`.
- `fnl-status` SKILL names the tabs and which command rebuilds the data; its step order is unchanged.

## Not in scope

Per-tab refresh intervals; saved layouts; printing; a second page file.

## Acceptance

1. Existing page tests (fake timers) keep passing with every current pane reachable in its tab.
2. New tests: tab switching by click and keyboard; hash selection, unknown hash, hostile hash values
   (`__proto__`, `constructor`, markup, selector characters) and a hostile stored value; storage that throws;
   a `data.js` reload keeps the tab; counts present only with sources; empty and missing-source states;
   narrow-width strip does not widen the page.
3. No new network request, script, stylesheet or inline handler; `check-references.py`,
   `claude plugin validate .` and the page tests pass.
