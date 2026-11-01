import pytest

from krmod.gamedata.luart import LuaError


def test_run_returns_result(lua):
    assert lua.run("return 1 + 1", want_result=True) == b"2"


def test_syntax_error_raises(lua):
    with pytest.raises(LuaError, match="near"):
        lua.run("return (")


def test_bytecode_with_nul_loads(lua):
    blob = lua.run("return string.dump(function() return 42 end)", want_result=True)
    assert b"\x00" in blob
    lua.run(blob, "=dumped")  # must not raise
