# Development notes

Working notes for building KrGenesis Mod, kept so development can continue on another machine.

- design.md: the approved design spec.
- plan.md: the implementation plan (Tasks 0-17).
- contracts.md: shared constraints, file formats and rulings every task follows.
- progress.md: the task ledger. Every task, review round, ruling, owner request and deferred minor fix, in order.
- verification.md: in-game verification results.

## Where things stand

- Tasks 0-17 are done on feat/krgenesis-mod. Owner smoke tests 1 and 2 passed; the owner closed Task 16 without reporting the remaining in-game checks.
- Added after the plan: slider range 0% to 500%, selectable game folder (top bar folder icon, saved in settings.json), cache\app.log for the windowed exe.
- Final whole-branch review fixed: stage 11 camp troop counts (camp insert wrapper), wide hero tables, per-page UI state, re-applying the app speed after F5-F7, Apply off the event loop and one Apply at a time. Ledger triage of the remaining minors is in progress.md (all LEAVE).
- Not yet checked in game: Heroic stage unlock, the stage 11 camp wrapper (logs "error troops: stage 11 camp hook not found" if the hook is absent), FPS at x3, re-clicking the speed button after F5-F7.
- Unexplained: the exe window once stopped responding to clicks. Not reproduced since. cache\app.log now logs "page built" and connect/disconnect lines; read it before restarting the app if it happens again.
- Kept on purpose for now: the docs/mod-studio-design branch and these notes.

## Setting up on another machine

See the main README for the venv setup and building the exe. The app expects to sit in a folder inside the game folder, or the game folder can be chosen in the app. Profiles (profiles\) are not in git; copy profiles\default.json by hand to keep existing edits.
