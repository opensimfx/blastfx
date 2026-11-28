"""Deterministic pre-bake Mantaflow domain envelope calculation."""

from __future__ import annotations


import math

UP = (0.0, 0.0, 1.0)
MAX_TILT_DEG = 75.0          # a blast aimed lower than this mostly drives into the ground
DIRECTED_SHIFT = 0.4         # the envelope moves this share of its half-width toward a tilted blast


def blast_direction(vector) -> tuple[float, float, float]:
    """Unit blast direction, tilted at most MAX_TILT_DEG from straight up; zero or invalid -> straight up."""
    try:
        x, y, z = (float(v) for v in vector)
    except (TypeError, ValueError):
        return UP
    n = math.sqrt(x * x + y * y + z * z)
    if not math.isfinite(n) or n < 1e-9:
        return UP
    x, y, z = x / n, y / n, z / n
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, z))))
    if tilt > MAX_TILT_DEG:
        h = math.hypot(x, y)
        a = math.radians(MAX_TILT_DEG)
        x, y, z = (x / h * math.sin(a), y / h * math.sin(a), math.cos(a)) if h > 1e-9 else UP
    return (round(x, 9), round(y, 9), round(z, 9))


def directed_vector(props):
    """The blast direction when Directed Blast is on, straight up otherwise."""
    return getattr(props, "blast_direction", UP) if getattr(props, "use_directed", False) else UP


def build_domain_envelope(physical, profile, direction=UP) -> dict:
    """Return simulation-space bounds for the complete planned event.

    The envelope is a fixed shape in fireball radii (profile ``envelope_*_R``).
    Under Froude scaling a blast of any size fills the same fraction of it,
    so the voxel size and solver time scale follow from the radius alone.
    """
    radius = max(float(physical.characteristic_radius_m), 1e-6)
    lateral = radius * float(profile.envelope_lateral_R)
    min_z = -radius * float(profile.envelope_bottom_R)
    max_z = radius * float(profile.envelope_top_R)
    # a directed blast drives its fireball sideways: move the envelope that way (zero shift straight up, so
    # undirected blasts keep their envelope and cache identity)
    dx, dy, _ = blast_direction(direction)
    ox, oy = dx * lateral * DIRECTED_SHIFT, dy * lateral * DIRECTED_SHIFT
    ox, oy = (0.0 if abs(ox) < 1e-12 else ox), (0.0 if abs(oy) < 1e-12 else oy)
    return {
        "min": (ox - lateral, oy - lateral, min_z),
        "max": (ox + lateral, oy + lateral, max_z),
        "size": (lateral * 2.0, lateral * 2.0, max_z - min_z),
        "center": (ox, oy, (min_z + max_z) * 0.5),
        "adaptive_domain_enabled": False,
        "boundary_top_open": not bool(getattr(profile, "ceiling", False)),
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
