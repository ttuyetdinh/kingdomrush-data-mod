"""Test entry point for NiceGUI user simulation."""
import dataclasses
import tempfile
from pathlib import Path

from nicegui import core, ui

from krmod.gamedata.reader import read_balance
from krmod.model.grouping import GroupIndex
from krmod.paths import GamePaths
from krmod.profiles import ProfileStore
from krmod.state import AppState
from krmod.ui.main import build_page

# Reset NiceGUI core state so ui.page works under user_simulation:
core.reset()

paths = GamePaths.locate()
# Use isolated test profiles and mods directories:
_test_profiles = Path(tempfile.mkdtemp(prefix="krmod-ui-test-profiles-"))
_test_mods = Path(tempfile.mkdtemp(prefix="krmod-ui-test-mods-"))
_test_repo = Path(tempfile.mkdtemp(prefix="krmod-ui-test-repo-"))  # settings.json lives here
paths = dataclasses.replace(paths, profiles_dir=_test_profiles, mods_dir=_test_mods)

tree = read_balance(paths)
index = GroupIndex.build(tree)
store = ProfileStore(paths.profiles_dir)
state = AppState(paths, tree, index, store)

build_page(state, None, repo_dir=_test_repo)
ui.run()
