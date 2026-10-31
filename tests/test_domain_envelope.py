from dataclasses import dataclass

from blastfx.core.domain_envelope import build_domain_envelope, envelope_state


@dataclass
class Physical:
    characteristic_radius_m: float = 0.5
    characteristic_velocity_mps: float = 3.0
    buoyancy_strength: float = 1.0


@dataclass
class Numerical:
    voxel_size_m: float = 0.03


def test_domain_envelope_is_deterministic_and_exceeds_legacy_bounds():
    first = build_domain_envelope(Physical(), Numerical(), 9.80665, 8.0)
    second = build_domain_envelope(Physical(), Numerical(), 9.80665, 8.0)

    assert first == second
    assert first["size"][0] > 3.0
    assert first["size"][2] > 6.0
    assert envelope_state(first) == envelope_state(second)


def test_domain_envelope_changes_with_timeline():
    short = build_domain_envelope(Physical(), Numerical(), 9.80665, 2.0)
    long = build_domain_envelope(Physical(), Numerical(), 9.80665, 8.0)

    assert long["size"][0] > short["size"][0]
    assert long["size"][2] > short["size"][2]
    assert envelope_state(long) != envelope_state(short)
