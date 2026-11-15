from blastfx.core.explosion_profile import profile_for, profile_state


def test_profiles_have_distinct_source_and_timing():
    small = profile_for("GROUND")
    fuel = profile_for("FUEL")
    ground = profile_for("LARGE")

    assert len({p.burst_speed_U for p in (small, fuel, ground)}) == 2
    assert len({p.event_T for p in (small, fuel, ground)}) == 3
    assert len({p.envelope_top_R for p in (small, fuel, ground)}) == 3


def test_profile_state_is_deterministic_and_complete():
    first = profile_state(profile_for("LARGE"))
    second = profile_state(profile_for("LARGE"))

    assert first == second
    assert {"source_radius", "burning_rate", "burst_speed_U", "envelope_top_R"} <= set(first)


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
    # Fire is hot at the core and colour-mapped by temperature.
    low, high = config.fire_temperature_k
    assert 600.0 <= low < high <= 8000.0
    assert config.fire_brightness > 1.0 and config.optical_depth > 1.0
    # Dense soot still scatters a little so the fire can light it.
    assert min(min(color[:3]) for _p, color in config.smoke_ramp) >= 0.03


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
    # Compact, smooth fireball: the burst's fuel reach (speed x lifetime)
    # stays within about one radius (2.6 U for 1.1 T spread it to ~3 R and
    # rendered a spiky urchin), and it burns out well before the shot ends.
    assert profile.burst_speed_U * profile.burst_lifetime_T <= 1.0
    assert profile.burst_random_U <= 0.5
    # The cap needs headroom under the closed top; the ground burst needs no
    # room below ground.
    assert profile.ceiling is True
    assert profile.envelope_top_R >= 7.0
    assert profile.envelope_bottom_R <= 0.5


def test_nuclear_airburst_keeps_room_below_the_burst():
    ground = profile_for("NUCLEAR", "nuclear_groundburst")
    air = profile_for("NUCLEAR", "nuclear_airburst")
    assert ground == profile_for("NUCLEAR")
    assert air.envelope_bottom_R >= 1.5
    # A full sphere: the lower half bursts downward, not up like a ground burst.
    assert air.burst_flip_lower is False
    # Same domain height, so the solver scaling (and its shortfall) match.
    assert air.envelope_top_R + air.envelope_bottom_R == ground.envelope_top_R + ground.envelope_bottom_R
    # Everything else is the shared nuclear profile.
    assert air.burst_speed_U == ground.burst_speed_U and air.fuel_amount == ground.fuel_amount


def test_nuclear_shading_used_for_nuclear_type():
    from blastfx.core.explosion_profile import shading_for

    config = shading_for("NUCLEAR")
    # Near-white incandescent core: hotter than any conventional profile.
    assert config.fire_temperature_k[1] > max(
        shading_for(t).fire_temperature_k[1] for t in ("GROUND", "FUEL", "LARGE", "HEAVY")
    )
    # Light thin end, near-black dense core — same ramp sanity.
    positions = [position for position, _color in config.smoke_ramp]
    assert positions == sorted(positions)
    assert sum(config.smoke_ramp[-1][1][:3]) < sum(config.smoke_ramp[0][1][:3])


def test_every_profile_has_its_own_shading():
    from blastfx.core.explosion_profile import PROFILES, SHADING

    assert set(PROFILES) <= set(SHADING)
    for config in SHADING.values():
        assert config.fire_light_T > 0.0
        assert 0.0 <= config.anisotropy < 1.0
