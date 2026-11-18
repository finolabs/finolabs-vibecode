# forms mode

Runs when the change touches a form, or when the user asks to optimise one. Enforcer: agent judgment, advisory.

## Evidence

Run `scripts/fields.js` first: the ordered fields with name, type, `inputmode`, `autocomplete`, label and required state. It never reads a field's value. Fill fields only with synthetic inputs.

## What to check

- **Layout**: one column; labels above their fields; required fields marked in the visible label, not by colour alone.
- **Field types**: each field has the right `type`, `inputmode` and `autocomplete` for its purpose (for example `type="email"` with `autocomplete="email"`; a phone field `type="tel"`; a one-time code `autocomplete="one-time-code"` and `inputmode="numeric"`). A missing `autocomplete` on a field that collects the user's own data is 1.3.5.
- **Labels**: every field has a label; `labelSource` of `placeholder-only`, `title-only` or `none` is a finding (3.3.2).
- **Validation timing**: validate on blur and on submit; once a field shows an error, re-check it as the user types, so the error clears as soon as it is fixed.
- **Error messages** say how to fix the problem (3.3.3), are tied to their field (`aria-describedby`, `aria-invalid`), and on a failed submit focus moves to the first field in error.
- **States**: focus, disabled, loading and error states exist and are visible; a loading submit cannot be sent twice.
- **Redundant entry** (3.3.7): information the user already gave in the same process is filled in or selectable.
- **Authentication** (3.3.8): login and verification forms allow paste and password managers.

## Constraints

- Field order does not change. Proof: the `order` list from `fields.js` before and after.
- API calls do not change. Proof: the network comparison in `SKILL.md` "Constraints and evidence".

A fix that needs either to change stops and asks the user first.
