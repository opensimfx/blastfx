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
