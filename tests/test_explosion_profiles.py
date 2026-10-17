from blastfx.core.explosion_profile import profile_for, profile_state


def test_profiles_have_distinct_source_and_timing():
    small = profile_for("GROUND")
    fuel = profile_for("FUEL")
    ground = profile_for("LARGE")

    assert len({p.source_radius for p in (small, fuel, ground)}) == 3
    assert len({p.source_duration for p in (small, fuel, ground)}) == 3


def test_profile_state_is_deterministic_and_complete():
    first = profile_state(profile_for("LARGE"))
    second = profile_state(profile_for("LARGE"))

    assert first == second
    assert {"source_radius", "burning_rate", "expansion_factor"} <= set(first)
