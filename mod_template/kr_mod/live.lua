-- KrGenesis live controls: speed hotkeys, badge, and live polling.
local M = {}

local function is_valid_mult(m)
  if type(m) ~= "number" then return false end
  if m < 0.5 or m > 3 then return false end
  local m4 = m * 4
  return math.abs(m4 - math.floor(m4 + 0.5)) < 1e-6
end

-- Read and validate mods/kr_mod_live.lua. Returns a clean table or nil.
function M.read_live(path)
  if type(path) ~= "string" then return nil end
  local chunk = loadfile(path)
  if not chunk then return nil end
  setfenv(chunk, {})
  local ok, result = pcall(chunk)
  if not ok or type(result) ~= "table" then return nil end

  local speed = result.speed
  if type(speed) ~= "number" or (speed ~= 1 and speed ~= 2 and speed ~= 3) then
    return nil
  end

  if not is_valid_mult(result.enemy_mult) or not is_valid_mult(result.troop_mult) then
    return nil
  end

  return {
    speed = speed,
    enemy_mult = result.enemy_mult,
    troop_mult = result.troop_mult,
  }
end

-- Poll the live settings file and invoke registered pollers.
function M.poll(K, ctx)
  ctx = ctx or (K and K.ctx)
  local base = (ctx and ctx.base) or (K and K.base) or "."
  local path = base .. "/mods/kr_mod_live.lua"
  local live = M.read_live(path)
  if not live then return end

  if type(K.live) ~= "table" then
    K.live = { speed = 1, enemy_mult = 1, troop_mult = 1 }
  end

  if live.speed ~= K.file_speed then
    K.file_speed = live.speed
    K.live.speed = live.speed
    if game then game.DBG_TIME_MULT = live.speed end
    if ctx and ctx.log then ctx.log("speed x" .. tostring(live.speed)) end
  end

  if live.enemy_mult ~= K.live.enemy_mult then
    if ctx and ctx.log then ctx.log("enemies x" .. tostring(live.enemy_mult)) end
    K.live.enemy_mult = live.enemy_mult
  end

  K.live.troop_mult = live.troop_mult

  if type(K.pollers) == "table" then
    local names = {}
    for name, fn in pairs(K.pollers) do
      if type(fn) == "function" then
        names[#names + 1] = name
      end
    end
    table.sort(names, function(a, b) return tostring(a) < tostring(b) end)
    for _, name in ipairs(names) do
      local fn = K.pollers[name]
      local ok, err = pcall(fn, K)
      if not ok and ctx and ctx.log then
        ctx.log("error poller " .. tostring(name) .. ": " .. tostring(err))
      end
    end
  end
end

-- Install live hooks onto the global game table (guarded by K.installed.live).
function M.install(K, ctx)
  if type(K) ~= "table" then return end
  K.ctx = ctx

  if type(K.live) ~= "table" then
    K.live = { speed = 1, enemy_mult = 1, troop_mult = 1 }
  end
  if type(K.pollers) ~= "table" then
    K.pollers = {}
  end
  if type(K.speed_keys) ~= "table" then
    K.speed_keys = { "f5", "f6", "f7" }
  end

  local live_path = (ctx and ctx.base or K.base or ".") .. "/mods/kr_mod_live.lua"
  local live = M.read_live(live_path)
  if live then
    K.live.speed = live.speed
    K.live.enemy_mult = live.enemy_mult
    K.live.troop_mult = live.troop_mult
    K.file_speed = live.speed
    if game then game.DBG_TIME_MULT = live.speed end
  else
    K.file_speed = K.live.speed or 1
    if game then game.DBG_TIME_MULT = K.file_speed end
  end

  local now = 0
  if love and love.timer and type(love.timer.getTime) == "function" then
    local ok_now, val_now = pcall(love.timer.getTime)
    if ok_now and type(val_now) == "number" then now = val_now end
  end
  K.last_poll = now

  if K.installed.live then return end
  if type(game) ~= "table" then return end
  K.installed.live = true

  local orig_update = game.update
  game.update = function(self, dt, ...)
    if orig_update then
      local ok, err = pcall(orig_update, self, dt, ...)
      if not ok then
        local log_fn = (K and K.ctx and K.ctx.log) or (ctx and ctx.log)
        if log_fn then log_fn("error update: " .. tostring(err)) end
      end
    end
    local ok_poll, err_poll = pcall(function()
      local cur_now = 0
      if love and love.timer and type(love.timer.getTime) == "function" then
        local ok_t, val_t = pcall(love.timer.getTime)
        if ok_t and type(val_t) == "number" then cur_now = val_t end
      end
      if cur_now - (K.last_poll or 0) >= 0.5 then
        K.last_poll = cur_now
        M.poll(K, K.ctx or ctx)
      end
    end)
    if not ok_poll then
      local log_fn = (K and K.ctx and K.ctx.log) or (ctx and ctx.log)
      if log_fn then log_fn("error poll: " .. tostring(err_poll)) end
    end
  end

  local orig_keypressed = game.keypressed
  game.keypressed = function(self, key, isrepeat, ...)
    local k = key
    if k == nil and type(self) == "string" then
      k = self
    end
    local handled = false
    local ok, err = pcall(function()
      local keys = K.speed_keys
      if type(keys) == "table" then
        for i = 1, #keys do
          if k == keys[i] then
            game.DBG_TIME_MULT = i
            K.live.speed = i
            local log_fn = (K and K.ctx and K.ctx.log) or (ctx and ctx.log)
            if log_fn then log_fn("speed x" .. tostring(i)) end
            handled = true
            return
          end
        end
      end
    end)
    if not ok then
      local log_fn = (K and K.ctx and K.ctx.log) or (ctx and ctx.log)
      if log_fn then log_fn("error keypressed: " .. tostring(err)) end
    end
    if handled then return end
    if orig_keypressed then
      return orig_keypressed(self, key, isrepeat, ...)
    end
  end

  local orig_draw = game.draw
  game.draw = function(self, ...)
    if orig_draw then
      local ok, err = pcall(orig_draw, self, ...)
      if not ok then
        local log_fn = (K and K.ctx and K.ctx.log) or (ctx and ctx.log)
        if log_fn then log_fn("error draw: " .. tostring(err)) end
      end
    end
    local ok_badge, err_badge = pcall(function()
      local mult = (self and self.DBG_TIME_MULT) or (game and game.DBG_TIME_MULT)
      if type(mult) == "number" and mult > 1 and love and love.graphics then
        local g = love.graphics
        local text = "x" .. tostring(mult)
        local w = 1920
        if type(g.getWidth) == "function" then
          local ok_w, val_w = pcall(g.getWidth)
          if ok_w and type(val_w) == "number" then w = val_w end
        end
        local x = w - 80
        local y = 12
        local r, gr, b, a
        if type(g.getColor) == "function" then
          local ok_c, cr, cg, cb, ca = pcall(g.getColor)
          if ok_c then r, gr, b, a = cr, cg, cb, ca end
        end
        if type(g.push) == "function" then pcall(g.push) end
        if type(g.origin) == "function" then pcall(g.origin) end
        if type(g.setColor) == "function" then pcall(g.setColor, 1, 1, 1, 1) end
        if type(g.print) == "function" then pcall(g.print, text, x, y) end
        if type(g.setColor) == "function" and r ~= nil then pcall(g.setColor, r, gr, b, a) end
        if type(g.pop) == "function" then pcall(g.pop) end
      end
    end)
    if not ok_badge then
      local log_fn = (K and K.ctx and K.ctx.log) or (ctx and ctx.log)
      if log_fn then log_fn("error badge: " .. tostring(err_badge)) end
    end
  end
end

return M
