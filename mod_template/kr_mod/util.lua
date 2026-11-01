-- Shared helpers for the KrGenesis loader. Loaded with dofile at every level start.
local M = {}

M.log_path = nil

-- Truncate the log and remember where later lines go.
function M.log_open(path)
  M.log_path = path
  local f = io.open(path, "w")
  if f then f:close() end
end

-- Append one line. Never raises.
function M.log(line)
  if not M.log_path then return end
  local ok, f = pcall(io.open, M.log_path, "a")
  if ok and f then
    pcall(f.write, f, tostring(line), "\n")
    f:close()
  end
end

-- Read a data file that must return a plain table. Runs with an empty environment.
-- Returns the table, or nil and a message (missing, unparsable, raised, wrong type).
function M.load_table(path)
  local chunk, err = loadfile(path)
  if not chunk then return nil, err end
  setfenv(chunk, {})
  local ok, result = pcall(chunk)
  if not ok then return nil, tostring(result) end
  if type(result) ~= "table" then return nil, "file did not return a table: " .. path end
  return result
end

-- Load kr_mod/<name>.lua and return its module table, or nil and a message.
function M.load_module(base, name)
  local ok, result = pcall(dofile, base .. "/mods/kr_mod/" .. name .. ".lua")
  if not ok then return nil, tostring(result) end
  if type(result) ~= "table" then return nil, "module " .. name .. " did not return a table" end
  return result
end

return M
