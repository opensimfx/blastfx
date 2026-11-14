"""Deterministic pre-bake Mantaflow domain envelope calculation."""

from __future__ import annotations


def build_domain_envelope(physical, profile) -> dict:
    """Return simulation-space bounds for the complete planned event.

    The envelope is a fixed shape in fireball radii (profile ``envelope_*_R``).
    Under Froude scaling a blast of any size fills the same fraction of it,
    so the voxel size and solver time scale follow from the radius alone.
    """
    radius = max(float(physical.characteristic_radius_m), 1e-6)
    lateral = radius * float(profile.envelope_lateral_R)
    min_z = -radius * float(profile.envelope_bottom_R)
    max_z = radius * float(profile.envelope_top_R)
    return {
        "min": (-lateral, -lateral, min_z),
        "max": (lateral, lateral, max_z),
        "size": (lateral * 2.0, lateral * 2.0, max_z - min_z),
        "center": (0.0, 0.0, (min_z + max_z) * 0.5),
        "adaptive_domain_enabled": False,
        "boundary_top_open": True,
        "boundary_sides_open": True,
    }


def longest_side(envelope: dict) -> float:
    """Longest domain side in metres: Mantaflow's FLUID_DOMAIN_SIZE."""
    return max(float(value) for value in envelope["size"])


def envelope_state(envelope: dict) -> dict:
    """Return only deterministic envelope inputs for cache identity."""
    return {
        "min": tuple(round(float(value), 9) for value in envelope["min"]),
        "max": tuple(round(float(value), 9) for value in envelope["max"]),
        "size": tuple(round(float(value), 9) for value in envelope["size"]),
        "adaptive_domain_enabled": bool(envelope["adaptive_domain_enabled"]),
        "boundary_top_open": bool(envelope["boundary_top_open"]),
        "boundary_sides_open": bool(envelope["boundary_sides_open"]),
    }
