import sys
from pathlib import Path

# Pure-Python physics tests can be run without Blender once the package
# dependencies are kept isolated from bpy.

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blastfx.core.physics import (
    PhysicalConfig,
    derive_physics,
    effective_scale_m,
    nuclear_scale_m,
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


def test_nuclear_scale_follows_cinematic_cube_root():
    # 15 kt -> ~173 m diameter (70 m per kt^(1/3), 8x compression).
    assert nuclear_scale_m(15.0) == 70.0 * 15.0 ** (1.0 / 3.0)
    assert nuclear_scale_m(1.0) == 70.0
    grows = [nuclear_scale_m(kt) for kt in (1.0, 15.0, 100.0)]
    assert grows == sorted(grows)


def test_effective_scale_honors_nuclear_yield_only():
    class FakeProps:
        explosion_type = "NUCLEAR"
        yield_kt = 15.0
        scale = 1.0

    assert effective_scale_m(FakeProps()) == 70.0 * 15.0 ** (1.0 / 3.0)

    class YieldZero(FakeProps):
        yield_kt = 0.0

    assert effective_scale_m(YieldZero()) == 1.0

    class Conventional(FakeProps):
        explosion_type = "FUEL"

    assert effective_scale_m(Conventional()) == 1.0
