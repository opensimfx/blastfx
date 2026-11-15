"""Froude scaling: the conversions measured in Blender 5.2.3 (docs/VALIDATION.md section 1.1)."""
import math

import pytest

from blastfx.core.froude import (
    MAX_BUOYANCY,
    MAX_TIME_SCALE,
    REFERENCE_DOMAIN_M,
    solver_scaling,
    time_unit,
    velocity_unit,
)


def test_units_multiply_to_radius():
    for radius in (0.5, 5.0, 86.0):
        assert velocity_unit(radius, 9.81) * time_unit(radius, 9.81) == pytest.approx(radius)


def test_reference_domain_runs_at_real_time():
    scaling = solver_scaling(REFERENCE_DOMAIN_M)
    assert scaling.time_scale == pytest.approx(1.0)
    assert scaling.buoyancy_gain == pytest.approx(1.0)
    assert scaling.flow_velocity(3.0) == pytest.approx(3.0)


def test_time_scale_is_sqrt_of_size_ratio():
    # The probe: a 40 m domain at sqrt(10) matched the 4 m reference.
    scaling = solver_scaling(40.0)
    assert scaling.time_scale == pytest.approx(math.sqrt(10.0))
    assert scaling.particle_velocity_factor == pytest.approx(1.0 / math.sqrt(10.0))
    assert scaling.buoyancy_gain == pytest.approx(1.0)


def test_slow_motion_folds_into_time_scale():
    real = solver_scaling(16.0, 1.0)
    slow = solver_scaling(16.0, 0.5)
    assert slow.time_scale == pytest.approx(real.time_scale * 0.5)
    # Particles fly slower through the scene...
    assert slow.scene_velocity(10.0) == pytest.approx(5.0)
    # ...but the solver sees the same reference-model velocity.
    assert slow.flow_velocity(10.0) == pytest.approx(real.flow_velocity(10.0))
    # And shots stretch into more frames.
    assert slow.scene_frames(1.0, 24.0) == pytest.approx(48.0)


def test_clamped_time_scale_is_made_up_with_buoyancy():
    scaling = solver_scaling(REFERENCE_DOMAIN_M * 400.0)  # ideal 20
    assert scaling.time_scale == MAX_TIME_SCALE
    assert scaling.buoyancy_gain == pytest.approx(4.0)
    assert scaling.buoyancy(1.0) == pytest.approx(4.0)
    assert scaling.buoyancy(3.0) == MAX_BUOYANCY
    assert scaling.buoyancy_shortfall(3.0) == pytest.approx(1.0 - 5.0 / 12.0)
    assert scaling.buoyancy_shortfall(1.0) == 0.0


def test_normal_velocity_converts_to_grid_units():
    # Calibrated: vn = v * res / (2.5 * size) matched velocity_coord exactly.
    scaling = solver_scaling(REFERENCE_DOMAIN_M)
    voxel = 4.0 / 32
    assert scaling.flow_normal_velocity(1.6, voxel) == pytest.approx(5.12)
    assert scaling.flow_normal_velocity(1.6, voxel / 2) == pytest.approx(10.24)


def test_dissolve_compensates_time_scale():
    assert solver_scaling(REFERENCE_DOMAIN_M).dissolve_frames(60) == 60
    assert solver_scaling(REFERENCE_DOMAIN_M * 4).dissolve_frames(60) == 120
