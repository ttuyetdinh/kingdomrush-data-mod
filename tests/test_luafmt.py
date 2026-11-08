import pytest

from krmod.modgen.luafmt import to_lua


def test_to_lua():
    assert to_lua({"a": 1, "b": [1.5, 'x"y'], 3: True}) == '{ a = 1, b = { 1.5, "x\\"y" }, [3] = true }'
    with pytest.raises(ValueError):
        to_lua(float("nan"))


def test_non_finite_rejected_anywhere():
    for bad in (float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            to_lua({"x": [bad]})


def test_scalars_and_escapes():
    assert to_lua(False) == "false"
    assert to_lua(7) == "7"
    assert to_lua(0.25) == "0.25"
    assert to_lua("a\\b\nc\rd\0e") == '"a\\\\b\\nc\\rd\\000e"'


def test_keys_and_containers():
    assert to_lua({"not an id": 1, "end": 2, "_ok1": 3}) == '{ ["not an id"] = 1, ["end"] = 2, _ok1 = 3 }'
    assert to_lua((1, 2)) == "{ 1, 2 }"
    assert to_lua({}) == "{}"
    assert to_lua([]) == "{}"
    with pytest.raises(TypeError):
        to_lua(object())
