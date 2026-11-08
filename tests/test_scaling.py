import pytest

from krmod.model.scaling import (
    PCT_MAX,
    PCT_MIN,
    common_pct,
    original_decimals,
    scale,
    warn,
)


def test_pct_bounds():
    assert PCT_MIN == 0.0 and PCT_MAX == 500.0


@pytest.mark.parametrize(
    "orig,pct,out",
    [(70, 50, 35), (75, 133.3, 100), (0.5, 150, 0.75), (1.33, 50, 0.67), (3, 150, 5), (-4, 50, -2)],
)
def test_scale(orig, pct, out):
    assert scale(orig, pct) == out
def test_scale_zero_percent():
    assert scale(70, 0) == 0
    assert scale(0.05, 0) == 0
    assert scale(1.33, 0) == 0


def test_scale_preserves_multi_decimal_precision():
    assert scale(0.002, 50) == 0.001
    assert scale(0.015, 200) == 0.03
    assert scale(1.33, 50) == 0.67
    assert scale(62.400000000000006, 50) == 31.2
    assert scale(1e99, 50) == 5e98


def test_scale_100_returns_original_unchanged():
    for o in (62.400000000000006, 0.3999999999999999, 0.19999999999999996, 70):
        scaled = scale(o, 100)
        assert scaled == o and type(scaled) is type(o)
        assert common_pct([(o, o)]) == 100


def test_common_pct_large_values():
    assert common_pct([(1e99, 1e99)]) == 100


def test_original_decimals():
    assert original_decimals(62.400000000000006) == 1
    assert original_decimals(0.3999999999999999) == 1
    assert original_decimals(0.002) == 3
    assert original_decimals(0.0208) == 4
    assert original_decimals(70.0) == 0
    assert original_decimals(70) == 0

def test_scale_whole_rounds_away_from_zero():
    assert scale(5, 50) == 3
    assert scale(-5, 50) == -3
    assert isinstance(scale(70, 50), float)


def test_common_pct():
    assert common_pct([(70, 35), (110, 55)]) == 50
    assert common_pct([(70, 35), (110, 110)]) is None
    assert common_pct([(0, 5), (70, 140)]) == 200
    assert common_pct([(75, 100), (3, 4)]) == 133.3
    assert common_pct([(0, 0)]) == 100
    assert common_pct([]) == 100


def test_common_pct_recovers_percent_when_levels_round_apart():
    originals = [70, 110, 160, 220]
    for pct in (51, 101, 7):
        pairs = [(o, scale(o, pct)) for o in originals]
        assert common_pct(pairs) == pct
    # the largest level alone would suggest 50.9, which maps 160 to 81 instead of 82:
    assert common_pct([(70, 36), (110, 56), (160, 82), (220, 112)]) == 51
    assert common_pct([(70, 36), (110, 56), (160, 90), (220, 112)]) is None


def test_warn():
    assert warn(("t", "cooldown", 1), 0) and warn(("t", "stun_duration"), 0)
    assert warn(("t", "hp", 1), -1) and warn(("t", "hp", 1), 0) is None
    assert isinstance(warn(("t", "hp", 1), -1), str)
    assert warn(("t", "cooldown", 1), 3) is None
    assert warn(("t", "Cooldown_Time"), 0)
    assert warn(("t", "cooldown", 1), -2)
