"""Minimal ctypes binding to the game's own lua51.dll (x64 LuaJIT)."""
from __future__ import annotations

import ctypes
from pathlib import Path

LUA_GLOBALSINDEX = -10002
LUA_MULTRET = -1


class LuaError(RuntimeError):
    pass


class LuaRuntime:
    def __init__(self, dll_path: Path):
        lib = ctypes.CDLL(str(dll_path))
        vp, i, sz = ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t
        cp = ctypes.c_char_p
        for name, argtypes, restype in (
            ("luaL_newstate", [], vp),
            ("luaL_openlibs", [vp], None),
            ("luaL_loadbuffer", [vp, cp, sz, cp], i),
            ("lua_pcall", [vp, i, i, i], i),
            ("lua_tolstring", [vp, i, ctypes.POINTER(sz)], vp),
            ("lua_settop", [vp, i], None),
            ("lua_gettop", [vp], i),
            ("lua_pushlstring", [vp, cp, sz], None),
            ("lua_setfield", [vp, i, cp], None),
            ("lua_close", [vp], None),
        ):
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = argtypes, restype
        self._lib = lib
        self._state = lib.luaL_newstate()
        if not self._state:
            raise LuaError("luaL_newstate failed")
        lib.luaL_openlibs(self._state)

    def __enter__(self) -> LuaRuntime:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._state:
            self._lib.lua_close(self._state)
            self._state = None

    def _top_string(self) -> bytes:
        """Return the value at stack top as bytes; messages of a failed call are strings."""
        size = ctypes.c_size_t()
        ptr = self._lib.lua_tolstring(self._state, -1, ctypes.byref(size))
        return b"" if not ptr else ctypes.string_at(ptr, size.value)

    def run(self, code: bytes | str, chunkname: str = "=chunk", want_result: bool = False) -> bytes | None:
        if self._state is None:
            raise LuaError("runtime is closed")
        data = code.encode("utf-8") if isinstance(code, str) else code
        lib, state = self._lib, self._state
        top = lib.lua_gettop(state)
        try:
            status = lib.luaL_loadbuffer(state, data, len(data), chunkname.encode("utf-8"))
            if status == 0:
                status = lib.lua_pcall(state, 0, 1 if want_result else 0, 0)
            if status != 0:
                raise LuaError(self._top_string().decode("utf-8", "replace"))
            return self._top_string() if want_result else None
        finally:
            lib.lua_settop(state, top)

    def set_global_string(self, name: str, value: str) -> None:
        self.set_global_bytes(name, value.encode("utf-8"))

    def set_global_bytes(self, name: str, raw: bytes) -> None:
        if self._state is None:
            raise LuaError("runtime is closed")
        self._lib.lua_pushlstring(self._state, raw, len(raw))
        self._lib.lua_setfield(self._state, LUA_GLOBALSINDEX, name.encode("utf-8"))
