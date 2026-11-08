"""Card portraits cut from the game's own art, cached as small PNGs.

Sources, all inside the exe zip under _assets/kr6-desktop/images/ipadhd_bc3/:
  room_tower.lua      atlas descriptor naming the standalone 1180x1120 DXT5 images
                      (tower_portraits_big_*, hero_portraits_big_*, power_portraits_big_*)
  gui_portraits.lua   atlas descriptor for the small HUD portraits, used for enemies
                      and for the Kingdom Rush 1 towers

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
    ("skills/powers/", "power_portraits_big_"),
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

# Kingdom Rush 1 tower (card id towers/kr1/<key>) -> n of gui_bottom_info_image_towers_<n>.
_KR1_TOWER_FRAMES = {
    "archers": 17, "musketeers": 18, "barracks": 19, "paladins": 20, "barbarians": 21,
    "mages": 22, "arcane": 23, "sorcerer": 24, "engineers": 25, "bfg": 26, "tesla": 27,
}
_KR1_PREFIX = "gui_bottom_info_image_towers_"

# Enemies the HUD atlas has no portrait for, taken from the encyclopedia thumbnails
# (a whole scene tile, so they look different) -> n of encyclopedia_enemies_thumb_<n>.
_ENEMY_THUMBS = {"dark_army/death_rider": 50}
_THUMB_PREFIX = "encyclopedia_enemies_thumb_"

# Descriptor key -> file name under IMAGES_DIR; each is read independently.
_DESCRIPTORS = {
    "room_tower": "room_tower.lua",
    "gui_portraits": "gui_portraits.lua",
    "encyclopedia_thumbs": "encyclopedia_thumbs.lua",
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
    for key, n in _KR1_TOWER_FRAMES.items():
        frame = frames["gui_portraits"].get(f"{_KR1_PREFIX}{n:04d}")
        if frame:
            wanted[f"towers/kr1/{key}"] = frame
    for key, n in _ENEMY_FRAMES.items():
        frame = frames["gui_portraits"].get(f"{_ENEMY_PREFIX}{n:04d}")
        if frame:
            wanted[f"enemies/{key}"] = frame
    for key, n in _ENEMY_THUMBS.items():
        frame = frames["encyclopedia_thumbs"].get(f"{_THUMB_PREFIX}{n:04d}")
        if frame:
            wanted[f"enemies/{key}"] = frame
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
