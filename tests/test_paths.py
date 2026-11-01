import json
from pathlib import Path

import pytest

import krmod
from krmod.paths import (
    GameNotFoundError,
    GamePaths,
    load_game_dir_setting,
    save_game_dir_setting,
    validate_game_dir,
)


def test_locate_finds_game(game_paths):
    assert game_paths.exe.name == "Kingdom Rush Genesis.exe"
    assert game_paths.mods_dir == game_paths.game_dir / "mods"
    assert game_paths.repo_dir == Path(krmod.__file__).resolve().parents[1]


def test_locate_missing_exe(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    repo = tmp_path / "kingdomrush-data-mod"
    repo.mkdir()
    with pytest.raises(GameNotFoundError, match="Kingdom Rush Genesis.exe"):
        GamePaths.locate(repo)


def _fake_game(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Kingdom Rush Genesis.exe").write_bytes(b"x")
    (folder / "lua51.dll").write_bytes(b"x")
    return folder


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("KRMOD_GAME_DIR", raising=False)
    repo = tmp_path / "game" / "kingdomrush-data-mod"
    repo.mkdir(parents=True)
    return repo


def test_default_is_repo_parent(repo):
    _fake_game(repo.parent)
    assert GamePaths.locate(repo).game_dir == repo.parent


def test_setting_beats_repo_parent(repo, tmp_path):
    _fake_game(repo.parent)
    chosen = _fake_game(tmp_path / "other")
    save_game_dir_setting(repo, chosen)
    assert GamePaths.locate(repo).game_dir == chosen.resolve()


def test_env_beats_setting(repo, tmp_path, monkeypatch):
    saved = _fake_game(tmp_path / "saved")
    from_env = _fake_game(tmp_path / "from_env")
    save_game_dir_setting(repo, saved)
    monkeypatch.setenv("KRMOD_GAME_DIR", str(from_env))
    assert GamePaths.locate(repo).game_dir == from_env


def test_saved_setting_is_found_by_locate_and_written_as_json(repo, tmp_path):
    chosen = _fake_game(tmp_path / "chosen")
    save_game_dir_setting(repo, chosen)
    data = json.loads((repo / "settings.json").read_text(encoding="utf-8"))
    assert data == {"game_dir": str(chosen.resolve())}
    assert load_game_dir_setting(repo) == chosen.resolve()
    paths = GamePaths.locate(repo)
    assert paths.game_dir == chosen.resolve()
    assert paths.mods_dir == chosen.resolve() / "mods"
    assert paths.repo_dir == repo


@pytest.mark.parametrize(
    "content",
    ["{ not json", "[]", "{}", '{"game_dir": 5}', '{"game_dir": ""}', '{"game_dir": null}'],
)
def test_corrupt_settings_mean_no_setting(repo, content):
    (repo / "settings.json").write_text(content, encoding="utf-8")
    assert load_game_dir_setting(repo) is None
    with pytest.raises(GameNotFoundError):
        GamePaths.locate(repo)  # falls through to repo.parent, which is no game folder


def test_missing_settings_mean_no_setting(repo):
    assert load_game_dir_setting(repo) is None


def test_saved_but_invalid_folder_reports_it(repo, tmp_path):
    _fake_game(repo.parent)
    (repo / "settings.json").write_text(
        json.dumps({"game_dir": str(tmp_path / "moved")}), encoding="utf-8"
    )
    with pytest.raises(GameNotFoundError, match="moved"):
        GamePaths.locate(repo)


def test_validate_accepts_complete_folder(tmp_path):
    validate_game_dir(_fake_game(tmp_path / "ok"))


def test_validate_rejects_missing_folder(tmp_path):
    with pytest.raises(GameNotFoundError, match="folder not found"):
        validate_game_dir(tmp_path / "nope")


def test_validate_rejects_missing_exe(tmp_path):
    folder = tmp_path / "g"
    folder.mkdir()
    (folder / "lua51.dll").write_bytes(b"x")
    with pytest.raises(GameNotFoundError, match="Kingdom Rush Genesis.exe"):
        validate_game_dir(folder)


def test_validate_rejects_missing_dll(tmp_path):
    folder = tmp_path / "g"
    folder.mkdir()
    (folder / "Kingdom Rush Genesis.exe").write_bytes(b"x")
    with pytest.raises(GameNotFoundError, match="lua51.dll"):
        validate_game_dir(folder)


def test_portraits_dir_differs_per_game_folder(tmp_path):
    a = GamePaths.for_game_dir(tmp_path / "a", tmp_path / "repo")
    b = GamePaths.for_game_dir(tmp_path / "b", tmp_path / "repo")
    assert a.portraits_dir != b.portraits_dir
    assert a.portraits_dir.parent == b.portraits_dir.parent == tmp_path / "repo" / "cache" / "portraits"
