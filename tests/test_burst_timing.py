from blastfx.core.explosion_profile import PROFILES


def test_burst_timing_windows_follow_expert_benchmarks():
    # Iridesium benchmark: emitter on 1-5 frames, short-lived particles
    # (start 10 -> end 14-15, life 5-7 at 24 fps).
    emission, lifetime, total = PROFILES["FUEL"].burst_timing(24.0)
    assert emission == 5
    assert lifetime == 9
    assert total == emission + lifetime + 1

    # Fast blast: at least 2 emission frames, lifespan floor of 3 frames.
    emission_g, lifetime_g, total_g = PROFILES["GROUND"].burst_timing(24.0)
    assert emission_g == 2
    assert lifetime_g >= 3
    assert total_g > emission_g

    # However long the fuel blast is scheduled for, the injector window
    # never exceeds the 5-frame expert ceiling.
    for profile in PROFILES.values():
        for fps in (12.0, 24.0, 30.0, 60.0):
            emission, lifetime, total = profile.burst_timing(fps)
            assert 2 <= emission <= 5
            assert lifetime >= 3
            assert total == emission + lifetime + 1
