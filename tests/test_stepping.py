import pytest

from krmod.model.stepping import (
    ENEMY_VALUES,
    clamp_troop,
    parse_number,
    parse_pct,
    snap_enemy,
    step_cell,
    step_enemy,
    step_pct,
    step_troop,
)


@pytest.mark.parametrize(
    ("current", "original", "direction", "shift", "expected"),
    [
        (150, 150, 1, False, 151),
        (0.8, 0.8, 1, False, 0.9),
        (0.15, 0.15, -1, False, 0.14),
        (0.15, 0.15, 1, True, 0.25),
        (150, 150, -1, True, 140),
        (152.5, 150, 1, False, 153.5),
        (0.07, 0.07, 1, False, 0.08),
    ],
)
def test_step_cell_uses_smallest_digit_of_original(current, original, direction, shift, expected):
    assert step_cell(current, original, direction, shift) == expected


def test_step_cell_stops_at_zero_but_leaves_typed_negatives_alone():
    assert step_cell(0.5, 3, -1) == 0
    assert step_cell(0, 3, -1) == 0
    assert step_cell(-5, 3, 1) == -4
    assert step_cell(-5, 3, -1) == -6


def test_step_pct_bounds_and_mixed():
    assert step_pct(None, 1) == 101
    assert step_pct(None, -1, shift=True) == 90
    assert step_pct(103.3, 1) == 104.3
    assert step_pct(0, -1) == 0
    assert step_pct(495, 1, shift=True) == 500


@pytest.mark.parametrize(("text", "pct"), [("150", 150), (" 150 % ", 150), ("99.55", 99.6), ("900", 500), ("-3", 0)])
def test_parse_pct(text, pct):
    assert parse_pct(text) == pct


@pytest.mark.parametrize("text", ["", "abc", "1_5", "١٥٠", "%", "inf", "nan"])
def test_parse_rejects_non_numbers(text):
    with pytest.raises(ValueError):
        parse_pct(text)
    with pytest.raises(ValueError):
        parse_number(text)


def test_enemy_values_and_steps():
    assert ENEMY_VALUES == (0.25, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert step_enemy(0.25, 1) == 1
    assert step_enemy(1, -1) == 0.25
    assert step_enemy(0.25, -1) == 0.25
    assert step_enemy(10, 1) == 10
    assert snap_enemy(1.5) == 2
    assert snap_enemy(0.5) == 0.25
    assert snap_enemy(0.7) == 1
    assert snap_enemy(42) == 10


def test_troop_whole_numbers_and_bounds():
    assert clamp_troop(1.5) == 2
    assert clamp_troop(-1.5) == -2
    assert clamp_troop(2.4) == 2
    assert clamp_troop(-30) == -10
    assert step_troop(10, 1) == 10
    assert step_troop(-10, -1) == -10
    assert step_troop(0, -1) == -1
