"""Reads the original balance values by running the game's own Lua files."""
from __future__ import annotations

import zipfile

from krmod.gamedata.luart import LuaError, LuaRuntime
from krmod.model.values import BalanceTree, KeyPath, Leaf
from krmod.paths import GamePaths

CONSTANTS_ENTRY = "all/constants.lua"
BALANCE_ENTRY = "kr6/data/balance/balance.lua"

# Walks KRMOD_BALANCE and returns one string. Tab separated lines:
#   num|str|bool <value> <seg>...        a leaf; segments are s:<key> or n:<index>
#   alias <seg>... = <seg>...            a table already reached at another path
#   const <name> <value>                 a DAMAGE_* global number
#   tables <n>                           tables nested under the root, root not counted
# Tab, newline, CR and backslash inside values and keys are backslash escaped.
_WALKER = r"""
local out, visited, count = {}, {}, 0
local function esc(s)
  return (s:gsub("[\\\t\n\r]", function(c)
    if c == "\\" then return "\\\\" elseif c == "\t" then return "\\t"
    elseif c == "\n" then return "\\n" else return "\\r" end
  end))
end
local function num(n) return string.format("%.17g", n) end
local function seg(k)
  if type(k) == "number" then return "n:" .. num(k) end
  if type(k) == "string" then return "s:" .. esc(k) end
  error("unsupported key type " .. type(k))
end
local function walk(t, segs)
  visited[t] = segs
  for k, v in pairs(t) do
    local child = {}
    for i = 1, #segs do child[i] = segs[i] end
    child[#child + 1] = seg(k)
    local tv = type(v)
    if tv == "table" then
      if visited[v] then
        out[#out + 1] = "alias\t" .. table.concat(child, "\t") .. "\t=\t" .. table.concat(visited[v], "\t")
      else
        count = count + 1
        walk(v, child)
      end
    elseif tv == "number" then
      out[#out + 1] = "num\t" .. num(v) .. "\t" .. table.concat(child, "\t")
    elseif tv == "string" then
      out[#out + 1] = "str\t" .. esc(v) .. "\t" .. table.concat(child, "\t")
    elseif tv == "boolean" then
      out[#out + 1] = "bool\t" .. tostring(v) .. "\t" .. table.concat(child, "\t")
    else
      error("unsupported value type " .. tv)
    end
  end
end
if type(KRMOD_BALANCE) ~= "table" then error("balance.lua did not return a table") end
walk(KRMOD_BALANCE, {})
for k, v in pairs(_G) do
  if type(k) == "string" and k:sub(1, 7) == "DAMAGE_" and type(v) == "number" then
    out[#out + 1] = "const\t" .. k .. "\t" .. num(v)
  end
end
out[#out + 1] = "tables\t" .. count
return table.concat(out, "\n")
"""

_LOAD_BALANCE = (
    f'local f, err = loadstring(KRMOD_BALANCE_CODE, "@{BALANCE_ENTRY}")\n'
    "if not f then error(err, 0) end\n"
    "KRMOD_BALANCE = f()\n"
    "KRMOD_BALANCE_CODE = nil\n"
)


class ReaderError(Exception):
    pass


def _unescape(s: str) -> str:
    if "\\" not in s:
        return s
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            i += 1
            c = {"t": "\t", "n": "\n", "r": "\r"}.get(s[i], s[i])
        out.append(c)
        i += 1
    return "".join(out)


def _segment(raw: str) -> str | int:
    kind, _, body = raw.partition(":")
    if kind == "n":
        number = float(body)
        return int(number) if number == int(number) else number
    return _unescape(body)


def _path(raws: list[str]) -> KeyPath:
    return tuple(_segment(r) for r in raws)


def _parse(text: str) -> BalanceTree:
    leaves: dict[KeyPath, Leaf] = {}
    aliases: dict[KeyPath, KeyPath] = {}
    flags: dict[str, int] = {}
    table_count = 0
    for line in text.split("\n"):
        parts = line.split("\t")
        tag = parts[0]
        if tag == "num":
            path = _path(parts[2:])
            leaves[path] = Leaf(path, float(parts[1]), "num")
        elif tag == "str":
            path = _path(parts[2:])
            leaves[path] = Leaf(path, _unescape(parts[1]), "str")
        elif tag == "bool":
            path = _path(parts[2:])
            leaves[path] = Leaf(path, parts[1] == "true", "bool")
        elif tag == "alias":
            split = parts.index("=", 1)
            aliases[_path(parts[1:split])] = _path(parts[split + 1:])
        elif tag == "const":
            flags[parts[1]] = int(float(parts[2]))
        elif tag == "tables":
            table_count = int(parts[1])
        else:
            raise ReaderError(f"unexpected walker line: {line!r}")
    return BalanceTree(leaves, aliases, flags, table_count)


def read_balance(paths: GamePaths) -> BalanceTree:
    entry = CONSTANTS_ENTRY
    try:
        with zipfile.ZipFile(paths.exe) as exe:
            constants = exe.read(CONSTANTS_ENTRY)
            entry = BALANCE_ENTRY
            balance = exe.read(BALANCE_ENTRY)
        with LuaRuntime(paths.lua_dll) as lua:
            entry = CONSTANTS_ENTRY
            lua.run(constants, f"@{CONSTANTS_ENTRY}")
            entry = BALANCE_ENTRY
            lua.set_global_bytes("KRMOD_BALANCE_CODE", balance)
            lua.run(_LOAD_BALANCE, "=load_balance")
            result = lua.run(_WALKER, "=balance_walker", want_result=True)
        return _parse(result.decode("utf-8"))
    except (OSError, KeyError, zipfile.BadZipFile, LuaError, ValueError) as exc:
        raise ReaderError(f"Cannot read {entry} from {paths.exe}: {exc}") from exc
