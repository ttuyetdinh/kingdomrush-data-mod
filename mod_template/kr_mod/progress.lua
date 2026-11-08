-- Hero, tower and spell unlocks and extra skill points. The game loads the mod when the map
-- screen opens (and at every level start), so these show in the hero, tower, spell and skill
-- tree screens. Nothing here writes the save: the game works these out every time.
local M = {}

-- game_settings tables: total hero skill points per hero level, and total skill tree
-- points per furthest finished stage. What the player can spend is the total minus spent.
local POINT_TABLES = {
  hero = "skill_points_for_hero_level",
  upgrade = "upgrades_points_per_stage",
}

local function whole(n)
  n = tonumber(n) or 0
  if n < 0 then return 0 end
  return math.floor(n)
end

-- Set every entry of GS[name] to the game's own value plus extra. The game's values are
-- copied the first time each table is seen, so repeated runs never stack and an extra of 0
-- puts the game's numbers back. Returns false when the table is missing.
local function add_extra(K, GS, name, extra)
  local t = GS[name]
  if type(t) ~= "table" then return false end
  K.points_orig = K.points_orig or {}
  local saved = K.points_orig[name]
  if not saved or saved.table ~= t then
    saved = { table = t, values = {} }
    for i, v in ipairs(t) do saved.values[i] = v end
    K.points_orig[name] = saved
  end
  for i, v in ipairs(saved.values) do t[i] = v + extra end
  return true
end

function M.apply_points(K, GS, rules, log)
  if type(GS) ~= "table" then
    log("error points: game settings not found")
    return
  end
  local hero = whole(rules.extra_hero_points)
  local upgrade = whole(rules.extra_upgrade_points)
  if not add_extra(K, GS, POINT_TABLES.hero, hero) then
    log("error points: hero skill point table not found")
  end
  if not add_extra(K, GS, POINT_TABLES.upgrade, upgrade) then
    log("error points: skill tree point table not found")
  end
  local spell = whole(rules.extra_spell_points)
  if hero > 0 or spell > 0 or upgrade > 0 then
    log("points: hero skills +" .. hero .. ", spell skills +" .. spell .. ", skill tree +" .. upgrade)
  end
end

-- The spell room has no point table: PowerRoomView:get_unit_stats(name) returns the spell's
-- remaining_points (spell level - 1 - spent). The wrapper adds get_extra() to it, so the room,
-- its point label and its skill tree all see the extra. Wraps each function once; returns
-- false when the spell room is not loaded.
function M.install_spell_points(K, view, get_extra)
  if type(view) ~= "table" or type(view.get_unit_stats) ~= "function" then return false end
  if view.get_unit_stats == K.spell_points_wrapper then return true end
  local original = view.get_unit_stats
  K.spell_points_wrapper = function(...)
    local out = original(...)
    if type(out) == "table" and type(out.remaining_points) == "number" then
      out.remaining_points = out.remaining_points + whole(get_extra())
    end
    return out
  end
  view.get_unit_stats = K.spell_points_wrapper
  return true
end

-- Content names of the star check, by rule: "hero_<name>", "tower_<name>", "power_<name>".
local STAR_PREFIXES = {
  unlock_heroes = "hero_",
  unlock_towers = "tower_",
  unlock_spells = "power_",
}

-- True when the name belongs to a rule that is on in rules.
function M.passes(rules, name)
  if type(name) ~= "string" or type(rules) ~= "table" then return false end
  for rule, prefix in pairs(STAR_PREFIXES) do
    if rules[rule] == true and name:sub(1, #prefix) == prefix then return true end
  end
  return false
end

-- screen_map:is_content_stage_unlocked(name, user_data) is the star check of the hero,
-- tower and spell rooms. Names for which M.passes(get_rules(), name) is true are unlocked;
-- everything else keeps the game's check. Wraps each screen_map function once; returns
-- false when the map screen is not loaded.
function M.install_star_unlocks(K, map, get_rules)
  if type(map) ~= "table" or type(map.is_content_stage_unlocked) ~= "function" then
    return false
  end
  if map.is_content_stage_unlocked == K.star_wrapper then return true end
  local original = map.is_content_stage_unlocked
  K.star_wrapper = function(self, name, ...)
    if M.passes(get_rules(), name) then return true end
    return original(self, name, ...)
  end
  map.is_content_stage_unlocked = K.star_wrapper
  return true
end

return M
