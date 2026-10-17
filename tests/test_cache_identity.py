from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blastfx.core.physical_state import state_hash


def test_cache_identity_changes_when_simulation_state_changes():
    base = {
        "blast_id": "abc123",
        "speed": 1.0,
        "frame_end": 120,
        "numerical": {"domain_resolution": 128, "noise_upres": 2},
    }
    changed = {
        **base,
        "numerical": {"domain_resolution": 256, "noise_upres": 2},
    }

    assert state_hash(base) != state_hash(changed)


def test_cache_identity_is_order_independent():
    first = {"speed": 1.0, "seed": 4, "components": {"fireball": True}}
    second = {"components": {"fireball": True}, "seed": 4, "speed": 1.0}

    assert state_hash(first) == state_hash(second)


def test_cache_identity_changes_when_domain_envelope_changes():
    first = {"domain_envelope": {"size": (4.5, 4.5, 11.0)}}
    second = {"domain_envelope": {"size": (4.5, 4.5, 12.0)}}

    assert state_hash(first) != state_hash(second)


def test_cache_identity_changes_when_profile_changes():
    import dataclasses

    from blastfx.core.explosion_profile import profile_for

    profile = profile_for("LARGE")
    base = {"explosion_profile": dataclasses.asdict(profile)}
    changed = {"explosion_profile": dataclasses.asdict(
        dataclasses.replace(profile, source_radius=profile.source_radius + 0.5)
    )}

    assert state_hash(base) != state_hash(changed)
