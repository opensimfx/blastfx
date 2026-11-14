import pytest

from blastfx.core.explosion_profile import PROFILES, profile_for
from blastfx.core.froude import time_unit


def test_burst_windows_are_event_times_in_frames():
    fuel = profile_for("FUEL")
    T = time_unit(5.0, 9.81)
    emission, lifetime, total = fuel.burst_frames(T, 1.0, 24.0)
    assert emission == round(fuel.burst_emission_T * T * 24.0)
    assert lifetime == round(fuel.burst_lifetime_T * T * 24.0)
    assert total == emission + lifetime + 1


def test_slow_motion_and_fps_stretch_windows_together():
    fuel = profile_for("FUEL")
    T = time_unit(20.0, 9.81)
    base = fuel.burst_frames(T, 1.0, 24.0)
    slow = fuel.burst_frames(T, 0.5, 24.0)
    fast_fps = fuel.burst_frames(T, 1.0, 48.0)
    assert slow[:2] == fast_fps[:2]
    assert slow[0] == pytest.approx(base[0] * 2, abs=1)


def test_tiny_blasts_still_seed_fuel():
    for profile in PROFILES.values():
        emission, lifetime, total = profile.burst_frames(time_unit(0.05, 9.81), 1.0, 24.0)
        assert emission >= 1 and lifetime >= 2
        assert total == emission + lifetime + 1


def test_burst_reach_stays_near_the_fireball():
    # speed x lifetime is the fuel's reach in radii; the fireball should not
    # be sprayed across the whole domain (the old small preset reached ~6 R).
    for name, profile in PROFILES.items():
        reach = profile.burst_speed_U * profile.burst_lifetime_T
        assert reach < profile.envelope_lateral_R, name


def test_ground_surge_traits():
    assert PROFILES["GROUND"].burst_flip_lower
    assert PROFILES["LARGE"].burst_flip_lower
    assert not PROFILES["FUEL"].burst_flip_lower
    heavy = profile_for("HEAVY")
    assert heavy.burst_flip_lower and heavy.ground_surge
    assert heavy.fuel_amount > PROFILES["LARGE"].fuel_amount
