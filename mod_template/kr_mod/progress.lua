-- Hero unlock and extra skill points. The game loads the mod when the map screen opens
-- (and at every level start), so these show in the hero room and the skill tree screen.
-- Nothing here touches the save: the game works points out from these tables every time.
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
  if hero > 0 or upgrade > 0 then
    log("points: hero skills +" .. hero .. ", skill tree +" .. upgrade)
  end
end

-- screen_map:is_content_stage_unlocked(name, user_data) is the star check of the hero,
-- tower and spell rooms. Heroes ("hero_<name>") pass while is_enabled() is true; towers and
-- spells keep the game's check. Wraps each screen_map function once; returns false when the
-- map screen is not loaded.
function M.install_heroes(K, map, is_enabled)
  if type(map) ~= "table" or type(map.is_content_stage_unlocked) ~= "function" then
    return false
  end
  if map.is_content_stage_unlocked == K.heroes_wrapper then return true end
  local original = map.is_content_stage_unlocked
  K.heroes_wrapper = function(self, name, ...)
    if type(name) == "string" and name:sub(1, 5) == "hero_" and is_enabled() then
      return true
    end
    return original(self, name, ...)
  end
  map.is_content_stage_unlocked = K.heroes_wrapper
  return true
end

return M
