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


def test_shading_configs_are_deterministic_and_sane():
    from blastfx.core.explosion_profile import shading_for

    config = shading_for("FUEL")
    again = shading_for("CUSTOM")  # unknown types fall back to FUEL
    assert config == again
    assert shading_for("FUEL").as_dict() == shading_for("FUEL").as_dict()

    # Ramp positions ascending, colors valid rgba tuples.
    positions = [position for position, _color in config.smoke_ramp]
    assert positions == sorted(positions)
    assert all(len(color) == 4 for _position, color in config.smoke_ramp)
    # Thin end is lighter than the dense core end.
    assert sum(config.smoke_ramp[0][1][:3]) > sum(config.smoke_ramp[-1][1][:3])
    # Flame-grid fire drives emission; blackbody stays off by default.
    assert config.flame_multiplier > 1.0
    assert config.blackbody_intensity == 0.0
    assert 0.0 < config.density_multiplier <= 1.0


def test_dust_profiles_use_negative_cool_ground_temperature():
    for explosion_type in ("GROUND", "FUEL", "CUSTOM", "AIRBURST"):
        profile = profile_for(explosion_type)
        assert profile.dust_temperature <= -1.0
    # The big ground-surge profile hugs hardest (strongest cool air).
    assert profile_for("LARGE").dust_temperature <= profile_for("FUEL").dust_temperature
