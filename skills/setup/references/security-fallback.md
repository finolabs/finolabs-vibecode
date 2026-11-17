# Same-family security fallback

Ask after review posting, with neutral Yes and No and none preselected. First show the exact line the answer writes in `## Reviews` of local host.md (`- Same-family security fallback: yes (YYYY-MM-DD)` or `- Same-family security fallback: no (YYYY-MM-DD)`, today's date). Question: "When every other AI helper that could review is out of quota, may a security review by the same kind of AI that wrote the change count, without asking you on each pull request?"
Yes: Save the yes line. Outside an away lease, `merge_check.py --independent --fallback-family <family>` then counts both same-family reviews only when every other present family is positively out of quota (the same evidence the lease fallback uses), each marker's second line starts with the exact fallback reviewer line, and two models approve each kind when an enforcer script or instruction file changed; the merge itself still waits for your go. Nothing is sent.
No: Save the no line; a same-family security review outside a lease keeps asking you on each pull request.
Undo: Change the line to `no` through setup, or delete it.
Choices: "Yes, count it when others are out" / "No, ask me each time".
The line grants nothing by itself; only `merge_check.py` reads it, strictly (one exact line, a real date not in the future; anything else is `no`). Asking and writing it are advisory (agent judgment).
