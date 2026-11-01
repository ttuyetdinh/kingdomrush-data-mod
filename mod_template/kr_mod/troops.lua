-- Troop count multiplier for KrGenesis.
-- Scales max_soldiers on barracks templates and live tower entities.
local M = {}

local current_ctx = nil
local last_mult = nil

local function write_log(K, line)
  local log_fn
  if current_ctx and type(current_ctx.log) == "function" then
    log_fn = current_ctx.log
  elseif type(K) == "table" and K._troops_ctx and type(K._troops_ctx.log) == "function" then
    log_fn = K._troops_ctx.log
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
  end
end

return M
