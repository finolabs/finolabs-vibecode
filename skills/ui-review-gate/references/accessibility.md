# accessibility mode

Runs on every UI change. Standard: WCAG 2.2 level AA from W3C (A and AA success criteria), kept in the list below; enforcer: agent judgment, advisory.

## What to check

- **Contrast** (`scripts/contrast.js`): 4.5:1 for normal text; 3:1 for large text (at least 24 CSS px, or 18.66 CSS px and bold), UI components and focus indicators. A reading marked uncertain is checked by eye.
- **Keyboard pass, by hand, every run**: Tab and Shift+Tab through the touched UI. Every control is reachable and usable by keyboard, in a sensible order, with no trap, and the focus indicator is visible and not hidden behind a sticky header, banner or dialog. Automated checks catch only part of the failures, so the report always says this pass was done by hand, and what it covered.
- **Accessible names**: every icon-only control has a name (`aria-label`, `aria-labelledby` or visually hidden text), and a visible label's words appear in the name (2.5.3).
- **Target size**: per `scripts/targets.js` and the decision in `SKILL.md` "Measurements".
- **Reduced motion**: `prefers-reduced-motion` honoured for animation the change adds. This is 2.3.3, level AAA: report a miss as `low`, never as blocking.

## WCAG 2.2 A and AA criteria

"Auto" names the snippet or axe rule family that measures part of a criterion; every other check is by hand. A criterion the touched UI cannot reach (no media, no timing) is reported as not applicable, with the reason.

| Criterion | Name | Level | How |
| --- | --- | --- | --- |
| 1.1.1 | Non-text Content | A | axe; by hand for meaning of alt text |
| 1.2.1 | Audio-only and Video-only (Prerecorded) | A | by hand |
| 1.2.2 | Captions (Prerecorded) | A | by hand |
| 1.2.3 | Audio Description or Media Alternative (Prerecorded) | A | by hand |
| 1.2.4 | Captions (Live) | AA | by hand |
| 1.2.5 | Audio Description (Prerecorded) | AA | by hand |
| 1.3.1 | Info and Relationships | A | axe; `fields.js` for labels |
| 1.3.2 | Meaningful Sequence | A | by hand |
| 1.3.3 | Sensory Characteristics | A | by hand |
| 1.3.4 | Orientation | AA | by hand |
| 1.3.5 | Identify Input Purpose | AA | `fields.js` (`autocomplete`) |
| 1.4.1 | Use of Color | A | by hand |
| 1.4.2 | Audio Control | A | by hand |
| 1.4.3 | Contrast (Minimum) | AA | `contrast.js` |
| 1.4.4 | Resize Text | AA | by hand, 200% text zoom |
| 1.4.5 | Images of Text | AA | by hand |
| 1.4.10 | Reflow | AA | `overflow.js` at 320 CSS px |
| 1.4.11 | Non-text Contrast | AA | `contrast.js` (components); by hand for focus indicators and icons |
| 1.4.12 | Text Spacing | AA | by hand |
| 1.4.13 | Content on Hover or Focus | AA | by hand |
| 2.1.1 | Keyboard | A | keyboard pass |
| 2.1.2 | No Keyboard Trap | A | keyboard pass |
| 2.1.4 | Character Key Shortcuts | A | by hand |
| 2.2.1 | Timing Adjustable | A | by hand |
| 2.2.2 | Pause, Stop, Hide | A | by hand |
| 2.3.1 | Three Flashes or Below Threshold | A | by hand |
| 2.4.1 | Bypass Blocks | A | axe; by hand |
| 2.4.2 | Page Titled | A | axe |
| 2.4.3 | Focus Order | A | keyboard pass |
| 2.4.4 | Link Purpose (In Context) | A | by hand |
| 2.4.5 | Multiple Ways | AA | by hand |
| 2.4.6 | Headings and Labels | AA | by hand |
| 2.4.7 | Focus Visible | AA | keyboard pass |
| 2.4.11 | Focus Not Obscured (Minimum) | AA | keyboard pass, with sticky and overlay content open |
| 2.5.1 | Pointer Gestures | A | by hand |
| 2.5.2 | Pointer Cancellation | A | by hand |
| 2.5.3 | Label in Name | A | by hand |
| 2.5.4 | Motion Actuation | A | by hand |
| 2.5.7 | Dragging Movements | AA | by hand: every drag has a single-pointer alternative |
| 2.5.8 | Target Size (Minimum) | AA | `targets.js` |
| 3.1.1 | Language of Page | A | axe |
| 3.1.2 | Language of Parts | AA | by hand |
| 3.2.1 | On Focus | A | keyboard pass |
| 3.2.2 | On Input | A | by hand |
| 3.2.3 | Consistent Navigation | AA | by hand |
| 3.2.4 | Consistent Identification | AA | by hand |
| 3.2.6 | Consistent Help | A | by hand |
| 3.3.1 | Error Identification | A | by hand; see `forms.md` |
| 3.3.2 | Labels or Instructions | A | `fields.js` |
| 3.3.3 | Error Suggestion | AA | by hand; see `forms.md` |
| 3.3.4 | Error Prevention (Legal, Financial, Data) | AA | by hand |
| 3.3.7 | Redundant Entry | A | by hand: information entered earlier in the same process is filled in or selectable |
| 3.3.8 | Accessible Authentication (Minimum) | AA | by hand: no cognitive function test without an alternative; paste and password managers work |
| 4.1.2 | Name, Role, Value | A | axe; by hand for custom controls |
| 4.1.3 | Status Messages | AA | by hand |

4.1.1 Parsing is obsolete in WCAG 2.2 and is not checked.

## Output

The mode's table in the report (Issue, Before, After per `SKILL.md` "Report"), each row naming its criterion; then the keyboard pass: what was tabbed through, and what it found.
