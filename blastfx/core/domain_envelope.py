"""Deterministic pre-bake Mantaflow domain envelope calculation."""

from __future__ import annotations


def build_domain_envelope(physical, numerical, gravity: float, duration_s: float, profile=None) -> dict:
    """Return simulation-space bounds for the complete planned event."""
    radius = max(float(physical.characteristic_radius_m), 1e-6)
    velocity = max(float(physical.characteristic_velocity_mps), 0.1)
    duration = max(float(duration_s), 1e-4)
    buoyancy = max(float(physical.buoyancy_strength), 0.0)
    gravity = max(float(gravity), 1e-6)

    margin = max(radius * 0.5, float(numerical.voxel_size_m) * 4.0)
    # Margin is the larger of a radius-proportional term and a numerical
    # safety (a few voxels). The voxel floor is intentionally constant because
    # it represents solver resolution, not physical scale.
    # The initial blast footprint itself needs room before expansion begins.
    # Keep this tied to the characteristic radius, then extend it by velocity.
    expansion_factor = float(getattr(profile, "expansion_factor", 1.0))
    lateral = max(
        radius * 6.0 * expansion_factor,
        radius + velocity * duration * 0.9 * expansion_factor + margin,
    )
    source_radius = radius
    if profile is not None:
        source_radius = max(
            source_radius,
            radius * 1.15 * expansion_factor,
        )
        max_z = radius + velocity * duration
    else:
        max_z = radius + velocity * duration
    buoyant_velocity = (gravity * radius * (1.0 + buoyancy)) ** 0.5
    vertical_rise = velocity * duration + buoyant_velocity * duration * 0.5
    min_z = -source_radius - margin
    max_z = max(max_z, radius + vertical_rise) + margin
    return {
        "min": (-lateral, -lateral, min_z),
        "max": (lateral, lateral, max_z),
        "size": (lateral * 2.0, lateral * 2.0, max_z - min_z),
        "center": (0.0, 0.0, (min_z + max_z) * 0.5),
        "adaptive_domain_enabled": True,
        "boundary_top_open": True,
        "boundary_sides_open": True,
        "margin_m": margin,
        "duration_s": duration,
        "numerical_voxel_size_m": float(numerical.voxel_size_m),
        "profile_expansion_factor": expansion_factor,
    }


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
