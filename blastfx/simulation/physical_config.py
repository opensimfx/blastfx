"""Compatibility shim: the pure configuration lives in core.sim_config."""

from ..core.sim_config import (  # noqa: F401
    AUTO_RESOLUTION_LIMITS,
    TIER_SOLVER,
    VOXELS_PER_RADIUS,
    SimulationConfig,
    build_simulation_config,
    resolve_resolution,
    tier_solver,
)
