-- KrGenesis enemy count multiplier module.
-- Wraps systems.wave_spawn_tsv.cmd_fns.spawn to scale wave spawns by KRMOD.live.enemy_mult, and
-- scales the wave's waits by KRMOD.live.group_gap (see M.paced).
-- Extra copies walk side by side: each row fills the road's lines (the original's line first),
-- and the next row follows EXTRA_SPACING seconds later.
--
-- Every road of the game has 3 rails: 1 in the middle, 2 and 3 on the edges (about 40 px
-- apart). A row has more lines the more enemies there are (lines_for): 2 to 7, GAP of the road
-- apart. Rows of 2 and 3 lines are the game's rails; wider rows reach past the edges, but only
-- over walkable ground of the level's grid: where the ground beside the road is not walkable,
-- the row narrows there. Lines other than the game's rails are rails the mod adds to every
-- road of the level when copies first need them. Their keys are far above 3 so #P.paths[pi]
-- stays 3: the game's own "random rail" picks and loops never see them. Only rows walk on
-- them: the copies, and an original that has copies (one on a rail outside the row, or on a
-- random rail, joins its row on a random line).
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

-- Lines per row for an Enemies multiplier: more enemies, more lines (shorter waves).
function M.lines_for(mult)
  if mult >= 70 then return 7 end
  if mult >= 50 then return 6 end
  if mult >= 30 then return 5 end
  if mult >= 10 then return 4 end
  if mult >= 5 then return 3 end
  return 2
end

-- Gap between neighbouring lines of a row, as a share of the road's width (rail 2 to rail 3,
-- about 40 px, so about 16 px).
M.GAP = 0.4

-- How far a row of `lines` lines reaches, in road half-widths from the middle: at least the
-- road's edges (1), so 2 and 3 lines are the game's rails; wider rows keep GAP between lines.
function M.spread(lines)
  return math.max(1, M.GAP * (lines - 1))
end

-- The rails of a row of `lines` lines, left to right, with each one's place across the road
-- (1 = rail 2's edge, 0 = the middle rail, -1 = rail 3's edge; beyond 1 = past the edge). The
-- game's rails serve where a line sits exactly on one; other lines get the key
-- 100 + 10 * lines + i, so rows of different sizes never share one.
function M.row_rails(lines)
  local row = {}
  local spread = M.spread(lines)
  for i = 0, lines - 1 do
    local u = 1 - 2 * i / (lines - 1)
    local key
    if u == 0 then
      key = 1
    elseif spread == 1 and u == 1 then
      key = 2
    elseif spread == 1 and u == -1 then
      key = 3
    else
      key = 100 + 10 * lines + i
    end
    row[#row + 1] = { key = key, t = u * spread }
  end
  return row
end

local WALK_MASK = 255 + 256 -- TERRAIN_TYPES_MASK + TERRAIN_NOWALK
local NOWALK = 256

-- Terrain of the level grid at x, y (the game's grid_db lookup, without its error log for
-- points off the grid), or nil without a grid.
local function cell(GR, x, y)
  if type(GR) ~= "table" or type(GR.grid) ~= "table" then return nil end
  local size = GR.cell_size or 16
  local col = GR.grid[math.ceil((x - (GR.ox or 0)) / size)]
  return type(col) == "table" and col[math.ceil((y - (GR.oy or 0)) / size)] or 0
end

-- How many road half-widths a row may reach on one side at each node (1 to `spread`): past the
-- edge only while the grid cell matches the middle's walkable terrain, narrowed to the smallest
-- reach within WIDTH_WINDOW nodes so a row eases in and out of narrow spots.
M.WIDTH_WINDOW = 6
local function reach(GR, mid, edge, spread)
  local raw = {}
  for ni = 1, #mid do
    local c, e = mid[ni], edge[ni]
    local dx, dy = e.x - c.x, e.y - c.y
    local half = math.sqrt(dx * dx + dy * dy)
    local base = cell(GR, c.x, c.y)
    local r = 1
    if spread > 1 and half > 0 and base and base ~= 0 and bit.band(base, NOWALK) == 0 then
      base = bit.band(base, WALK_MASK)
      local need = (spread - 1) * half
      local function walkable(d)
        return bit.band(cell(GR, e.x + dx / half * d, e.y + dy / half * d), WALK_MASK) == base
      end
      -- walk out in 2 px steps, then check the full reach itself (need is rarely a whole step)
      local walked, s = 0, 2
      while s < need and walkable(s) do
        walked, s = s, s + 2
      end
      if s >= need and walkable(need) then walked = need end
      r = 1 + walked / half
    end
    raw[ni] = r
  end
  local out = {}
  for ni = 1, #raw do
    local r = raw[ni]
    for k = math.max(1, ni - M.WIDTH_WINDOW), math.min(#raw, ni + M.WIDTH_WINDOW) do
      if raw[k] < r then r = raw[k] end
    end
    out[ni] = r
  end
  return out
end

-- Add the rails of a row of `lines` lines to every road of P, once per level (P.paths is a new
-- table each level) and row size. All or nothing: an enemy keeps its rail number when it walks
-- onto the next road, so every road needs them. Returns the row's rail keys, left to right, or
-- nil when the roads cannot have them.
function M.add_rails(P, lines, GR)
  local paths = type(P) == "table" and P.paths or nil
  if type(paths) ~= "table" or #paths == 0 then return nil end
  local row = M.row_rails(lines)
  local keys = {}
  for i, rail in ipairs(row) do keys[i] = rail.key end
  if M._railed ~= paths then M._railed, M._railed_sizes = paths, {} end
  if M._railed_sizes[lines] then return keys end
  for pi = 1, #paths do
    local road = paths[pi]
    if type(road) ~= "table" then return nil end
    local n = node_count(road[1])
    if n == 0 or node_count(road[2]) ~= n or node_count(road[3]) ~= n then return nil end
  end
  local spread = M.spread(lines)
  for pi = 1, #paths do
    local mid, left, right = paths[pi][1], paths[pi][2], paths[pi][3]
    local reach_left = reach(GR, mid, left, spread)
    local reach_right = reach(GR, mid, right, spread)
    for _, rail in ipairs(row) do
      if rail.key > 3 then
        local edge, side, f = left, reach_left, rail.t
        if f < 0 then edge, side, f = right, reach_right, -f end
        local nodes = {}
        for ni = 1, #mid do
          -- the row's outer line sits at this node's reach; the others keep even gaps
          local k = f * side[ni] / spread
          local c, e = mid[ni], edge[ni]
          nodes[ni] = { x = c.x + (e.x - c.x) * k, y = c.y + (e.y - c.y) * k }
        end
        paths[pi][rail.key] = nodes
      end
    end
  end
  M._railed_sizes[lines] = true
  return keys
end

-- The lines of one row (left to right) for an entry, and the index of the line the original
-- takes. On roads with the game's 3 rails: a row of `lines` lines (see add_rails; GR is the
-- level grid, without it rows stay within the road); an original on a rail outside the row, or
-- on "*", takes a random line. Otherwise the road's rails 1..n, "*" picking one as the game
-- would. An unknown rail gives no row: copies then spawn one behind another on the original's
-- rail.
function M.lanes(P, o, lines, GR)
  local road = type(P) == "table" and type(P.paths) == "table" and P.paths[o.pi] or nil
  local rails = type(road) == "table" and #road or 1
  if rails < 1 then rails = 1 end
  local spi = o.spi
  if spi ~= "*" and (type(spi) ~= "number" or spi < 1 or spi > rails or spi ~= math.floor(spi)) then
    return nil, nil
  end
  local row = rails == 3 and M.add_rails(P, lines or 4, GR) or nil
  if not row then
    row = {}
    for i = 1, rails do row[i] = i end
  end
  for i, lane in ipairs(row) do
    if lane == spi then return row, i end
  end
  return row, math.random(#row)
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

  local GR = nil
  local ok_g, gdb = pcall(require, "grid_db")
  if ok_g then GR = gdb end

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
      if n > 1 then lanes, base = M.lanes(P, o, M.lines_for(mult), GR) end
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

-- The wave file's waits (each spawn row's wait before it, and wait rows) in percent of the
-- game's: K.live.group_gap. Read on every command, so a change applies from the next one. The
-- wave command's countdown to the next wave is not touched. Returns cmd or a scaled copy (the
-- wave data itself is never changed).
function M.paced(K, cmd)
  local gap = K and type(K.live) == "table" and K.live.group_gap or 100
  if type(gap) ~= "number" or gap == 100 or type(cmd) ~= "table" then return cmd end
  local wait_time = cmd.wait_time
  if type(wait_time) ~= "number" or wait_time <= 0 then return cmd end
  local paced = shallow_copy(cmd)
  paced.wait_time = wait_time * gap / 100
  return paced
end

-- Wrap systems.wave_spawn_tsv.cmd_fns.spawn (and .wait) once.
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

  local cmd_fns = systems.wave_spawn_tsv.cmd_fns
  local original = cmd_fns.spawn

  cmd_fns.spawn = function(store, cmd, ...)
    cmd = M.paced(K, cmd)
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

  local original_wait = cmd_fns.wait
  if type(original_wait) == "function" then
    cmd_fns.wait = function(store, cmd, ...)
      return original_wait(store, M.paced(K, cmd), ...)
    end
  end
end

return M
