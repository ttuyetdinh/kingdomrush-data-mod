-- KrGenesis mod loader. Loaded by the game through -balance_override mods.kr_mod
-- from the function that builds the balance table (it holds a local named "balance").
-- Runs at every level start. Every section runs under pcall: this file never raises
-- into the game; problems go to mods/kr_mod_log.txt.
local DEFAULT_SPEED_KEYS = { "f5", "f6", "f7" }

local function main(found, stats)
  local ok_base, base = pcall(love.filesystem.getSourceBaseDirectory)
  if not ok_base or type(base) ~= "string" then base = "." end
  base = base:gsub("\\", "/")

  if type(KRMOD) ~= "table" then
    KRMOD = {
      installed = {},
      originals = {},
      live = { speed = 1, enemy_mult = 1, troop_mult = 1 },
      speed_keys = { DEFAULT_SPEED_KEYS[1], DEFAULT_SPEED_KEYS[2], DEFAULT_SPEED_KEYS[3] },
      pollers = {},
      enemy_acc = 0,
    }
  end
  local K = KRMOD
  K.base = base

  local ok_util, util = pcall(dofile, base .. "/mods/kr_mod/util.lua")
  if not ok_util or type(util) ~= "table" then return end

  util.log_open(base .. "/mods/kr_mod_log.txt")
  local log = util.log
  if not ok_base then log("error base: love.filesystem.getSourceBaseDirectory failed") end

  local function step(name, fn)
    local ok, err = pcall(fn)
    if not ok then log("error " .. name .. ": " .. tostring(err)) end
  end

  local data = { changes = {}, rules = {} }
  step("data", function()
    local loaded, err = util.load_table(base .. "/mods/kr_mod_data.lua")
    if loaded then
      data = loaded
    else
      log("error data: " .. tostring(err))
    end
    if type(data.changes) ~= "table" then data.changes = {} end
    if type(data.rules) ~= "table" then data.rules = {} end
    local keys = data.speed_keys
    if type(keys) ~= "table" or #keys == 0 then keys = DEFAULT_SPEED_KEYS end
    K.speed_keys = { keys[1], keys[2], keys[3] }
  end)
  K.data = data

  step("stats", function()
    if not stats then error("stats module failed to load") end
    if not found then
      log("error balance local not found")
      return
    end
    local applied, missing = stats.apply(found, data.changes, K)
    log("applied " .. applied .. " changes")
    for _, path in ipairs(missing) do log("missing " .. path) end
    package.loaded["data.balance.balance"] = found
  end)

  step("unlock", function()
    local unlock = dofile(base .. "/mods/kr_mod/unlock.lua")
    unlock.apply_current(game and game.store, data.rules.unlock_tower_levels, log)
    unlock.install(K, require("level_utils"), function()
      return K.data.rules.unlock_tower_levels
    end, log)
  end)

  local ctx = { base = base, log = log }
  for _, name in ipairs({ "live", "enemies", "troops" }) do
    step("module " .. name, function()
      local m, err = util.load_module(base, name)
      if not m then
        log("error module " .. name .. " missing")
        if err and not tostring(err):find("cannot open", 1, true) then
          log("error module " .. name .. ": " .. tostring(err))
        end
        return
      end
      m.install(K, ctx)
    end)
  end
end

-- The stack search must run close to the caller (it scans a fixed number of levels
-- up), so it happens here in the chunk body, not inside main's nested pcalls.
local stats
do
  local ok_base, base = pcall(love.filesystem.getSourceBaseDirectory)
  if ok_base and type(base) == "string" then
    local ok, mod = pcall(dofile, base:gsub("\\", "/") .. "/mods/kr_mod/stats.lua")
    if ok and type(mod) == "table" then stats = mod end
  end
end
local found = stats and stats.find_balance()

local ok, err = pcall(main, found, stats)
if not ok then
  pcall(function()
    local f = io.open("mods/kr_mod_log.txt", "a")
    if f then f:write("error loader: " .. tostring(err) .. "\n") f:close() end
  end)
end
return true
