import pytest

from krmod.gamedata.luart import LuaRuntime
from krmod.gamedata.reader import read_balance
from krmod.paths import GameNotFoundError, GamePaths


@pytest.fixture(scope="session")
def game_paths():
    try:
        return GamePaths.locate()
    except GameNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def tree(game_paths):
    return read_balance(game_paths)


@pytest.fixture
def lua(game_paths):
    with LuaRuntime(game_paths.lua_dll) as runtime:
        yield runtime
