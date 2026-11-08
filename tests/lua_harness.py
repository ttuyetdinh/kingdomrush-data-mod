"""Runs the mod loader (mod_template) against stubbed game globals in the game's own LuaJIT."""
from __future__ import annotations

import shutil
from pathlib import Path

from krmod.gamedata.luart import LuaRuntime
from krmod.model.values import KeyPath
from krmod.modgen.luafmt import to_lua

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "mod_template"

_STUBS = r"""
NOW = 0
PRINTS = {}
GAME_UPDATES = 0
DRAWS = 0
LAST_KEY = nil
LEVEL_DATA = nil
WAITS = {}
SPAWN_CMDS = {}
RESULT = nil
F_BOSS = 0x10000
LAST_PRINT_X = nil
LAST_PRINT_Y = nil

love = {
  filesystem = { getSourceBaseDirectory = function() return GAME_DIR end },
  timer = { getTime = function() return NOW end },
  graphics = {
    print = function(text, x, y) table.insert(PRINTS, text); LAST_PRINT_X = x; LAST_PRINT_Y = y end,
    getColor = function() return 1, 1, 1, 1 end,
    setColor = function() end,
    push = function() end,
    pop = function() end,
    origin = function() end,
    getWidth = function() return 1920 end,
    getFont = function() return { getWidth = function(self, t) return 40 end } end,
  },
  getVersion = function() return 11, 4, 0 end,
}

game = {
  DBG_TIME_MULT = 1,
  store = { entities = {}, level = nil },
  update = function(self, dt) GAME_UPDATES = GAME_UPDATES + 1 end,
  keypressed = function(self, key, isrepeat) LAST_KEY = key end,
  draw = function(self) DRAWS = DRAWS + 1 end,
}

package.path = GAME_DIR .. "/?.lua;" .. package.path
package.preload["level_utils"] = function()
  return { load_data = function(st) return LEVEL_DATA end }
end
package.preload["entity_db"] = function()
  return { entities = {}, get_template = function(self, n) return self.entities[n] end }
end
package.preload["systems"] = function()
  return { wave_spawn_tsv = { cmd_fns = { spawn = function(store, cmd, wave) table.insert(SPAWN_CMDS, cmd) end } } }
end
package.preload["utils"] = function()
  return { y_wait = function(store, t) table.insert(WAITS, t) end }
end
package.loaded["scripts_game"] = { tower_stage_11_camp = { insert = function(this, store) return true end } }
"""


class ModHarness:
    def __init__(self, tmp_path: Path, dll: Path):
        self.game_dir = Path(tmp_path)
        self.mods_dir = self.game_dir / "mods"
        shutil.copytree(TEMPLATE_DIR, self.mods_dir)
        self._rt = LuaRuntime(dll)
        self._rt.set_global_string("GAME_DIR", self.game_dir.as_posix())
        self._rt.run(_STUBS, chunkname="=stubs")

    def close(self) -> None:
        self._rt.close()

    def write_raw(self, name: str, text: str) -> None:
        (self.mods_dir / name).write_text(text, encoding="utf-8")

    def write_data(
        self,
        changes: list[tuple[KeyPath, float]] = [],
        unlock: bool = False,
        speed_keys=("f5", "f6", "f7"),
    ) -> None:
        data = {
            "version": 1,
            "changes": [{"p": list(path), "v": value} for path, value in changes],
            "rules": {"unlock_tower_levels": unlock},
            "speed_keys": list(speed_keys),
        }
        self.write_raw("kr_mod_data.lua", "return " + to_lua(data) + "\n")

    def write_live(self, speed=1, enemy_mult=1.0, troop_mult=1.0) -> None:
        live = {"speed": speed, "enemy_mult": enemy_mult, "troop_mult": troop_mult}
        self.write_raw("kr_mod_live.lua", "return " + to_lua(live) + "\n")

    def lua(self, code: str) -> str | None:
        out = self._rt.run(code, chunkname="=test", want_result=True)
        return out.decode("utf-8", "replace") if out else None

    def run_level(self, balance_expr: str = "BAL") -> None:
        self._rt.run(
            "local function templates_game() "
            f"local balance = {balance_expr}; "
            'package.loaded["mods.kr_mod"] = nil; '
            # not a tail call: a tail call would drop templates_game's frame (and its local)
            'local m = require("mods.kr_mod"); return m end; '
            "RESULT = templates_game()",
            chunkname="=run_level",
        )

    def log(self) -> str:
        path = self.mods_dir / "kr_mod_log.txt"
        return path.read_text(encoding="utf-8") if path.exists() else ""
