"""Card portraits cut from the game's own art, cached as small PNGs.

Sources, all inside the exe zip under _assets/kr6-desktop/images/ipadhd_bc3/:
  room_tower.lua        atlas descriptor naming the standalone 1180x1120 DXT5 images
                        (tower_portraits_big_*, hero_portraits_big_*, power_portraits_big_*)
  gui_portraits.lua     atlas descriptor for the small HUD portraits (the picture in the
                        bottom bar when a unit is clicked in a level), used for enemies,
                        troops, stage towers and heroes, and the Kingdom Rush 1 towers
  room_progression.lua  atlas descriptor holding the big item portraits

Families that cannot be matched reliably have no entry and portrait_for returns None.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from krmod.gamedata.luart import LuaRuntime
from krmod.paths import GamePaths

IMAGES_DIR = "_assets/kr6-desktop/images/ipadhd_bc3/"
MAX_SIDE = 256

# Runs a descriptor chunk and returns one tab separated line per frame:
#   <frame>\t<atlas file>\t<x>\t<y>\t<w>\t<h>
_WALKER = r"""
local frames = KRMOD_DESCRIPTOR()
local out = {}
for name, frame in pairs(frames) do
  if type(frame) == "table" and type(frame.f_quad) == "table" and frame.a_name then
    local q = frame.f_quad
    out[#out + 1] = table.concat({ name, frame.a_name, q[1], q[2], q[3], q[4] }, "\t")
  end
end
table.sort(out)
return table.concat(out, "\n")
"""

# (card id prefix, frame name prefix) for the standalone big portraits. The card id
# suffix and the frame name suffix are identical (towers/archers <-> ..._big_archers).
_BIG_FAMILIES = (
    ("towers/", "tower_portraits_big_"),
    ("heroes/", "hero_portraits_big_"),
    ("spells/", "power_portraits_big_"),
)
# The one tower whose frame name is singular.
_BIG_ALIASES = {"towers/culverine": "tower_portrait_big_culverine"}

# Enemy card id (without "enemies/") -> n of gui_bottom_info_image_enemies_<n>.
# Read from the game's enemy templates (each template names its HUD portrait) and
# checked by eye against the cropped frames.
_ENEMY_FRAMES = {
    "shadow_order/bandit": 1, "shadow_order/blackguard": 2, "shadow_order/shadow_blades": 3,
    "shadow_order/shadow_archer": 4, "shadow_order/crowcaller": 5, "shadow_order/crow": 6,
    "shadow_order/headhunter": 7, "shadow_order/demon_flareon": 63, "shadow_order/demon_spawn": 67,
    "orcs/goblin": 8, "orcs/wulf": 9, "orcs/orc_warrior": 10, "orcs/rider_goblin": 11,
    "orcs/worg": 12, "orcs/orc_wildling": 13, "orcs/orc_shaman": 14, "orcs/ogre": 15, "orcs/boss": 16,
    "deep_trolls/frost_brute": 19, "deep_trolls/troll_crusher": 20, "deep_trolls/troll_champion": 21,
    "deep_trolls/troll_chieftain": 22, "deep_trolls/troll_warrior": 23, "deep_trolls/frost_baiter": 24,
    "deep_trolls/troll_glider": 25, "deep_trolls/frost_icecaller": 26,
    "deep_trolls/troll_pathfinder": 27, "deep_trolls/troll_boss": 36,
    "jt_boss": 28,
    "spiders/giant_spider": 29, "spiders/spider_matriarch": 30, "spiders/spiderling": 31,
    "spiders/leaper_spider": 33, "spiders/son_of_sarelgaz": 34, "spiders/boss_spider": 35,
    "dark_army/exalted_shadow_blades": 42, "dark_army/exalted_shadow_archer": 43,
    "dark_army/exalted_crowcaller": 44, "dark_army/skeleton": 45, "dark_army/skeleton_big": 46,
    "dark_army/gargoyle": 47, "dark_army/brigand": 48, "dark_army/dark_sapper": 49,
    "dark_army/necromancer": 50, "dark_army/dark_disciple": 51, "dark_army/dark_knight": 52,
    "dark_army/skeleton_goat": 53, "dark_army/dark_construct": 54, "dark_army/darkling": 55,
    "dark_army/dark_slayer": 56, "dark_army/tainted_wolf": 57, "dark_army/swamp_thing": 58,
    "dark_army/swamp_husk": 59, "dark_army/rotten_tree": 61,
    "lord_blackburn_boss": 60,
    "demons/demon_hound": 64, "demons/demon_imp": 65, "demons/demon_lord": 66,
    "demons/magma_elemental": 68,
}
_ENEMY_PREFIX = "gui_bottom_info_image_enemies_"

# HUD frames (gui_bottom_info_image_<family>_<n>) by card id, read from the info.portrait
# of the game's unit templates and checked by eye against the cropped frames.
_HUD_PREFIX = "gui_bottom_info_image_"
_HUD_FRAMES: dict[str, tuple[str, int]] = {
    # Kingdom Rush 1 towers
    "towers/kr1/archers": ("towers", 17), "towers/kr1/musketeers": ("towers", 18),
    "towers/kr1/barracks": ("towers", 19), "towers/kr1/paladins": ("towers", 20),
    "towers/kr1/barbarians": ("towers", 21), "towers/kr1/mages": ("towers", 22),
    "towers/kr1/arcane": ("towers", 23), "towers/kr1/sorcerer": ("towers", 24),
    "towers/kr1/engineers": ("towers", 25), "towers/kr1/bfg": ("towers", 26),
    "towers/kr1/tesla": ("towers", 27), "towers/kr1/ranger": ("towers", 5),
    # Troops (level 1 picture where a troop has one per level)
    "troops/towers.alchemist.skill_b.soldier": ("soldiers", 56),
    "troops/towers.crossbows.ultimate.soldier": ("soldiers", 65),
    "troops/towers.knights.soldier": ("soldiers", 11),
    "troops/towers.miners.skill_a.soldier": ("soldiers", 61),
    "troops/towers.miners.soldier": ("soldiers", 61),
    "troops/towers.sunray_master.skill_a.soldier": ("soldiers", 41),
    "troops/towers.tree.soldier": ("soldiers", 22),
    "troops/towers.tree.ultimate.seedling": ("soldiers", 26),
    "troops/towers.wildcat.soldier": ("soldiers", 37),
    "troops/kr1_mode.towers.barbarians.soldier": ("soldiers", 35),
    "troops/kr1_mode.towers.barracks.soldier": ("soldiers", 31),
    "troops/kr1_mode.towers.paladins.soldier": ("soldiers", 34),
    "troops/kr1_mode.towers.sorcerer.elemental.soldier": ("soldiers", 30),
    "troops/heroes.hero_drakkan.skill_c.clone": ("soldiers", 20),
    "troops/heroes.hero_myriath.clone": ("heroes", 9),
    "troops/powers.aspect_of_sol.soldier": ("soldiers", 45),
    "troops/powers.musketeers.soldier": ("soldiers", 66),
    "troops/powers.reinforcements.soldier": ("soldiers", 1),
    "troops/powers.reinforcements.special_soldier": ("soldiers", 10),
    "troops/specials.heroes.hero_alleria.wildcat.soldier": ("soldiers", 15),
    "troops/specials.heroes.hero_denas.denas_guards.soldier": ("heroes", 18),  # Denas's own
    "troops/specials.stage_06.nivus.books.soldier": ("soldiers", 19),
    "troops/specials.towers.stage_07_barn.soldier": ("soldiers", 16),
    "troops/specials.towers.stage_11_tower_camp.soldier": ("soldiers", 16),
    "troops/specials.towers.stage_14_armory.soldier": ("soldiers", 59),
    "troops/specials.towers.stage_17_paladin_barracks.soldier": ("towers", 8),  # the barracks'
    # Stage towers and heroes
    "stages/heroes/hero_alleria": ("heroes", 2),
    "stages/heroes/hero_denas": ("heroes", 18),
    "stages/towers/stage_04_crane": ("towers", 6),
    "stages/towers/stage_07_barn": ("towers", 8),
    "stages/towers/stage_08_catapult": ("towers", 7),
    "stages/towers/stage_11_tower_camp": ("towers", 11),
    "stages/towers/stage_13_sunray_obelisk": ("towers", 12),
    "stages/towers/stage_13_sunray_tower": ("towers", 12),
    "stages/towers/stage_14_armory": ("towers", 32),
    "stages/towers/stage_14_blacksmith": ("towers", 33),
    "stages/towers/stage_16_treant_attacker": ("towers", 6),
    "stages/towers/stage_16_treant_healer": ("towers", 6),
    "stages/towers/stage_16_treant_killer": ("towers", 6),
    "stages/towers/stage_16_treant_rooter": ("towers", 6),
    "stages/towers/stage_17_paladin_barracks": ("towers", 8),
}

# Enemies the HUD atlas has no portrait for, taken from the encyclopedia thumbnails
# (a whole scene tile, so they look different) -> n of encyclopedia_enemies_thumb_<n>.
_ENEMY_THUMBS = {"dark_army/death_rider": 50}
_THUMB_PREFIX = "encyclopedia_enemies_thumb_"

# Item card id -> frame of the big item portraits.
_ITEM_FRAMES = {f"items/{k}": f"portraits_big_item_{k}" for k in ("bomb", "gold", "hearts")}

# Descriptor key -> file name under IMAGES_DIR; each is read independently.
_DESCRIPTORS = {
    "room_tower": "room_tower.lua",
    "gui_portraits": "gui_portraits.lua",
    "encyclopedia_thumbs": "encyclopedia_thumbs.lua",
    "room_progression": "room_progression.lua",
}


def _file_name(card_id: str) -> str:
    return card_id.replace("/", "__") + ".png"


def portrait_for(card_id: str, portraits_dir: Path) -> Path | None:
    """Cached portrait for a card id (see GamePaths.portraits_dir), or None when there is none."""
    path = Path(portraits_dir) / _file_name(card_id)
    return path if path.is_file() else None


def _read_frames(lua: LuaRuntime, exe: zipfile.ZipFile, descriptor: str) -> dict[str, tuple[str, int, int, int, int]]:
    lua.set_global_bytes("KRMOD_DESCRIPTOR_BLOB", exe.read(IMAGES_DIR + descriptor))
    lua.run("KRMOD_DESCRIPTOR = assert(loadstring(KRMOD_DESCRIPTOR_BLOB))", "=load_descriptor")
    text = lua.run(_WALKER, "=descriptor_walker", want_result=True).decode("utf-8")
    frames: dict[str, tuple[str, int, int, int, int]] = {}
    for line in text.split("\n"):
        name, atlas, x, y, w, h = line.split("\t")
        frames[name] = (atlas, int(x), int(y), int(w), int(h))
    return frames


class _Atlases:
    """Decodes each DDS atlas at most once."""

    def __init__(self, exe: zipfile.ZipFile):
        self._exe = exe
        self._images: dict[str, Image.Image] = {}

    def crop(self, frame: tuple[str, int, int, int, int]) -> Image.Image:
        atlas, x, y, w, h = frame
        if atlas not in self._images:
            with Image.open(io.BytesIO(self._exe.read(IMAGES_DIR + atlas))) as dds:
                self._images[atlas] = dds.convert("RGBA")
        return self._images[atlas].crop((x, y, x + w, y + h))

    def release(self, atlas: str) -> None:
        self._images.pop(atlas, None)


def _save(image: Image.Image, path: Path) -> None:
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    image.save(tmp, format="PNG")
    tmp.replace(path)


def _wanted(frames: dict) -> dict[str, tuple[str, int, int, int, int]]:
    """Card id -> frame, for every portrait this module can match."""
    wanted: dict[str, tuple[str, int, int, int, int]] = {}
    for card_prefix, frame_prefix in _BIG_FAMILIES:
        for name, frame in frames["room_tower"].items():
            if name.startswith(frame_prefix):
                wanted[card_prefix + name[len(frame_prefix):]] = frame
    for card_id, frame_name in _BIG_ALIASES.items():
        frame = frames["room_tower"].get(frame_name)
        if frame:
            wanted[card_id] = frame
    for card_id, (family, n) in _HUD_FRAMES.items():
        frame = frames["gui_portraits"].get(f"{_HUD_PREFIX}{family}_{n:04d}")
        if frame:
            wanted[card_id] = frame
    for key, n in _ENEMY_FRAMES.items():
        frame = frames["gui_portraits"].get(f"{_ENEMY_PREFIX}{n:04d}")
        if frame:
            wanted[f"enemies/{key}"] = frame
    for key, n in _ENEMY_THUMBS.items():
        frame = frames["encyclopedia_thumbs"].get(f"{_THUMB_PREFIX}{n:04d}")
        if frame:
            wanted[f"enemies/{key}"] = frame
    for card_id, frame_name in _ITEM_FRAMES.items():
        frame = frames["room_progression"].get(frame_name)
        if frame:
            wanted[card_id] = frame
    return wanted


def _read_all_frames(paths: GamePaths, exe: zipfile.ZipFile) -> dict[str, dict[str, tuple[str, int, int, int, int]]]:
    """Each descriptor on its own: one that cannot be read leaves only its family without portraits."""
    frames: dict[str, dict[str, tuple[str, int, int, int, int]]] = {key: {} for key in _DESCRIPTORS}
    try:
        with LuaRuntime(paths.lua_dll) as lua:
            for key, entry in _DESCRIPTORS.items():
                try:
                    frames[key] = _read_frames(lua, exe, entry)
                except Exception:
                    continue
    except Exception:
        pass
    return frames


def _remove_flat_cache(cache_dir: Path) -> None:
    """Delete the PNGs of the old shared cache (directly in cache/portraits, before it was
    split per game folder); the per-folder subdirectories are left alone."""
    for old in (Path(cache_dir) / "portraits").glob("*.png"):
        try:
            old.unlink()
        except OSError:
            pass


def build_portrait_cache(paths: GamePaths) -> int:
    """Write every missing portrait PNG under paths.portraits_dir; return how many were written.

    Existing files are kept, so repeated starts only read the exe when something is missing.
    Best effort and never raises (it runs in a background thread): an unreadable exe,
    descriptor, atlas or frame leaves only the affected cards without a portrait.
    """
    out_dir = paths.portraits_dir
    written = 0
    _remove_flat_cache(paths.cache_dir)
    try:
        with zipfile.ZipFile(paths.exe) as exe:
            wanted = _wanted(_read_all_frames(paths, exe))
            todo = {cid: fr for cid, fr in wanted.items() if not (out_dir / _file_name(cid)).is_file()}
            atlases = _Atlases(exe)
            # Group by atlas so each big DDS is decoded once and then dropped.
            by_atlas: dict[str, list[str]] = {}
            for cid, fr in todo.items():
                by_atlas.setdefault(fr[0], []).append(cid)
            for atlas, card_ids in by_atlas.items():
                for cid in card_ids:
                    try:
                        _save(atlases.crop(todo[cid]), out_dir / _file_name(cid))
                        written += 1
                    except Exception:
                        continue
                atlases.release(atlas)
    except Exception:
        return written
    return written
