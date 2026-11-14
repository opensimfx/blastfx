import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blastfx.core.explosion_profile import profile_for
from blastfx.core.physics import PhysicalConfig, derive_physics
from blastfx.core import sim_config as _MODULE
from blastfx.core.sim_config import build_simulation_config, resolve_resolution


def _physical(scale=10.0, intensity=1.0, duration=5.0):
    return derive_physics(
        PhysicalConfig(scale_m=scale, reference_energy=1.0, intensity=intensity, duration_s=duration)
    )


def test_quality_changes_resolution_not_physical_values():
    physical = _physical(intensity=2.0)
    draft = build_simulation_config(physical, "DRAFT", 0, 1, 7)
    final = build_simulation_config(physical, "FINAL", 0, 2, 7)

    assert draft.domain_resolution < final.domain_resolution
    assert draft.characteristic_velocity_mps == final.characteristic_velocity_mps
    assert draft.time_scale_multiplier == final.time_scale_multiplier
    assert draft.burst_normal_velocity == final.burst_normal_velocity
    assert draft.seed == final.seed == 7


def test_artist_simulation_controls_reach_derived_configuration():
    config = build_simulation_config(
        _physical(), "PREVIEW", 128, 1, 3,
        turbulence=2.0, smoke_density=2.0, fire_temperature=2.0,
    )
    # Artist turbulence maps into the expert vorticity band (ceiling 0.2).
    assert 0.05 < config.turbulence_strength <= 0.2
    assert config.density_scale == pytest.approx(2.0 * profile_for("FUEL").density)
    assert config.temperature_scale > 2.0


def test_burst_speed_is_froude_scaled_and_profile_driven():
    fuel = profile_for("FUEL")
    small = build_simulation_config(_physical(scale=2.0), "PREVIEW", 0, 1, 7, profile=fuel)
    # 20 m stays under the time-scale clamp (90 m domain -> k ~ 4.7).
    big = build_simulation_config(_physical(scale=20.0), "PREVIEW", 0, 1, 7, profile=fuel)
    assert big.time_scale_multiplier < 10.0
    # Bigger blasts move faster in m/s (U = sqrt(g R))...
    assert big.burst_normal_velocity == pytest.approx(small.burst_normal_velocity * 10.0 ** 0.5)
    assert small.burst_normal_velocity == pytest.approx(
        fuel.burst_speed_U * small.characteristic_velocity_mps
    )
    # ...and the solver sees the same reference-model value at both sizes.
    assert big.burst_normal_velocity * big.particle_velocity_factor == pytest.approx(
        small.burst_normal_velocity * small.particle_velocity_factor
    )


def test_slow_motion_slows_particles_and_solver():
    fuel = profile_for("FUEL")
    real = build_simulation_config(_physical(), "PREVIEW", 0, 1, 7, profile=fuel)
    slow = build_simulation_config(_physical(), "PREVIEW", 0, 1, 7, profile=fuel, playback_speed=0.5)
    assert slow.burst_normal_velocity == pytest.approx(real.burst_normal_velocity * 0.5)
    assert slow.time_scale_multiplier == pytest.approx(real.time_scale_multiplier * 0.5)


def test_auto_resolution_keeps_voxels_per_radius_constant():
    fuel = profile_for("FUEL")
    for scale in (2.0, 20.0, 200.0):
        config = build_simulation_config(_physical(scale=scale), "PREVIEW", 0, 1, 7, profile=fuel)
        voxels_per_radius = (scale / 2.0) / config.voxel_size_m
        assert voxels_per_radius == pytest.approx(_MODULE.VOXELS_PER_RADIUS["PREVIEW"], rel=0.05)


def test_resolution_override_keeps_historical_meaning():
    assert resolve_resolution("PREVIEW", 128, 50.0, 5.0) == 128
    assert resolve_resolution("FINAL", 128, 50.0, 5.0) == 192
    assert resolve_resolution("PREVIEW", 0, 50.0, 5.0) == 140


def test_burst_count_scales_with_quality_to_hero_band():
    large = profile_for("LARGE")
    draft = build_simulation_config(_physical(intensity=2.0), "DRAFT", 0, 1, 7, profile=large)
    preview = build_simulation_config(_physical(intensity=2.0), "PREVIEW", 0, 1, 7, profile=large)
    final = build_simulation_config(_physical(intensity=2.0), "FINAL", 0, 1, 7, profile=large)

    assert draft.burst_count == large.burst_count
    assert preview.burst_count == large.burst_count * 2
    assert final.burst_count == large.burst_count * 4
    # Hero quality stays inside the researched 8-10k band.
    assert 8000 <= final.burst_count <= 10000


def test_draft_has_no_noise_pass_but_final_keeps_it():
    draft = build_simulation_config(_physical(), "DRAFT", 128, 2, 7)
    preview = build_simulation_config(_physical(), "PREVIEW", 128, 2, 7)
    final = build_simulation_config(_physical(), "FINAL", 128, 2, 7)
    assert draft.noise_upres == 1
    assert preview.noise_upres == 2 and final.noise_upres == 2


def test_solver_cost_falls_with_lower_tier_and_never_changes_physics():
    draft = build_simulation_config(_physical(), "DRAFT", 128, 2, 7)
    final = build_simulation_config(_physical(), "FINAL", 128, 2, 7)
    assert draft.adapt_margin < final.adapt_margin
    assert draft.additional_res <= final.additional_res
    assert draft.timesteps_max <= final.timesteps_max
    assert 1 <= draft.timesteps_min <= draft.timesteps_max
    assert draft.characteristic_velocity_mps == final.characteristic_velocity_mps
    assert draft.burst_normal_velocity == final.burst_normal_velocity


def test_unknown_tier_falls_back_to_preview_settings():
    assert _MODULE.tier_solver("nope") == _MODULE.TIER_SOLVER["PREVIEW"]


def test_huge_blast_reports_buoyancy_shortfall():
    nuclear = profile_for("NUCLEAR")
    config = build_simulation_config(_physical(scale=172.0), "PREVIEW", 0, 1, 7, profile=nuclear)
    assert config.time_scale_multiplier == pytest.approx(10.0)
    assert config.buoyancy_heat == pytest.approx(5.0)
    assert config.buoyancy_shortfall > 0.0


def test_smoke_fade_follows_blast_not_shot_length():
    fuel = profile_for("FUEL")
    short = build_simulation_config(_physical(duration=2.0), "PREVIEW", 0, 1, 7, profile=fuel, timeline_duration_s=2.0)
    long = build_simulation_config(_physical(duration=30.0), "PREVIEW", 0, 1, 7, profile=fuel, timeline_duration_s=30.0)
    assert short.dissolve_speed == long.dissolve_speed


def test_rates_hold_per_T_across_sizes():
    from blastfx.core.froude import solver_scaling
    from blastfx.core.domain_envelope import build_domain_envelope, longest_side

    fuel = profile_for("FUEL")
    for scale in (4.0, 40.0):
        physical = _physical(scale=scale)
        config = build_simulation_config(physical, "PREVIEW", 0, 1, 7, profile=fuel)
        scaling = solver_scaling(longest_side(build_domain_envelope(physical, fuel)))
        burned_per_T = config.burning_rate * scaling.solver_seconds_per_T(physical.time_unit_s)
        if scale == 4.0:
            reference = burned_per_T
    assert burned_per_T == pytest.approx(reference)


def test_zero_duration_means_natural_event_length():
    from types import SimpleNamespace as NS
    from blastfx.core.blast_plan import plan_blast
    from blastfx.core.froude import time_unit

    scene = NS(gravity=NS(length=9.80665), render=NS(fps=24, fps_base=1.0))
    base = dict(explosion_type="FUEL", preset_id="medium", scale=10.0, intensity=1.0, speed=0.5,
                duration=0.0, reference_energy=1.0, yield_kt=0.0, quality="DRAFT", resolution=0,
                noise_upres=1, seed=1, turbulence=1.0, smoke_density=1.0, fire_temperature=1.0,
                start_frame=1)
    plan = plan_blast(NS(**base), scene)
    expected = profile_for("FUEL").event_T * time_unit(5.0, 9.80665)
    assert plan.physical.characteristic_time_s == pytest.approx(expected)
    # Slow motion stretches the frame count, not the event.
    assert plan.frame_end - plan.frame_start == round(expected / 0.5 * 24)


def test_adaptive_domain_is_off_by_default():
    # Its moving box clipped rising smoke into horizontal bands (measured).
    assert build_simulation_config(_physical(), "FINAL", 0, 2, 7).use_adaptive_domain is False
