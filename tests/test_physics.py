import sys
from pathlib import Path

# Pure-Python physics tests can be run without Blender once the package
# dependencies are kept isolated from bpy.

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blastfx.core.physics import (
    PhysicalConfig,
    derive_physics,
    seconds_to_frames,
    validate_physical_config,
)


def test_physics_derivation():
    config = PhysicalConfig(
        scale_m=10.0,
        reference_energy=1.0,
        intensity=2.0,
        duration_s=5.0,
    )

    derived = derive_physics(config)

    assert derived.characteristic_radius_m == 5.0
    assert derived.characteristic_time_s == 5.0
    assert derived.characteristic_velocity_mps == 1.0


def test_frame_conversion_is_fps_aware():
    assert seconds_to_frames(1.0, 24.0) == 24.0
    assert seconds_to_frames(1.0, 30.0) == 30.0


def test_invalid_config():
    config = PhysicalConfig(
        scale_m=-1.0,
        reference_energy=0.0,
        intensity=1.0,
        duration_s=1.0,
    )
    assert validate_physical_config(config)
