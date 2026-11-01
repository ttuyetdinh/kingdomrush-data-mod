import pytest

from krmod.model.scaling import (
    PCT_MAX,
    PCT_MIN,
    c2_range,
    common_pct,
    pct_to_track,
    scale,
    track_to_pct,
    warn,
)


def test_pct_bounds():
    assert PCT_MIN == 50.0 and PCT_MAX == 300.0


@pytest.mark.parametrize("t,p", [(0, 50), (0.25, 75), (0.5, 100), (0.75, 200), (1, 300)])
def test_track_mapping(t, p):
    assert track_to_pct(t) == p and pct_to_track(p) == t


@pytest.mark.parametrize("t", [0.0, 0.1, 0.125, 0.3, 0.5, 0.6, 0.875, 1.0])
def test_track_round_trip(t):
    assert pct_to_track(track_to_pct(t)) == pytest.approx(t)


@pytest.mark.parametrize(
    "orig,pct,out",
    [(70, 50, 35), (75, 133.3, 100), (0.5, 150, 0.75), (1.33, 50, 0.67), (3, 150, 5), (-4, 50, -2)],
)
def test_scale(orig, pct, out):
    assert scale(orig, pct) == out


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


def test_c2_range():
    assert c2_range([1, 2]) == (0, 10) and c2_range([70, 110]) == (0, 330)
    assert c2_range([-200, 5]) == (0, 600)
    assert c2_range([]) == (0, 10)


def test_warn():
    assert warn(("t", "cooldown", 1), 0) and warn(("t", "stun_duration"), 0)
    assert warn(("t", "hp", 1), -1) and warn(("t", "hp", 1), 0) is None
    assert isinstance(warn(("t", "hp", 1), -1), str)
    assert warn(("t", "cooldown", 1), 3) is None
    assert warn(("t", "Cooldown_Time"), 0)
    assert warn(("t", "cooldown", 1), -2)
