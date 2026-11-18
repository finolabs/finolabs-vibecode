# ui-review-gate

Typed by the user, or loaded by the agent when the task matches.

**What it does.** Reviews what a change does to the interface, with evidence: four modes (audit, forms, responsive, accessibility on WCAG 2.2 AA), measured by small read-only snippets in the browser the host session already exposes, and every constraint it states ("desktop layout unchanged", "API calls unchanged", "field order unchanged") proved before and after a fix. Report only by default; a direct request to fix fixes at once.

**When to use it.** A change touches components, pages, templates, styles, design tokens or interface copy; or you ask to review the UI, audit the design, check accessibility, check a page is responsive, or optimise a form.

**Type:** Claude Code `/finolabs-vibecode:ui-review-gate` or `/ui-review-gate`; Codex `$ui-review-gate`; Antigravity `/ui-review-gate`.

## Tips

- It runs beside the code and security reviews, never instead of them, and it is advisory: `merge_check.py` does not read it; a blocking finding goes through `review-gate` finding dispositions.
- A target below 24 by 24 CSS px is blocking (WCAG 2.2 AA 2.5.8, with its spacing and inline exceptions); 24 to 43 px is low, since 44 px is Apple's guideline and WCAG AAA.
- axe-core runs only when your repository already declares it and you authorized the command; otherwise it asks whether to add it as a pinned dev dependency, and on a no it says the axe pass was skipped.
- With no browser available to the host session the run reports BLOCKED, never PASS; it never launches a browser of its own.
