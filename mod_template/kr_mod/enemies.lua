-- KrGenesis enemy count multiplier module.
-- Wraps systems.wave_spawn_tsv.cmd_fns.spawn to scale wave spawns by KRMOD.live.enemy_mult.
-- Extra copies walk side by side: each row fills the road's lines (the original's line first),
-- and the next row follows EXTRA_SPACING seconds later.
--
-- Every road of the game has 3 rails: 1 in the middle, 2 and 3 on the edges. When copies are
-- needed, two inner rails are added to every road of the level, a third of the way from the
-- middle to each edge, so a row is 4 evenly spaced lines: 2, INNER[1], INNER[2], 3. Their keys
-- are far above 3 so #P.paths[pi] stays 3: the game's own "random rail" picks and loops never
-- see them. Only rows walk on them: the copies, and an original that has copies (one from the
-- middle rail or a random rail joins its row on one of the 4 lines).
local M = {}

M.EXTRA_SPACING = 0.25
M.INNER = { 101, 102 }

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

-- Plan number of spawns n for an entry given mult, kind and stream key.
-- Boss enemies always spawn 1 and leave accumulators untouched.
-- Otherwise adds mult to stream accumulator, floors to n (at least 1 for carrier), and subtracts n.
function M.plan(K, mult, kind, key)
  if kind == "boss" then
    return 1
  end
  mult = mult or 1
  local accs = K and K.enemy_acc
  if type(accs) ~= "table" then
    accs = {}
    if K then K.enemy_acc = accs end
  end
  local cur = (key and accs[key]) or 0
  local acc = cur + mult
  local n = math.floor(acc)
  if kind == "carrier" then
    n = math.max(1, n)
  end
  local rem = acc - n
  if math.abs(rem) < 1e-9 then
    rem = 0
  end
  if key then
    accs[key] = rem
  end
  return n
end

local function node_count(rail)
  return type(rail) == "table" and #rail or 0
end

-- Add the inner rails to every road of P once per level (P.paths is a new table each level).
-- All or nothing: an enemy keeps its rail number when it walks onto the next road, so every road
-- needs them. Returns true when the roads have them.
function M.add_inner_rails(P)
  local paths = type(P) == "table" and P.paths or nil
  if type(paths) ~= "table" or #paths == 0 then return false end
  if M._railed == paths then return true end
  for pi = 1, #paths do
    local road = paths[pi]
    if type(road) ~= "table" then return false end
    local n = node_count(road[1])
    if n == 0 or node_count(road[2]) ~= n or node_count(road[3]) ~= n then return false end
  end
  for pi = 1, #paths do
    local mid, left, right = paths[pi][1], paths[pi][2], paths[pi][3]
    local inner_left, inner_right = {}, {}
    for ni = 1, #mid do
      local c, l, r = mid[ni], left[ni], right[ni]
      inner_left[ni] = { x = c.x + (l.x - c.x) / 3, y = c.y + (l.y - c.y) / 3 }
      inner_right[ni] = { x = c.x + (r.x - c.x) / 3, y = c.y + (r.y - c.y) / 3 }
    end
    paths[pi][M.INNER[1]] = inner_left
    paths[pi][M.INNER[2]] = inner_right
  end
  M._railed = paths
  return true
end

-- The lines of one row (left to right) for an entry, and the line the original takes. With the
-- inner rails: 2, INNER[1], INNER[2], 3, and an original on the middle rail or on "*" takes a
-- random one of them. Without them: the road's rails 1..n, "*" picking one as the game would.
-- An unknown rail gives no row: copies then spawn one behind another on the original's rail.
function M.lanes(P, o)
  local road = type(P) == "table" and type(P.paths) == "table" and P.paths[o.pi] or nil
  local rails = type(road) == "table" and #road or 1
  if rails < 1 then rails = 1 end
  local spi = o.spi
  if spi ~= "*" and (type(spi) ~= "number" or spi < 1 or spi > rails or spi ~= math.floor(spi)) then
    return nil, nil
  end
  local row
  if rails == 3 and M.add_inner_rails(P) then
    row = { 2, M.INNER[1], M.INNER[2], 3 }
    if spi == "*" or spi == 1 then spi = row[math.random(#row)] end
  else
    row = {}
    for i = 1, rails do row[i] = i end
    if spi == "*" then spi = math.random(rails) end
  end
  for i, lane in ipairs(row) do
    if lane == spi then return row, i end
  end
  return nil, nil
end

-- Spawn one row of copies of o at the same moment, one per given lane, without touching the
-- wave's spawn counter or gem carriers.
local function spawn_row(original, store, cmd, o, lanes_in_row, ...)
  local row_cmd = shallow_copy(cmd)
  row_cmd.wait_time = 0
  row_cmd.spawns = {}
  for _, lane in ipairs(lanes_in_row) do
    local copy = shallow_copy(o)
    if lane then copy.spi = lane end
    row_cmd.spawns[#row_cmd.spawns + 1] = copy
  end
  local orig_gems_idx = store.gems_spawn_idx
  local orig_spawn_idx = store.current_spawn_idx
  store.gems_spawn_idx = {}
  local ok, err = pcall(original, store, row_cmd, ...)
  store.gems_spawn_idx = orig_gems_idx
  store.current_spawn_idx = orig_spawn_idx
  if not ok then error(err) end
end

local function handle_spawn(original, K, ctx, store, cmd, mult, ...)
  if store.force_next_wave then return end

  local wait_time = cmd.wait_time
  if wait_time and wait_time > 0 then
    local wait_cmd = shallow_copy(cmd)
    wait_cmd.spawns = {}
    original(store, wait_cmd, ...)
    if store.force_next_wave then return end
  end

  local E = nil
  local ok_e, edb = pcall(require, "entity_db")
  if ok_e then E = edb end

  local U = nil
  local ok_u, utils = pcall(require, "utils")
  if ok_u then U = utils end

  local P = nil
  local ok_p, pdb = pcall(require, "path_db")
  if ok_p then P = pdb end

  for _, o in ipairs(cmd.spawns) do
    if store.force_next_wave then break end

    local key = tostring(o.pi) .. "|" .. tostring(o.enemy)
    local kind, tpl = get_kind(E, store, o)
    local n = M.plan(K, mult, kind, key)

    if n == 0 then
      if tpl ~= nil then
        store.current_spawn_idx = (store.current_spawn_idx or 0) + 1
      end
    elseif n >= 1 then
      -- A single enemy keeps its rail; copies get a row of lines (none: one behind another).
      local lanes, base = nil, nil
      if n > 1 then lanes, base = M.lanes(P, o) end
      local width = lanes and #lanes or 1
      local first = o
      if base then
        first = shallow_copy(o)
        first.spi = lanes[base]
      end
      local sub_cmd = shallow_copy(cmd)
      sub_cmd.spawns = { first }
      sub_cmd.wait_time = 0

      if kind == "carrier" then
        local orig_gems = store.gems_per_wave
        store.gems_per_wave = (orig_gems or 0) * mult
        local ok, err = pcall(original, store, sub_cmd, ...)
        store.gems_per_wave = orig_gems
        if not ok then error(err) end
      else
        original(store, sub_cmd, ...)
      end

      -- Copy k (1 .. n-1) takes the line base+k of the row, wrapping; a row spawns together.
      local row, row_lanes = 0, {}
      for k = 1, n - 1 do
        if store.force_next_wave then break end
        local k_row = math.floor(k / width)
        if k_row ~= row then
          if #row_lanes > 0 then spawn_row(original, store, cmd, o, row_lanes, ...) end
          row, row_lanes = k_row, {}
          if U and U.y_wait then
            U.y_wait(store, M.EXTRA_SPACING, function(st) return st.force_next_wave end)
          end
          if store.force_next_wave then break end
        end
        row_lanes[#row_lanes + 1] = base and lanes[((base - 1 + k) % width) + 1] or false
      end
      if #row_lanes > 0 and not store.force_next_wave then
        spawn_row(original, store, cmd, o, row_lanes, ...)
      end
    end
  end
end

-- Wrap systems.wave_spawn_tsv.cmd_fns.spawn once.
function M.install(K, ctx)
  if K then
    K.enemy_acc = {}
  end

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
