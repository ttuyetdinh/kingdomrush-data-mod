-- Removes "<tower>_lvlN" entries from level lock lists so every tower can be upgraded.
local M = {}

-- Strip level locks from `list` in place; every other entry keeps its order.
-- Returns removed, kept.
function M.strip(list)
  if type(list) ~= "table" then return 0, 0 end
  local removed, i = 0, 1
  while list[i] ~= nil do
    local name = list[i]
    if type(name) == "string" and name:match("_lvl%d+$") then
      table.remove(list, i)
      removed = removed + 1
    else
      i = i + 1
    end
  end
  return removed, #list
end

local function strip_logged(list, label, log)
  if type(list) ~= "table" then return end
  local removed, kept = M.strip(list)
  log("unlock " .. label .. ": removed " .. removed .. ", kept " .. kept)
end

local function tag(st)
  st = st or {}
  return tostring(st.level_name) .. " mode " .. tostring(st.level_mode)
end

-- The level is usually loaded before the override runs: patch the live store now.
function M.apply_current(store, enabled, log)
  if not enabled or type(store) ~= "table" or type(store.level) ~= "table" then return end
  local label = tag(store)
  strip_logged(store.level.locked_towers, label, log)
  if type(store.level.data) == "table" then
    strip_logged(store.level.data.locked_towers, label, log)
  end
end

-- Wrap LU.load_data once so later level loads are stripped too (when is_enabled()).
function M.install(K, LU, is_enabled, log)
  if K.installed.unlock then return end
  if type(LU) ~= "table" or type(LU.load_data) ~= "function" then
    log("error unlock: level_utils.load_data not found")
    return
  end
  K.installed.unlock = true
  local original = LU.load_data
  local function finish(st, data, ...)
    if type(data) == "table" then
      local ok, err = pcall(function()
        if is_enabled() then strip_logged(data.locked_towers, "load_data " .. tag(st), log) end
      end)
      if not ok then log("error unlock: " .. tostring(err)) end
    end
    return data, ...
  end
  LU.load_data = function(st, ...)
    return finish(st, original(st, ...))
  end
end

return M
