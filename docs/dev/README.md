# Development notes

Working notes for building KrGenesis Mod, kept so development can continue on another machine.

- design.md: the approved design spec.
- plan.md: the implementation plan (Tasks 0-17).
- contracts.md: shared constraints, file formats and rulings every task follows.
- progress.md: the task ledger. Every task, review round, ruling, owner request and deferred minor fix, in order.
- verification.md: in-game verification results.

## Where things stand

- Tasks 0-15 are done and merged into feat/krgenesis-mod. Owner smoke tests 1 and 2 passed.
- Added after the plan: slider range 0% to 500%, selectable game folder (top bar folder icon, saved in settings.json), cache\app.log for the windowed exe.
- Task 16 (in-game verification with the owner) is in progress. Spec sections 11 and 12 list what to check.
- Task 17 (final review, PR to main, delete the docs/mod-studio-design branch, clean up test leftovers) is after Task 16. The deferred minors to triage are listed in progress.md.
- Open question: the stage 11 camp troop count (see progress.md, parked for Task 16).
- Unexplained: the exe window once stopped responding to clicks. Not reproduced since. If it happens again, read cache\app.log before restarting the app.

## Setting up on another machine

See the main README for the venv setup and building the exe. The app expects to sit in a folder inside the game folder, or the game folder can be chosen in the app. Profiles (profiles\) are not in git; copy profiles\default.json by hand to keep existing edits.
