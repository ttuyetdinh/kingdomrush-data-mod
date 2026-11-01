-- KrGenesis enemy count multiplier module.
-- Wraps systems.wave_spawn_tsv.cmd_fns.spawn to scale wave spawns by KRMOD.live.enemy_mult.
local M = {}

M.EXTRA_SPACING = 0.25

local ok_bit, bit_lib = pcall(require, "bit")
local bit = bit or (ok_bit and bit_lib)

local function contains(tbl, target)
  if type(tbl) ~= "table" then return false end
  for _, v in pairs(tbl) do
    if v == target then return true end
  end
  return false
end

local function shallow_copy(tbl)
  if type(tbl) ~= "table" then return tbl end
  local copy = {}
  for k, v in pairs(tbl) do
    copy[k] = v
  end
  return copy
end

-- Determine kind ("boss" | "carrier" | "normal") and return the template if found.
local function get_kind(E, store, o)
  local tpl = nil
  if E and type(E.get_template) == "function" and o and o.enemy then
    local ok, res = pcall(function() return E:get_template(o.enemy) end)
    if ok then tpl = res end
  end

  if F_BOSS and bit and type(bit.band) == "function" and tpl and type(tpl) == "table"
     and type(tpl.vis) == "table" and type(tpl.vis.flags) == "number" then
    if bit.band(tpl.vis.flags, F_BOSS) ~= 0 then
      return "boss", tpl
    end
  end

  local next_idx = (store.current_spawn_idx or 0) + 1
  if contains(store.gems_spawn_idx, next_idx) then
    return "carrier", tpl
  end

  return "normal", tpl
end

-- Plan number of spawns n for an entry given mult and kind.
-- Boss enemies always spawn 1 and leave K.enemy_acc untouched.
-- Otherwise adds mult to K.enemy_acc, floors to n (at least 1 for carrier), and subtracts n.
function M.plan(K, mult, kind)
  if kind == "boss" then
    return 1
  end
  mult = mult or 1
  local acc = (K and K.enemy_acc or 0) + mult
  local n = math.floor(acc)
  if kind == "carrier" then
    n = math.max(1, n)
  end
  if K then
    K.enemy_acc = acc - n
    if math.abs(K.enemy_acc) < 1e-9 then
      K.enemy_acc = 0
    end
  end
  return n
end

local function handle_spawn(original, K, ctx, store, cmd, mult, ...)
  if store.force_next_wave then return end

  local E = nil
  local ok_e, edb = pcall(require, "entity_db")
  if ok_e then E = edb end

  local U = nil
  local ok_u, utils = pcall(require, "utils")
  if ok_u then U = utils end

  local wait_time = cmd.wait_time
  local first_entry = true

  for _, o in ipairs(cmd.spawns) do
    if store.force_next_wave then break end

    local kind, tpl = get_kind(E, store, o)
    local n = M.plan(K, mult, kind)

    if n == 0 then
      if tpl ~= nil then
        store.current_spawn_idx = (store.current_spawn_idx or 0) + 1
      end
    elseif n >= 1 then
      local sub_cmd = shallow_copy(cmd)
      sub_cmd.spawns = { o }
      if first_entry then
        sub_cmd.wait_time = wait_time or 0
        first_entry = false
      else
        sub_cmd.wait_time = 0
      end

      if kind == "carrier" then
        local orig_gems = store.gems_per_wave
        store.gems_per_wave = (orig_gems or 0) * mult
        local ok, err = pcall(original, store, sub_cmd, ...)
        store.gems_per_wave = orig_gems
        if not ok then error(err) end
      else
        original(store, sub_cmd, ...)
      end

      if store.force_next_wave then break end

      for j = 1, n - 1 do
        if store.force_next_wave then break end
        if U and U.y_wait then
          U.y_wait(store, M.EXTRA_SPACING, function(st) return st.force_next_wave end)
        end
        if store.force_next_wave then break end

        local extra_cmd = shallow_copy(cmd)
        extra_cmd.spawns = { o }
        extra_cmd.wait_time = 0

        local orig_gems_idx = store.gems_spawn_idx
        local orig_spawn_idx = store.current_spawn_idx
        store.gems_spawn_idx = {}
        local ok, err = pcall(original, store, extra_cmd, ...)
        store.gems_spawn_idx = orig_gems_idx
        store.current_spawn_idx = orig_spawn_idx
        if not ok then error(err) end
      end
    end
  end
end

-- Wrap systems.wave_spawn_tsv.cmd_fns.spawn once.
function M.install(K, ctx)
  if K and K.installed and K.installed.enemies then return end

  local ok_sys, systems = pcall(require, "systems")
  if not ok_sys
     or type(systems) ~= "table"
     or type(systems.wave_spawn_tsv) ~= "table"
     or type(systems.wave_spawn_tsv.cmd_fns) ~= "table"
     or type(systems.wave_spawn_tsv.cmd_fns.spawn) ~= "function" then
    if ctx and ctx.log then
      ctx.log("error enemies: systems.wave_spawn_tsv.cmd_fns.spawn not found")
    end
    return
  end

  if not K.installed then K.installed = {} end
  K.installed.enemies = true

  local original = systems.wave_spawn_tsv.cmd_fns.spawn

  systems.wave_spawn_tsv.cmd_fns.spawn = function(store, cmd, ...)
    local mult = 1
    if K and K.live and type(K.live.enemy_mult) == "number" then
      mult = K.live.enemy_mult
    end

    if mult == 1 or type(store) ~= "table" or type(cmd) ~= "table" or type(cmd.spawns) ~= "table" then
      return original(store, cmd, ...)
    end

    local ok, err = pcall(handle_spawn, original, K, ctx, store, cmd, mult, ...)
    if not ok then
      if ctx and ctx.log then
        ctx.log("error enemies: " .. tostring(err))
      end
    end
  end
end

return M
