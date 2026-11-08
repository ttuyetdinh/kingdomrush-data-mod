# In-game verification log

## Smoke 1 (after Task 5), 2026-11-01

Setup: mods\ = mod_template (kr_mod.lua, kr_mod\util/stats/unlock), kr_mod_data.lua with towers.archers.price[1] = 7 and unlock_tower_levels = true, kr_mod_live.lua 1/1/1. Launched with mods\launch_modded.bat. Owner played stage 1.

Owner: all good (Archers cost 7, level 2 upgrade available, restart from pause worked, no crash).

Log (mods\kr_mod_log.txt, written 18:24):
- applied 1 changes
- unlock level01 mode 1: removed 0, kept 0 (twice: store.level and store.level.data)
- error module live/enemies/troops missing (expected before Tasks 6-8)

Result: PASS for the balance stack walk and stat patch, the log truncation and restart. Unlock hook ran, but stage 1 has no level locks, so stripping is still unproven in game: verify on a stage with locks (Heroic 14-17/19) in Task 16.

## Smoke 2 (after Task 8), 2026-11-01, stage 2

Setup: full mod_template in mods\, same data file, live switched with mods\smoke\*.bat.
- Speed: PASS. F6/F7/F5 work (log speed x2, x3, x1). Badge shows but overlapped the pause button top right; moved to top centre (follow-up commit 9d8c905), recheck in Task 16.
- Enemies x2: PASS. Owner screenshot shows pairs per group; log "enemies x2". Boss wave not checked (Task 16).
- Troops x2: PASS. Owner confirmed doubled; log "troops x2: 26 barracks".
- No error lines in the log. Unlock still "removed 0" (stage 2 has no level locks).
