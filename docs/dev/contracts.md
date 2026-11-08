# Global constraints and shared contracts

## Global Constraints

- Game folder: C:\Games\KR6.Genesis.TD.v1.01.008_LinkNeverDie.Com. Repo: its subfolder kingdomrush-data-mod\ (remote ttuyetdinh/kingdomrush-data-mod, private).
- Never modify Kingdom Rush Genesis.exe or any original game file. A normal launch must stay vanilla.
- Everything new lives in new folders inside the game folder. Nothing goes to %APPDATA%. NiceGUI storage and WebView2 data go under kingdomrush-data-mod\cache\.
- Never commit game files, bytecode, decompiled code, extracted art or the owner's profiles. The .gitignore blocks every *.lua except mod_template\**\*.lua. Test fixtures are hand-written Lua inside Python tests, never game-derived.
- Python and the packaged app are 64-bit (lua51.dll is x64).
- Original values are read at every start from the exe zip: run all/constants.lua, then kr6/data/balance/balance.lua, with luaL_loadbuffer (explicit length), never luaL_loadstring.
- Verified facts the tests pin: 5,857 numbers, 34 strings, 7 booleans, 1,665 tables, 0 aliased tables; towers.archers.price[1] = 70.
- Profile stores changes only (path → value). A change equal to its original is removed.
- Mod launch: Kingdom Rush Genesis.exe -balance_override mods.kr_mod, working directory = game folder.
- Live controls: speed 1/2/3; enemy_mult is one of 0.25, 1, 2, ..., 10 (default 1); troop_delta is a whole number of extra soldiers per barracks from -10 to +10 (default 0; a barracks never goes below 0 soldiers, and a barracks or upgrade level whose game count is 0 stays 0). Speed keys default f5/f6/f7; forbidden keys: f1, f2, f3, space, escape, return, up, down, left, right.
- C1 slider: 0% to 500%, piecewise with 100% at the centre (left half 0→100, right half 100→500). Skips cells whose original is 0. C2 range: 0 to max(10, 3 × largest absolute original in the row).
- Rounding: whole-number originals give whole results (round half up, away from zero); decimal originals keep 2 decimals (round half up).
- Warn (allow, but flag) negative values, and 0 for any key containing cooldown or duration.
- Window title "KrGenesis Mod". Internal server binds 127.0.0.1 only. Exe: kingdomrush-data-mod\dist\KrGenesisMod\KrGenesisMod.exe.
- Git: work on feature branch feat/krgenesis-mod cut from origin/main, then git branch --unset-upstream; first push git push -u origin feat/krgenesis-mod. Parallel tasks use isolated worktrees merged back into that branch. No AI attribution in commits or PRs. No em-dashes in prose.
- The loader must never crash the game: every section runs under pcall and logs errors to mods\kr_mod_log.txt.


## Shared Contracts

These formats cross task boundaries. Every task that touches them uses them exactly.

**KeyPath:** tuple[str | int, ...]. Integer segments are Lua array indices. path_str(("towers","archers","price",1)) == "towers.archers.price.1". The Lua loader logs paths in the same dotted form.

**mods\kr_mod_data.lua** (written by Task 9, read by the loader):

```lua
return {
  version = 1,
  changes = {
    { p = { "towers", "archers", "price", 1 }, v = 7 },
  },
  rules = { unlock_tower_levels = false },
  speed_keys = { "f5", "f6", "f7" },
}
```

**mods\kr_mod_live.lua** (written atomically by Task 9, polled by the loader): return { speed = 1, enemy_mult = 1.0, troop_delta = 0 }, plus an optional seq counter (the app bumps it on every speed button click; the poller re-applies the file's speed whenever seq changes). The loader ignores the whole file when enemy_mult is not an allowed value or troop_delta is not an integer in -10..10.

**Loader session table:** global KRMOD = { installed = {}, originals = {}, live = { speed = 1, enemy_mult = 1, troop_delta = 0 }, speed_keys = { "f5","f6","f7" }, pollers = {}, enemy_acc = {} (per-stream accumulators keyed by pi|enemy, reset at each level start; ruling on Task 7), data = <last data table>, base = <game dir> }.

**Loader module shape:** each file in mod_template\kr_mod\ returns a table M. Feature modules expose M.install(K, ctx), where K is KRMOD and ctx = { base = <game dir>, log = function(line) }. install is called at every level start and must guard its own hooks with K.installed.<name>.

**Log lines** (mods\kr_mod_log.txt, truncated at each level start, appended by live events):
- applied <n> changes
- missing <dotted path>
- unlock <label>: removed <n>, kept <m>
- speed x<n>
- enemies x<mult>
- troops <+n|-n|0>: <n> barracks
- error <text>

**Profile JSON** (profiles\<slug>.json; slug = name lowercased, runs of non [a-z0-9] → "-", trimmed):

```json
{"version": 1, "name": "Easy mode",
 "changes": [{"path": ["towers", "archers", "price", 1], "value": 7}],
 "rules": {"unlock_tower_levels": false},
 "live": {"speed": 1, "enemy_mult": 1.0, "troop_delta": 0},
 "speed_keys": ["f5", "f6", "f7"]}
```

profiles\_active.json holds {"active": "<name>"}.


## Controller rulings (binding, override the plan text where they differ)

- R1 Tests import the checkout they run in: pyproject [tool.pytest.ini_options] gets pythonpath = ["."] (the editable install in the shared .venv points at the main checkout; worktrees must still test their own krmod).
- R2 Use the shared venv by absolute path: C:\Games\KR6.Genesis.TD.v1.01.008_LinkNeverDie.Com\kingdomrush-data-mod\.venv\Scripts\python.exe (created in Task 1). Worktrees have no .venv of their own.
- R3 Task-specific fixtures (enemy_h, troop_h, tmp_game, state, user fixtures for UI) live in that task's own test module unless the brief says conftest.py. conftest.py holds only game_paths, tree, lua (Task 1) and harness (Task 5).
- R4 Commit only the files your task owns (git add <paths>), never git add -A. No AI attribution in commit messages. No em-dashes in prose or comments.
- R5 Never touch the game exe, original game files, or %APPDATA%. Tests that write files use tmp_path.
- R6 Shell: this Windows host's `bash` is WSL and broken; use the bash tool's default shell or "C:/Program Files/Git/bin/bash.exe" for sh scripts. Run python via the absolute venv path above.
