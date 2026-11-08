-- Troop count multiplier for KrGenesis.
-- Scales max_soldiers on barracks templates and live tower entities.
local M = {}

local current_ctx = nil
local last_mult = nil

local function write_log(K, line)
  local log_fn
  if type(K) == "table" and K._troops_ctx and type(K._troops_ctx.log) == "function" then
    log_fn = K._troops_ctx.log
  elseif current_ctx and type(current_ctx.log) == "function" then
    log_fn = current_ctx.log
  end
  if log_fn then
    pcall(log_fn, line)
  end
end

-- Scale max_soldiers in a barrack table by mult.
-- Returns changed: boolean.
function M.apply_barrack(b, mult)
  if type(b) ~= "table" or type(mult) ~= "number" then return false end
  local changed = false

  if type(b.max_soldiers) == "number" then
    if b._kr_applied == nil or b.max_soldiers ~= b._kr_applied then
      b._kr_base = b.max_soldiers
    end
    if type(b._kr_base) == "number" then
      local want = math.max(1, math.floor(b._kr_base * mult + 0.5))
      if b.max_soldiers ~= want then
        changed = true
      end
      b.max_soldiers = want
      b._kr_applied = want
    end
  elseif type(b.max_soldiers) == "table" then
    if type(b._kr_base_t) ~= "table" then b._kr_base_t = {} end
    if type(b._kr_applied_t) ~= "table" then b._kr_applied_t = {} end
    for i, v in pairs(b.max_soldiers) do
      if type(i) == "number" and type(v) == "number" then
        if b._kr_applied_t[i] == nil or v ~= b._kr_applied_t[i] then
          b._kr_base_t[i] = v
        end
        local base = b._kr_base_t[i]
        if type(base) == "number" then
          local want = math.max(1, math.floor(base * mult + 0.5))
          if b.max_soldiers[i] ~= want then
            changed = true
          end
          b.max_soldiers[i] = want
          b._kr_applied_t[i] = want
        end
      end
    end
  end

  return changed
end

-- Walk templates and live entities, applying K.live.troop_mult to each barrack.
-- Logs "troops x<m>: <n> barracks" when the multiplier changes.
-- Returns count of barrack tables touched.
function M.apply_all(K)
  K = K or KRMOD
  local mult = 1
  if type(K) == "table" and type(K.live) == "table" and type(K.live.troop_mult) == "number" then
    mult = K.live.troop_mult
  end

  local count = 0

  -- 1. Walk templates: require("entity_db").entities
  local ok_edb, edb = pcall(require, "entity_db")
  if ok_edb then
    if type(edb) == "table" and type(edb.entities) == "table" then
      for _, t in pairs(edb.entities) do
        if type(t) == "table" and type(t.barrack) == "table" then
          local ok, err = pcall(M.apply_barrack, t.barrack, mult)
          if ok then
            count = count + 1
          else
            write_log(K, "error troops: " .. tostring(err))
          end
        end
      end
    end
  else
    write_log(K, "error troops: " .. tostring(edb))
  end

  -- 2. Walk live entities: game.store.entities
  if type(game) == "table" and type(game.store) == "table" and type(game.store.entities) == "table" then
    for _, t in pairs(game.store.entities) do
      if type(t) == "table" and type(t.barrack) == "table" then
        local ok, err = pcall(M.apply_barrack, t.barrack, mult)
        if ok then
          count = count + 1
        else
          write_log(K, "error troops: " .. tostring(err))
        end
      end
    end
  end

  -- 3. Log if multiplier changed since last log
  local prev_mult = nil
  if type(K) == "table" and K._troops_last_mult ~= nil then
    prev_mult = K._troops_last_mult
  else
    prev_mult = last_mult
  end

  if mult ~= prev_mult then
    write_log(K, "troops x" .. tostring(mult) .. ": " .. tostring(count) .. " barracks")
    last_mult = mult
    if type(K) == "table" then
      K._troops_last_mult = mult
    end
  end

  return count
end

-- The stage 11 camp tower's insert script writes the vanilla per-level soldier count
-- into every personal camp barrack. When that value equals the one this module applied
-- at the previous level, apply_barrack cannot tell it is a game rewrite and would keep
-- the old scaled number. So wrap the insert: after the original runs, forget the applied
-- marker on those barracks and apply the current multiplier right away.
local function camp_cleanup(K, this, store)
  if type(this) ~= "table" or type(store) ~= "table" or type(store.entities) ~= "table" then
    return
  end
  local mult = 1
  if type(K) == "table" and type(K.live) == "table" and type(K.live.troop_mult) == "number" then
    mult = K.live.troop_mult
  end
  for _, e in pairs(store.entities) do
    if type(e) == "table" and e.template_name == this.barracks_t and type(e.barrack) == "table" then
      e.barrack._kr_applied = nil
      e.barrack._kr_applied_t = nil
      M.apply_barrack(e.barrack, mult)
    end
  end
end

-- Wrap scripts.tower_stage_11_camp.insert once. K._troops_wrapped (weak keys, kept in
-- the persistent KRMOD table) remembers our wrappers across level reloads.
local function wrap_camp_insert(K)
  local scripts = package.loaded["scripts_game"]
  local camp = type(scripts) == "table" and scripts.tower_stage_11_camp or nil
  if type(camp) ~= "table" or type(camp.insert) ~= "function" then
    write_log(K, "error troops: stage 11 camp hook not found")
    return
  end
  if type(K._troops_wrapped) ~= "table" then
    K._troops_wrapped = setmetatable({}, { __mode = "k" })
  end
  local original = camp.insert
  if K._troops_wrapped[original] then return end

  local function finish(this, store, ...)
    local ok, err = pcall(camp_cleanup, K, this, store)
    if not ok then write_log(K, "error troops camp: " .. tostring(err)) end
    return ...
  end
  local function wrapper(this, store, ...)
    return finish(this, store, original(this, store, ...))
  end
  K._troops_wrapped[wrapper] = true
  camp.insert = wrapper
end

-- Install module hooks and register poller.
function M.install(K, ctx)
  current_ctx = ctx
  last_mult = nil
  if type(K) == "table" then
    K.installed = K.installed or {}
    K.installed.troops = true
    K._troops_ctx = ctx
    K._troops_last_mult = nil
    K.pollers = K.pollers or {}
    K.pollers.troops = M.apply_all
    local ok, err = pcall(wrap_camp_insert, K)
    if not ok then write_log(K, "error troops: " .. tostring(err)) end
  end
end

return M
