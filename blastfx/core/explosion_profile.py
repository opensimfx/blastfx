"""Physically informed, deterministic VFX profiles for each explosion type."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExplosionProfile:
    source_radius: float
    source_duration: float
    fuel_amount: float
    temperature: float
    density: float
    velocity_factor: float
    velocity_random: float
    burning_rate: float
    flame_vorticity: float
    flame_smoke: float
    buoyancy_density: float
    buoyancy_heat: float
    turbulence: float
    noise_strength: float
    noise_scale: int
    smoke_dissipation: float
    expansion_factor: float
    fireball: bool = True
    stem: bool = False
    ground_surge: bool = False
    shockwave_delay: float = 0.0
    shockwave_radius_factor: float = 3.0
    shockwave_end_fraction: float = 1.0
    camera_distance_factor: float = 1.0
    dust_duration_factor: float = 0.35
    dust_density_factor: float = 2.0
    dust_velocity_random: float = 0.65
    dust_velocity_normal_factor: float = 0.30


PROFILES = {
    "GROUND": ExplosionProfile(
        0.72, 0.10, 0.75, 1.15, 0.95, 1.5, 0.32, 1.15, 0.38, 1.25,
        1.0, 1.1, 1.05, 0.8, 1, 0.8, 1.15, ground_surge=True, shockwave_delay=0.12,
        camera_distance_factor=2.0,
    ),
    "FUEL": ExplosionProfile(
        1.0, 1.25, 2.5, 1.35, 1.25, 1.15, 0.6, 0.32, 0.78, 2.25,
        1.15, 1.35, 1.45, 1.2, 2, 2.2, 1.4, shockwave_delay=0.18,
        camera_distance_factor=2.2,
    ),
    "LARGE": ExplosionProfile(
        1.45, 0.56, 1.45, 1.2, 1.55, 1.08, 0.48, 0.65, 0.62, 2.7,
        1.3, 1.55, 1.65, 1.4, 2, 2.8, 1.9, stem=True, ground_surge=True,
        shockwave_delay=0.16, shockwave_radius_factor=6.0,
        camera_distance_factor=2.5,
        dust_duration_factor=0.85, dust_density_factor=0.8,
        dust_velocity_random=0.25, dust_velocity_normal_factor=0.12,
    ),
}


def profile_for(explosion_type: str) -> ExplosionProfile:
    """Return the stable profile for a Blender explosion type."""
    return PROFILES.get(explosion_type, PROFILES["FUEL"])


def profile_state(profile: ExplosionProfile) -> dict:
    """Return profile values suitable for the existing cache identity."""
    return asdict(profile)