## Where files go

Shared files (documentation and design notes with lasting value) go in the project's documentation folders and are committed. Local files (briefs, logs, working notes, captured state) go in `.finolabs/` at the main checkout's root (`briefs/` for briefs and notes, `logs/` for logs and outputs), kept out of git through `.git/info/exclude` (the shared `.gitignore` changes only with the user's approval); never in temporary directories or session scratchpads. A repository that still has the older `.orchestration/` folder and no `.finolabs/` keeps using it; nothing is moved for the user. The full rule: [references/dispatch.md](dispatch.md) "Where files go".


Run hygiene narrows the log location: run the headless form and its `ledger.py finish`, scan, show and redact
from the task checkout, with logs in that checkout's private `.finolabs/logs/`. This overrides the older
main-checkout log placement above; briefs and other notes retain it. Host-config paths do not widen the log guard.
