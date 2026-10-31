from blastfx.core.explosion_profile import PROFILES


def test_burst_timing_windows_follow_expert_benchmarks():
    # Burn-matrix tuned: fireball visibility scales with blast size —
    # GROUND ≈ 1.5-2 s, FUEL ≈ 3 s (matrix variant B), LARGE ≈ 5 s
    # (variant D scaled), HEAVY (long ground-burn, big preset).
    # (Derived-only windows still respect the Iridesium 2-5 frame ceiling.)
    emission, lifetime, total = PROFILES["FUEL"].burst_timing(24.0)
    assert emission == 24
    assert lifetime == 28
    assert total == emission + lifetime + 1

    emission_g, lifetime_g, total_g = PROFILES["GROUND"].burst_timing(24.0)
    assert (emission_g, lifetime_g) == (6, 14)
    assert total_g > emission_g
    # Flip is a ground-surge trait only.
    assert PROFILES["GROUND"].burst_flip_lower
    assert PROFILES["LARGE"].burst_flip_lower
    assert not PROFILES["FUEL"].burst_flip_lower

    # However long the fuel blast is scheduled for, derived injectors never
    # exceed the 5-frame expert ceiling; explicit overrides (e.g. HEAVY's
    # long ground-burn windows) are fps-independent and exact.
    for profile in PROFILES.values():
        for fps in (12.0, 24.0, 30.0, 60.0):
            emission, lifetime, total = profile.burst_timing(fps)
            if profile.burst_emission_frames > 0:
                assert emission == profile.burst_emission_frames
            else:
                assert 2 <= emission <= 5
            if profile.burst_lifetime_frames > 0:
                assert lifetime == profile.burst_lifetime_frames
            else:
                assert lifetime >= 3
            assert total == emission + lifetime + 1


def test_heavy_long_fire_windows():
    # Heavy ground bursts burn 1-3 s (vs 2-5 s airbursts): ~1.5 s of fuel
    # injection at 24 fps -> 36 emission frames, 40-frame particle life.
    from blastfx.core.explosion_profile import profile_for

    heavy = profile_for("HEAVY")
    emission, lifetime, total = heavy.burst_timing(24.0)
    assert (emission, lifetime, total) == (36, 40, 77)
    assert heavy.burst_flip_lower and heavy.ground_surge
    assert heavy.fuel_amount > PROFILES["LARGE"].fuel_amount


def test_burst_timing_overrides_bypass_duration_derivation():
    import dataclasses

    tuned = dataclasses.replace(
        PROFILES["GROUND"], burst_emission_frames=0, burst_lifetime_frames=0
    )
    # Zero overrides fall back to derived, fps-scaled windows ≤ 5 frames.
    for fps in (24.0, 60.0):
        emission, lifetime, total = tuned.burst_timing(fps)
        assert 2 <= emission <= 5
        assert lifetime >= 3
        assert total == emission + lifetime + 1
    # Explicit frame counts are fps-independent.
    assert PROFILES["LARGE"].burst_timing(24.0)[0] == 36
    assert PROFILES["LARGE"].burst_timing(60.0)[0] == 36
