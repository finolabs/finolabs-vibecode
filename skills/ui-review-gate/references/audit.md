# audit mode

Runs for a new page or a change to design tokens, or when the user asks for a design audit. Enforcer: agent judgment, advisory.

## Steps

1. **Five largest problems.** Report the five largest problems of visual hierarchy and information density in the touched UI (what the eye lands on first, competing emphasis, crowding, empty space that carries no meaning, inconsistent alignment), each with a screenshot reference and the element and file. Done when there are five, or fewer with the reason.
2. **Read the existing system.** From the code, list the spacing scale, type scale and colour set the UI already uses (tokens, Tailwind config, CSS custom properties, repeated literal values), with counts of one-off values.
3. **Propose a system** of at most five primary colours, not counting semantic colours (error, warning, success, info) and the neutral greys, built from what already exists, with the spacing and type scales it keeps or merges. Every text and component pair it proposes meets the contrast thresholds of `accessibility.md`.
4. **Stop for approval.** Ask the user to approve, change or reject the proposed system. Nothing is redesigned before the user approves it.

A redesign that uses only the approved system is a separate step, run only on request; `frontend-design` may help with it when the user has installed it (`SKILL.md` "Companions").

## Defaults

- No gradients: a default that the repository's own design rules or the user can turn off, not a rule. Say which applies.

## Output

The five problems as the mode's findings table, then the existing system, then the proposed system, then the approval question.
