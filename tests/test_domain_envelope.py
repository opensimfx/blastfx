from dataclasses import dataclass

import pytest

from blastfx.core.domain_envelope import build_domain_envelope, envelope_state, longest_side
from blastfx.core.explosion_profile import PROFILES, profile_for


@dataclass
class Physical:
    characteristic_radius_m: float = 0.5


def test_domain_envelope_is_deterministic():
    first = build_domain_envelope(Physical(), profile_for("FUEL"))
    second = build_domain_envelope(Physical(), profile_for("FUEL"))
    assert first == second
    assert envelope_state(first) == envelope_state(second)


def test_envelope_is_a_fixed_shape_in_radii():
    # Froude similarity: the same profile fills the same fraction of its
    # domain at any size, so the envelope scales exactly with R.
    for profile in PROFILES.values():
        small = build_domain_envelope(Physical(1.0), profile)
        big = build_domain_envelope(Physical(50.0), profile)
        for a, b in zip(small["size"], big["size"]):
            assert b == pytest.approx(a * 50.0)
        assert small["min"][2] < 0.0 < small["max"][2]
        assert longest_side(big) == pytest.approx(longest_side(small) * 50.0)


def test_envelope_identity_changes_with_size():
    a = envelope_state(build_domain_envelope(Physical(1.0), profile_for("LARGE")))
    b = envelope_state(build_domain_envelope(Physical(2.0), profile_for("LARGE")))
    assert a != b


def test_blast_direction_defaults_and_clamp():
    import math
    from blastfx.core.domain_envelope import MAX_TILT_DEG, blast_direction
    assert blast_direction((0, 0, 1)) == (0.0, 0.0, 1.0)
    assert blast_direction((0, 0, 0)) == (0.0, 0.0, 1.0)
    assert blast_direction(None) == (0.0, 0.0, 1.0)
    x, y, z = blast_direction((1, 0, 1))
    assert math.isclose(x, z, rel_tol=1e-6) and y == 0.0
    x, y, z = blast_direction((1, 0, -1))                      # aimed into the ground: tilted back to the limit
    assert math.isclose(math.degrees(math.acos(z)), MAX_TILT_DEG, abs_tol=1e-6) and x > 0


def test_directed_envelope_shifts_only_when_tilted():
    from types import SimpleNamespace
    from blastfx.core.domain_envelope import build_domain_envelope
    phys = SimpleNamespace(characteristic_radius_m=10.0)
    prof = SimpleNamespace(envelope_lateral_R=4.5, envelope_top_R=7.0, envelope_bottom_R=1.0, ceiling=False)
    up = build_domain_envelope(phys, prof)
    assert up == build_domain_envelope(phys, prof, (0, 0, 1))      # identity unchanged for undirected blasts
    side = build_domain_envelope(phys, prof, (1, 0, 1))
    assert side["center"][0] > 0 and side["center"][1] == 0.0
    assert side["size"] == up["size"] and side["min"][2] == up["min"][2]
