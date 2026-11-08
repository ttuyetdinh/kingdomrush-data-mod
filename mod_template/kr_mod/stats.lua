-- Finds the balance table on the call stack and applies data-file changes to it.
local M = {}

local function dotted(p)
  local parts = {}
  for i = 1, #p do parts[i] = tostring(p[i]) end
  return table.concat(parts, ".")
end

-- The game keeps the balance table in a local named "balance" of the function that
-- requires the override module. Walk the stack to find it.
function M.find_balance()
  for level = 2, 12 do
    local info = debug.getinfo(level, "S")
    if not info then break end
    local i = 1
    while true do
      local name, value = debug.getlocal(level, i)
      if not name then break end
      if name == "balance" and type(value) == "table" and value.towers then
        return value, info.source
      end
      i = i + 1
    end
  end
  return nil
end

-- Walk path p inside root; returns the parent table and the last key, or nil when a
-- step is not a table.
local function parent_of(root, p)
  local cur = root
  for i = 1, #p - 1 do
    if type(cur) ~= "table" then return nil end
    cur = cur[p[i]]
  end
  if type(cur) ~= "table" then return nil end
  return cur, p[#p]
end

-- Undo the previous level's changes, then apply `changes` ({ p = path, v = number }).
-- K.originals maps dotted path -> { p = path, v = original }.
-- Returns applied (count) and missing (list of dotted paths).
function M.apply(balance, changes, K)
  for _, o in pairs(K.originals) do
    local parent, key = parent_of(balance, o.p)
    if parent and type(parent[key]) == "number" then parent[key] = o.v end
  end
  K.originals = {}

  local applied, missing = 0, {}
  for _, c in ipairs(changes or {}) do
    local p = type(c) == "table" and c.p
    if type(p) ~= "table" or #p == 0 then
      missing[#missing + 1] = "(invalid change)"
    else
      local label = dotted(p)
      local parent, key = parent_of(balance, p)
      if not parent or type(parent[key]) ~= "number" or type(c.v) ~= "number" then
        missing[#missing + 1] = label
      else
        if K.originals[label] == nil then K.originals[label] = { p = p, v = parent[key] } end
        parent[key] = c.v
        applied = applied + 1
      end
    end
  end
  return applied, missing
end

return M
