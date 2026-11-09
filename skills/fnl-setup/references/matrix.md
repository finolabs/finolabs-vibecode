# Assignment matrix (part of `add delegation`)

Writes the canonical `## Assignment matrix` section: for each helper, which task levels it takes, which types of work suit it, which model to use and which reviews it owns, plus the judge. Questions follow [interview.md](interview.md): native question tool, neutral Yes and No, none preselected. Only the section is written (advisory: the script enforces the format and the write, not the choices).

Run `python3 -I <this skill folder>/scripts/matrix_setup.py candidates` first: names only, runs nothing, shows no path. Offer each name as a candidate; a shell function is never listed, so the user types its name.

Ask once per helper, in one pass, as free text; a blank answer skips that part:
1. Levels: "Which task levels can <helper> take? 1 easy to 5 ultra hard; answer like 3-5, blank for all five."
2. Types of work: "Which types of work suit <helper>? Choose from frontend, design, video, three-d, image-generation, transcription (at most four); blank for none." When several helpers list a type, the earlier one is preferred.
3. Model: "Which full model id should <helper> use for those types? Blank for its default." A model not allowed on this machine is kept and shown as unverified.
4. Roles: "Which reviews does <helper> own? Choose from code-review, security-review, navigator; each role goes to one helper; blank or none for no role."
Then ask the judge: "Who judges evidence: jev (TypeSafe, needs your own key and approval) or host (the small host model)?"

Build one line per helper: `<agent>: levels L-H[; works on <type>, ...][; model <id>][; roles <role>, ...]`, keys in that order, with no leading dash.
Preview: `python3 -I <this skill folder>/scripts/matrix_setup.py preview --judge <jev|host> --consent yes --line "<agent line>" ...` (repeat `--line`; `validate` takes the same options and prints without saving). Show the lines printed and the digest.
Ask: "Save this assignment matrix, and let task briefs and repository files go to the provider of each listed helper and the judge?"
Yes: Write the shown section in local host.md after a backup; the `Consent:` line records today's date. Saving sends nothing; later helper and judge work uses those providers.
No: Leave the file unchanged; ask later.
Undo: Preview a matrix with no agent lines and `--consent no`, or restore the backup.
Choices: "Yes, save the matrix" / "No, keep the current settings".
After a clear yes run `matrix_setup.py apply --digest <printed Digest prefix, at least 12 hex>`, then `matrix_setup.py show`; exit 0 alone proves nothing. The preview expires after 60 minutes and any change to host.md makes it stale.

Moving from the old sections: `matrix_setup.py migrate` previews a matrix built from `## Agent roles` and `## Agent levels` (roles become each helper's `roles`, a helper named only in roles shows `levels 1-5` to edit, levels carry over, the judge carries over). Every line it cannot map is printed as `dropped`; `apply` refuses (exit 3) until the user has read them and you add `--ack-dropped`. Consent is not inherited: ask the question above again, and only after a clear yes add `--consent yes` to `apply`, which then removes both old sections in the same write. The backup keeps the originals. It refuses when the matrix already exists.

The matrix replaces `levels.md`; that legacy path stays until the readers are switched.
