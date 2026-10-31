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
    for explosion_type in ("GROUND", "FUEL", "CUSTOM", "AIRBURST", "NUCLEAR"):
        profile = profile_for(explosion_type)
        assert profile.dust_temperature <= -1.0
    # The big ground-surge profile hugs hardest (strongest cool air).
    assert profile_for("LARGE").dust_temperature <= profile_for("FUEL").dust_temperature


def test_nuclear_profile_is_a_long_ground_burst():
    profile = profile_for("NUCLEAR")

    # Trinity-style: surge + column, shock inside the 5-psi relation
    # (~3.7x fireball radius -> factor stays below that of HEAVY's 8.0),
    # fireball skin visible for the first seconds of a 14-16 s ring.
    assert profile.ground_surge is True
    assert profile.stem is True
    assert profile.burst_flip_lower is True
    assert profile.shockwave_radius_factor < profile_for("HEAVY").shockwave_radius_factor
    emission, lifetime, active = profile.burst_timing(24.0)
    assert (emission, lifetime, active) == (48, 80, 129)
    # Overrides are fps-independent by design.
    assert profile.burst_timing(60.0)[:2] == (48, 80)


def test_nuclear_shading_used_for_nuclear_type():
    from blastfx.core.explosion_profile import shading_for

    config = shading_for("NUCLEAR")
    # Near-white incandescent flash, grey fallout column.
    assert config.flame_color[:3] == (1.0, 0.88, 0.62)
    assert config.density_multiplier == 0.30
    # Light thin end, near-black dense core — same ramp sanity.
    positions = [position for position, _color in config.smoke_ramp]
    assert positions == sorted(positions)
    assert sum(config.smoke_ramp[-1][1][:3]) < sum(config.smoke_ramp[0][1][:3])
