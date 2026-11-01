# SDD ledger, plan: .planning/plans/2026-11-01-krgenesis-mod.md

Spec: .planning/specs/2026-11-01-krgenesis-mod-design.md (approved). Global constraints, contracts and rulings for subagents: global.md in this folder.
Branch: feat/krgenesis-mod (pushed, upstream origin/feat/krgenesis-mod). Docs branch docs/mod-studio-design still on GitHub until Task 17.

## Pre-flight scan

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1 self | tests vs impl; paths verified live (heroes.hero_bolin.stats.hp, demon_lord damage_type=2, catapult ultimate hit_damage_type=8) | consistent |
| T1 -> all | -e install vs worktrees | editable install resolves krmod to main checkout; ruling R1 (pytest pythonpath ["."]) |
| T2 self | place() tests are pattern-only; rows tests use real tree (archers price, hero_bolin stats) | consistent; categories test matches exclusion lists |
| T3 self | scale/common_pct cases checked by hand (75x133.3=99.975->100, 1.33x50=0.665->0.67) | consistent, needs Decimal(str(x)) |
| T4 self | test_stale, live validation | consistent |
| T2/T3 | both in krmod/model, distinct files | no conflict |
| T5 -> T6/T7/T8 | harness stubs, KRMOD, K.pollers, module loading | consistent; T6-8 each create only own .lua + test file; fixtures local (R3) |
| T5 self | kr_mod.lua logs "error module X missing" until T6-8 exist | tests don't assert no-errors; smoke 1 expects it |
| T6 self | last_poll must init so NOW=0 does not poll (test_hooks_installed_once) | consistent if last_poll = getTime() at install |
| T7 self | traced all 8 tests through algorithm | consistent |
| T8 self | troop_h binds T; log on first poll | consistent |
| T5/T9 | to_lua in modgen/luafmt.py; T9 adds modgen files | consistent |
| T4/T9 | Profile, LiveSettings, stale_changes | consistent |
| T9 -> T10 | apply_mod, write_live, apply_and_run | consistent |
| T10 -> T11-13 | AppState API | consistent |
| T12/T13 | both wire into ui/main.py (show_card, regions) | ruling R5-seq: run T12 then T13 sequentially |
| T13 self | top bar uses "×2" label (web UI), badge in game uses "x2" | intentional, different surfaces |
| T11/T14 | portrait_for(card.id, cache_dir) | T14 earlier wave; T11 consumes |
| T15 | pyproject edits after T11 | sequential |

## Rulings

- Ruling: parallel waves run as separate git worktrees on task branches, merged into feat/krgenesis-mod, despite the skill's no-parallel default. Why: owner asked for parallel work, and every parallel task owns disjoint files. Cost if wrong: a merge conflict to resolve by hand.
- Ruling: worktrees live at game-folder level (C:\Games\KR6...\wt-tN) so repo_dir.parent is the game folder; KRMOD_GAME_DIR also set. Cost if wrong: game-backed tests skip.
- Ruling: R1-R6 in global.md bind all tasks.
- Ruling: T12 then T13 sequentially. Why: both edit ui/main.py. Cost: some wall time.
- Ruling: smoke checkpoints are plan-mandated owner steps; while waiting on the owner, unrelated tasks (T2, T3, T4, T14) continue. T6-T9 start after smoke 1.

## Tasks

Task 0: complete (5419fed, done by controller)
Task 1: implementer T1Reader DONE_WITH_CONCERNS (3feeb82, base 5419fed); review T1Review dispatched. Concerns accepted: tables counted excluding root (1665), -p no:faulthandler for LuaJIT SEH noise, set_global_bytes added.
Ruling: wave A dispatched from 3feeb82 while T1 review runs. Why: saves a wave of wall time. Cost if wrong: T1 fixes merged into wave A branches afterwards.
Wave A dispatched in worktrees ../wt-t2, wt-t3, wt-t4, wt-t5, wt-t14 (branches task/tN, base 3feeb82): agents T2Grouping, T3Scaling, T4Profiles, T5LoaderCore, T14Portraits.
Task 1: complete (commits 5419fed..3feeb82, review clean: Approved, 7 Minor parked for final review: suite-wide -p no:faulthandler, ReaderError wrapping gaps in reader.py _parse/DLL label, root-alias path parse, run(want_result) b"" on non-string, no KRMOD_GAME_DIR test, no set_global_string/close tests)
Task 3: complete (commits 3feeb82..9a9ec59, review clean, 3 Minor parked: pct_to_track docstring "exact inverse", no clamp tests, no negative-decimal rounding test). Merged into feat.
Carry to T10/T12: round slider pct to 0.1 before scale (else large originals read back as mixed); common_pct may return values outside 50..300: show the true percent label with the knob clamped.
Task 4: review T4Review Needs fixes (head c132d02): 1 Critical (corrupt default.json blocks start/delete), 3 Important (TypeError/Overflow on hand edits, no LÖVE key allowlist, swallowed unlink). Fix round 1 sent to T4Profiles.
Task 4: minor (deferred): save() discards normalized speed keys (carry to T9/T10: lowercase keys before writing kr_mod_data.lua); dead _active reserved-name check; "version": true accepted.
Task 4: fix round 1/5 (4 addressed, 0 open; commits c132d02..95fe838)
Task 4: minor (deferred): LÖVE key allowlist is a subset (f20-f24, printscreen, media keys refused; test claims f20 invalid); corrupt default.json warning every start; create/rename to "Default" blocked while a corrupt default.json exists.
Task 4: complete (commits 3feeb82..95fe838, review clean after 1 round). Merged into feat.
Task 5: implementer DONE_WITH_CONCERNS c152bc0 (run_level avoids Lua tail call so templates_game frame keeps balance local; real game is not a tail call per spike). Review T5Review: Needs fixes, 2 Important (find_balance/base outside pcall; util.lua failure swallowed). Fix round 1 sent to T5LoaderCore (findings file task-5-findings-r1.md).
Task 5: minor (deferred): unlock-once test weak (brief-mandated); stats load error text dropped; unlock loaded with bare dofile not util.load_module; harness maps "" to None (luart run returns b"" for nil; T6-8 assert via tostring); mutable [] default in write_data; find_balance returns first match not last; no test for raising/non-table data file.
Task 5: fix round 1 implemented (365ef1e); re-review T5ReReview dispatched.
Task 2: implementer DONE 3f2b4e2. Review T2Review: Needs fixes, 1 Important (enum rule duplicated in rows.py/categories.py). Fix round 1 sent to T2Grouping.
Task 2: minor (deferred): self_check.unplaced can never fill (assert sc.other == [] instead); rule 1 skips leaf's own last segment (comment); one-cell rows with int keys sort as text (xp_level_steps 10 before 5; 64 rows); rows.py:80 KeyError if an int key is a subtable; test_rows silently skips missing card ids; speed test measures warm cache; "Classic upgrades" grouped "Classic towers" in Skills; "Hero screen bars" label also under heroes/common.
Carry to T10: category_of is path-only, so boolean leaf specials.terrain_2.pillar_tower_holders.friendly_damage gets "All damage"; card_categories/scale_card must skip non-num leaves. Troop titles keep middle segments ("Miners skill a soldier") for uniqueness.
Task 14: implementer DONE eee2e70 (towers 15/15, heroes 12/12, powers 9/9, kr1 11/12, enemies 62/63; frame numbers hand-mapped, bosses inferred). Review T14Review dispatched.
Carry to T11: start build_portrait_cache(paths) once in a background thread at startup.
Task 5: fix round 1/5 (2 addressed, 0 open; commits c152bc0..365ef1e)
Task 5: minor (deferred): fallback_log drops queued base/stats/find_balance errors when util fails; duplicate "error stats" lines; love-missing test doesn't assert the error line.
Task 5: complete (commits 3feeb82..365ef1e, review clean after 1 round). Merged into feat (bd67e52). Suite 89 passed.
Task 2: fix round 1/5 (1 addressed, 0 open; commits 3f2b4e2..46c9db1)
Task 2: complete (commits 3feeb82..46c9db1, review clean after 1 round). Merged into feat (84320e7).
Task 14: review T14Review Needs fixes, 2 Important (narrow except lets Pillow NotImplementedError/DecompressionBomb escape; one bad descriptor kills all families). Fix round 1 sent to T14Portraits.
Task 14: minor (deferred): failed atlas re-decoded per card; docstring claims zip skipped on warm start; docstring size swapped; enemy match threshold >= 50 weak.
Smoke 1 prepared in game mods\: mod_template copied (kr_mod.lua + kr_mod\util/stats/unlock), hand-written kr_mod_data.lua (archers price[1]=7, unlock on), kr_mod_live.lua (1,1,1). Spike kr_mod.lua replaced. launch_modded.bat kept.
Ruling: wave B (T6-T9) dispatched from bd67e52 while the owner runs smoke 1, instead of after it. Why: smoke 1 guards the core stack-walk/unlock in kr_mod.lua and stats.lua, which T6-T9 don't touch; waiting on the owner would idle the build. Cost if wrong: a core fix merged into wave B branches before their merge.
Wave B dispatched: worktrees ../wt-t6..wt-t9 (branches task/t6..t9, base bd67e52): agents T6Live, T7Enemies, T8Troops, T9Writer.
Task 14: fix round 1/5 (2 addressed, 0 open; commits eee2e70..e216e99)
Task 14: minor (deferred): decode-failure test doesn't assert exactly one skip; .tmp left if image.save fails.
Task 14: complete (commits 3feeb82..e216e99, review clean after 1 round). Merged into feat (20b1cdc).
Smoke 1: PASS (owner: Archers 7, level 2 upgrade, restart ok). Log: applied 1 changes; unlock level01 mode 1 removed 0 kept 0 (stage 1 has no level locks: stripping unproven, Task 16 item); module live/enemies/troops missing (expected). Recorded in .planning/verification.md.
Task 8: implementer DONE e1b09ae. Review T8Review Needs fixes: 1 Important (inner pcalls swallow errors in apply_all), 1 Important plan-mandated (stage 11 camp rewrite equal to last applied value not detected: tower_stage_11_camp.insert writes barracks_soldiers[level] = {1,2,2}; at mult 1.5-2.25 level 2 writes 2 == _kr_applied so no rebase). Fix round 1 sent for the first.
Task 8: Ruling: stage 11 camp equal-value rewrite (plan-mandated rule in spec 8.5) is parked as a known limitation and moved into Task 16's stage 11 camp check, where in-game evidence decides between wrapping scripts.tower_stage_11_camp.insert to clear _kr_applied and documenting it. Why: affects one stage's camp at four multipliers, nothing downstream builds on it, and the fix needs the real scripts module reachable from the mod. Cost if wrong: camp barracks keep 2 soldiers instead of 4 at x2 on stage 11.
Task 8: minor (deferred): K._troops_ctx/K._troops_last_mult mirror module-local state (not in session contract); "<n> barracks" counts untouched nil max_soldiers tables; test fixture pcall hides troops.lua load errors.
Task 6: implementer DONE 11e1078. Review T6Review Needs fixes: 3 Important (badge colour 0-1 under LÖVE 0.10 0-255; handled key returns nil so director forwards to ISM; update/draw originals wrapped in pcall swallow game errors) + spec gap (pollers skipped on bad read). Fix round 1 sent to T6Live.
Ruling: live.install re-reads the live file and resets DBG_TIME_MULT at every level start. Why: the live file is the authority at level start, and DBG_TIME_MULT otherwise carries over between levels. Cost if wrong: a key-pressed speed doesn't survive into the next level (owner re-presses).
Task 6: minor (deferred): repeated log/getTime expressions; dot-call fallback in keypressed; no test for colour restore/push order; TDD RED covered 9 of 12 tests.
Engine fact: game ships LÖVE 0.10 (0-255 colours). Any later Lua drawing must use 0-255.
Task 9: implementer DONE 930feb2. Review T9Review Needs fixes: 1 Important (atomic_write text mode turns \n into \r\n; bat gets \r\r\n). Fix round 1 sent to T9Writer.
Task 9: minor (deferred): unreachable hasattr(profile,"rules") branch; stale_changes computed twice; "kr_mod_live.lua" literal repeated; retries means attempts; launch creationflags not asserted; *.tmp check not recursive; parse_log accepts "error:" variants; tmp_game fixture duplicated in two test files.
Carry to T13: with UPDATED_RUNNING, LogWatcher can report a live line written after mark() while the "applied N" line predates the apply (data changes install at next level start). UI must call mark() at Apply and must not present such a summary's applied count as the new apply's result; say "changes apply at the next level start".
Task 8: fix round 1/5 (1 addressed, 0 open; commits e1b09ae..f4ce221)
Task 8: minor (deferred): "error troops:" lines repeat every poll (0.5 s) for a persistently failing barrack, no de-dup; entity_db require failure path untested.
Task 8: complete (commits bd67e52..f4ce221, review clean after 1 round; stage 11 camp limitation parked to Task 16). Merged into feat.
Task 7: implementer DONE f6ab679. Review T7Review Needs fixes: Important (all-n=0 command loses its wait_time; decisions taken before the original's wait), Important plan-mandated (single global enemy_acc phase-locks multi-path rows: a path vanishes at 0.5x).
Task 7: Ruling: per-stream accumulators K.enemy_acc = { [pi|enemy] = acc }, reset in enemies install at each level start; brief tests updated to the per-stream rule; global.md contract updated. Why: spec intent is mult x enemies on every path; a shared accumulator drops whole paths. Cost if wrong: small-sample counts differ from a single accumulator (averages still mult x).
Task 7: minor (deferred): n=0 entries skip wave-notification/mark_seen (new-enemy icon may never show for a once-per-level enemy at 0.5x); carrier check ignores tpl.enemy; no force_next_wave-mid-extras test; RED covered 10 of 13; unused ctx param.
Fix round 1 sent to T7Enemies (task-7-findings-r1.md).
Task 6: fix round 1/5 (4 addressed, 0 open; commits 11e1078..0abd9e5)
Task 6: complete (commits bd67e52..0abd9e5, review clean after 1 round). Merged into feat.
Task 9: fix round 1/5 (1 addressed, 0 open; commits 930feb2..4445d6f)
Task 9: minor (deferred): profiles._atomic_write_json duplicates modgen atomic_write and writes CRLF (harmless).
Task 9: complete (commits bd67e52..4445d6f, review clean after 1 round). Merged into feat.
Ruling: Task 10 starts before smoke 2. Why: AppState is pure Python over merged Tasks 2/3/4/9; smoke 2 checks in-game Lua hooks only. Cost if wrong: none expected.
Task 10: dispatched T10AppState in ../wt-t10 (task/t10, base a177a37).
Task 7: fix round 1/5 (2 addressed, 0 open; commits f6ab679..d55db24)
Task 7: minor (deferred): mult read before the up-front wait (live change applies one row late); dead `or WAITS[1]` branch in test_double.
Task 7: complete (commits bd67e52..d55db24, review clean after 1 round). Merged into feat (3e3abd5). Full suite 202 passed.
Smoke 2 prepared: full mod_template copied into game mods\ (live, enemies, troops added); data file unchanged (archers 7, unlock on).
Task 16 note (stage 11 camp): the camp TOWER template holds tt.barracks_soldiers = b.max_soldiers (templates_game.lua:12093, per-level {1,2,2}), not under .barrack, so troops.lua never scales it; insert writes vanilla values into personal barracks. Pick one fix only: wrap scripts.tower_stage_11_camp.insert to clear _kr_applied on personal barracks, OR scale barracks_soldiers and exclude controller_stage_11_camp_barrack entities from the live walk (else 4 -> rebase -> 8). Harness test: level 1->2 at mult 2 gives 4, not 2 or 8.
Smoke 2 pre-check: real mods\kr_mod_data.lua (archers 7, unlock on) and kr_mod_live.lua dry-run in ModHarness: "applied 1 changes", price 7, no module errors. Helper bats in game mods\smoke\ (1_enemies_x2, 2_troops_x2, 3_reset); delete after smoke 2. Waiting on owner.
Smoke 2 partial (level02): speed keys PASS (log speed x2/x3/x1), badge visible but overlaps the pause button top-right -> follow-up sent to T6Live (move to top centre); enemies x2 PASS (owner screenshot shows pairs, log "enemies x2"); troops pending (owner running 2_troops_x2.bat). Log had no error lines; "troops x1: 25 barracks" at start.
Task 10: implementer DONE 5fac125. Review T10Review Needs fixes: Important (set_level rounds derived pct, misses typed value on originals > 1000), Important (scale/store/validate logic copied 3-4x), spec gap ("1_5" and non-ASCII digits accepted). Fix round 1 sent to T10AppState.
Task 10: minor (deferred): round(pct,1) is half-even (use Decimal half-up); duplicate_profile extra new_name arg; test_rows_caching can't fail; tests mutate session tree; set_level warning ignores stored values. Carry to T12: c2_range must only be called on numeric rows.
Smoke 2: PASS. Troops x2 confirmed by owner; log "troops x2: 26 barracks", no error lines. Controller reset kr_mod_live.lua to 1/1/1. Badge position follow-up 9d8c905 (top centre) under review T6BadgeReview; re-copy mod into mods\ after merge; owner to glance at the badge during Task 16.
Task 6: follow-up round 2 (badge top centre, 1 addressed; commits 0abd9e5..9d8c905). Merged; mods\ refreshed. Owner confirmed reset works.
Task 6: minor (deferred): getFont stub width equals fallback 40 (use 60); brief text still says top right.
Task 10: fix round 1/5 (3 addressed, 0 open; commits 5fac125..ca424ff)
Task 10: minor (deferred): set_value always saves even when nothing changed; double validation in set_level(locked_row=None).
Task 10: complete (commits a177a37..ca424ff, review clean after 1 round). Merged into feat (a2b1022). Suite 229 passed. Merged worktrees removed; feat pushed.
Task 11: dispatched T11UIShell in ../wt-t11 (task/t11, base a2b1022).
Task 11: implementer DONE 7948745. Controller smoke: native window "KrGenesis Mod" opens, portraits, "5857/5857 values placed", Archers opens editor title (browser check via 127.0.0.1:8000; computer clicks into WebView2 land DPI-scaled, AX tree not exposed). Review T11Review Needs fixes: 3 Important (child click listeners fire twice in a real browser; bare Warning chip untested; startup-error test bypasses startup code). Fix round 1 sent to T11UIShell.
Task 11: minor (deferred): ProfileStore OSError at startup / in dialogs not caught; subtitle "Towers · Towers"; tests/ui_main.py mkdtemp never cleaned; UI_TABS duplicates TABS; topbar refreshes twice per action; portrait-or-initials block duplicated; rename/delete lack UI tests; repo-dir logic duplicated in app.py.
Task 11: fix round 1/5 (3 addressed, 0 open; commits 7948745..c625577)
Task 11: minor (deferred): profile marker breaks on names with spaces (mark splits on whitespace); card titles become per-word markers; tests click by display text not id markers; error tests assert file name not full path.
Task 11: complete (commits a2b1022..c625577, review clean after 1 round). Merged into feat.
Task 12: dispatched T12Table in ../wt-t12 (task/t12, base c31cdac). Subtitle "Towers · Towers" fix folded into T12 (header = name + portrait).
Task 12: implementer DONE 30d51e0. Controller smoke: Knights card renders rows/sliders but no column or group headings. Review T12Review Needs fixes: 3 Important (th/td .text never rendered; tooltip leak per mutation; :.2f hides 0.002/0.015 originals), spec gap ("-" instead of blank), review-focus test gaps. Fix round 1 sent to T12Table (task-12-findings-r1.md).
Task 12: minor (deferred): positional slot reach-in at table.py:212; unused pytest import; blank line in main.py; report claim about keystroke round-trips wrong.
Ruling: scaling.scale quantizes decimal originals to max(2, decimals of the original) instead of fixed 2. Why: spec's "keep 2 decimals" would zero 0.002-style originals (17 real values); intent is avoiding float noise, not destroying precision. Folded into T12 fix round 1. Cost if wrong: a few values show 3-4 decimals.
Checked: main checkout has no profiles\ dir; the "26 changes" came from wt-t12\profiles (T12's manual run), not the owner's data.
Carry to T13: identifier markers without spaces (profile-item-<slug>, apply-mod, apply-run, speed-1..3, enemy-mult, troop-mult, unlock-switch, speed-key-1..3); tests click by marker; verify NiceGUI 3.18 APIs against .venv\Lib\site-packages\nicegui before use.
T2: minor (deferred): "Classic Bfg" should read "Classic BFG" (acronym casing).
Task 12: fix round 1/5 (5 addressed + precision ruling, 0 open; commits 30d51e0..fa94d30). Controller smoke: headers and group headings render; Bolin HERO SCREEN BARS, Damage type Physical.
Task 12: fix round 2 sent (controller findings task-12-findings-r2.md): float-noise originals show 15 decimals after the precision ruling (normalise to 6 places); s_ keys collide with real keys ("Cd mult" twice) -> Ruling: s_ keys labelled "<Label> (info text)" (they are the game's description numbers, 263 leaves).
Task 12: fix round 2/5 (3 addressed + raw-key tooltip; 1 new Important regression; commits fa94d30..573a9a3)
Task 12: fix round 3 sent: scale(o,100) != o for 85 float-noise originals ("mixed" on untouched rows, spurious changes) -> Ruling: scale returns the original unchanged at pct == 100; pre-existing InvalidOperation for 1e99 originals (sniper max_range) -> wider Decimal context.
Task 12: fix round 3/5 (2 addressed, 0 open; commits 573a9a3..04d9c8f). Real-tree probe: all 5857 leaves round-trip at 100, none raise.
Task 12: minor (deferred): 1e99 leaves may store a 99-digit int in the profile via _store (check writer formatting in final review).
Task 12: complete (commits c31cdac..04d9c8f, review clean after 3 rounds). Merged into feat.
Task 13: dispatching in ../wt-t13 (task/t13).
Task 13: implementer DONE 9ba3434. Controller smoke: top bar wraps to 2 rows, top sliders ~20 px, bottom bar not pinned. Review T13Review Needs fixes: 7 Important (footer not pinned; slider width; Reset all leaves table stale; profile switch on Rules shows a card; Apply mod with running modded game shows old count; modal log dialog vs spec non-blocking panel; live-slider logic copied 4x). Fix round 1 sent to T13Rules with minor cleanups folded in.
Task 13: minor (deferred): UPDATED_RUNNING still shows old missing/error lines; slider label updates only on release; some test assertions weak (highlight, panel).
Caution: an app launched manually from a worktree targets the REAL game mods folder (repo_dir.parent). Never click Apply/live controls in manual checks.
Task 13: fix round 1 implemented (9ba3434..309d7c8). Controller smoke with KRMOD_GAME_DIR=_scratch_game: one-row top bar, pinned footer, Apply wrote files to scratch mods and notified "Mod written: 0 changes"; top sliders 75 px but inactive track invisible on dark header. Re-review T13ReReview was dispatched then STOPPED at owner's request (paused).
PAUSED by owner. Resume point: re-dispatch the Task 13 fix-round-1 re-review (diff review-9ba3434..309d7c8.diff, findings task-13-findings-r1.md), then merge task/t13, then Task 15. Scratch folder C:\Games\KR6...\_scratch_game (hardlinked exe + lua51.dll, empty mods) exists for safe UI checks; delete at Task 17. mods\smoke\ helper bats still in the game folder; delete at Task 17.
Note for T13 re-review/final review: suite time rose 24 s -> 82 s with 309d7c8; check tests/test_ui_rules.py for real-interval ui.timer/log polling and make the poll interval injectable. Real mods\kr_mod_data.lua unchanged (18:20, archers 7, unlock on).
RESUMED by owner ("continue").
Task 13: fix round 1/5 (7 addressed, 0 open; commits 9ba3434..309d7c8). Suite slowdown: tests account ~5 s (sleep(1.2) x4); 82 s likely environmental.
Task 13: fix round 2 sent (task-13-findings-r2.md): invisible top-bar slider tracks (usability) + cleanups (AppState import, _slug alias, double Rules render, reload state reset), injectable poll interval, Apply-mod status when modded game runs.
Task 13: fix round 2/5 (4 addressed; new Important regression: refresh() always rerenders the card; commits 309d7c8..d35ec96). Controller smoke: top-bar tracks visible.
Task 13: fix round 3 sent (task-13-findings-r3.md).
Task 13: fix round 3/5 (3 addressed, 0 open; commits d35ec96..9422492)
Task 13: minor (deferred): POLL_INTERVAL_S set without monkeypatch in fixture; Rules pane rebuilt after its own slider release; missing blank lines main.py:80, applybar.py:136.
Task 13: complete (commits c200b27..9422492, review clean after 3 rounds). Merged into feat.
Task 13: merged 9e29db9; suite 288 passed; pushed.
Task 15: implementer T15Package DONE c1d2ddc (build.bat, README, pyproject/requirements.lock). Controller smoke of dist exe with KRMOD_GAME_DIR=_scratch_game: native window opens with portraits/one-row top bar/pinned footer; Archers price inputs 70,100,150,230; Apply wrote _scratch_game\mods (kr_mod\stats.lua etc.); real mods\kr_mod_data.lua unchanged (18:20); no nicegui/pywebview/KrGenesis folders under APPDATA/LOCALAPPDATA. Review pending.
Owner-reported defect: left sidebar and right editor scroll together (page-level scroll). Sent to T13Rules as a follow-up commit on feat (independent scroll areas, fixed header/footer). Rebuild exe after.
Task 15: review T15Review Approved. Minors to apply after the scroll fix lands (same checkout, avoid concurrent commits): build.bat --noconfirm (rebuild prompt), README first-time venv setup, README "keep the whole dist\KrGenesisMod folder (exe + _internal) together in place".
Owner scroll defect: fixed d2fb372 (T13Rules), review ScrollReview ADDRESSED, no breakage; controller smoke: page doesn't scroll, left/right independent. Reset main profiles\default.json troop_mult 1.5 -> 1.0 (left by the implementer's manual check).
Task 15: minors fixed 30098c1 (--noconfirm, README setup, dist placement). Exe rebuilt 22:53 including d2fb372. Task 15: complete (commits 9e29db9..30098c1). feat pushed.
Task 16: started. Owner checklist sent (acceptance 1-6 plus live apply, Heroic unlock, speed via app buttons).
For final review: windowed exe has no console; add an uncaught-exception hook writing tracebacks to cache\app.log, and confirm the frozen exe shows the error page with KRMOD_GAME_DIR pointed at an empty folder.
Owner change request: C1/row percentage sliders 0%-500% (was 50%-300%). Ruling: keep 100% at track centre (left 0->100, right 100->500); C2 unchanged; 0% allowed with existing warnings. Sent to T12Table (main checkout, no exe rebuild until the owner closes the app).
Slider range 0-500%: fdf126c (review RangeReview CORRECT) + 6b9be2b (track step 0.00125 so 125%/150% reachable). Suite 293 passed. feat pushed. Exe rebuilt (38 s) with both. Task 16 still waiting on owner results.
Owner bug: exe laggy, clicking a sidebar card shows nothing. Repro: frozen exe + CDP into WebView2 (WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333): click event sent, no server frames back, intermittent (about half of launches); source native 6/6 ok. Root cause: no freeze_support before app import in __main__, so the spawned window child re-ran krmod.app (load_state, portrait thread, page build) and truncated app.log. Fix 1d84ca8 (app.log redirect for windowed exe) + 4c25019 (freeze_support first). After fix frozen 8/8 ok. Exe rebuilt.
Owner request: game folder selectable. Dispatched GamePath in worktree ../wt-gamepath (branch wt/game-path from 1d84ca8). Contract: env KRMOD_GAME_DIR > settings.json in app folder > repo parent; picker on error page and in top bar.
Deferred minors: -0.0 from 0% on negative originals (normalise in _store); Heroes 10-level table overflows (row slider column cut off, labels wrap).
CORRECTION: A/B (pre-fix entry vs freeze_support entry, same harness, real and scratch game dir) gave 12/12 ok for BOTH builds. The window child shows --multiprocessing-fork with 0.1 s CPU, so it was not re-running load_state; the old child did import krmod.app and truncate app.log (pid in log was the child's). freeze_support kept (correct practice, fixes the log truncation) but the stall cause is UNPROVEN; failures (owner run, exe-dbg2, early trials) not reproducible since. Startup line added (commit "Write a startup line to app.log"); app.log verified to receive it. Next: add client connect/disconnect lines to app.log so an owner repro gives evidence.
Game folder selection: 0373680 + a8213a4 (GamePathReview: no stale refs, picker API correct; minors fixed: real switch test, picker tests with fake window, test isolation via KRMOD_GAME_DIR session fixture, io_bound load, cleanup of old flat portraits). Merged d9f3cd7, worktree removed. Plus "Log window connect and disconnect to app.log". Suite 321 passed. Exe rebuilt; frozen smoke: folder icon in top bar, native "Select Folder" dialog opens at current folder, cancel shows fallback input, app.log has startup + connect lines. Scratch mods cleared. feat pushed. Cleanup at T17: cache\test_game (test hardlinks, gitignored).
