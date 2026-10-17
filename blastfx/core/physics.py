from dataclasses import dataclass
import math


@dataclass(frozen=True)
class AmbientConditions:
    gravity: float = 9.80665
    air_density: float = 1.225
    ambient_temperature_k: float = 288.15


@dataclass(frozen=True)
class PhysicalConfig:
    scale_m: float
    reference_energy: float
    intensity: float
    duration_s: float
    ambient: AmbientConditions = AmbientConditions()


@dataclass(frozen=True)
class DerivedPhysics:
    characteristic_radius_m: float
    characteristic_time_s: float
    characteristic_velocity_mps: float
    buoyancy_strength: float
    normalized_temperature: float
    intensity: float


def gravity_magnitude(value) -> float:
    """Convert Blender scalar/vector gravity representations to m/s² magnitude."""
    try:
        return float(value.length)
    except AttributeError:
        return float(value)


def derive_physics(config: PhysicalConfig) -> DerivedPhysics:
    """Derive dimensionally coherent VFX scales.

    This intentionally stops short of predicting weapon effects or damage.
    Reference energy is a normalized artistic/solver control, while length,
    time, velocity, gravity and buoyancy remain expressed in SI units.
    """
    radius = max(config.scale_m * 0.5, 1e-6)
    intensity = max(config.intensity, 0.0)

    # Characteristic event time combines user duration with a gravity time scale.
    # The user duration remains authoritative; gravity supplies a physically
    # meaningful reference rather than changing the requested shot timing.
    gravity_time = math.sqrt(max(radius, 1e-9) / max(config.ambient.gravity, 1e-9))
    requested_time = max(config.duration_s, 1e-4)
    time_s = max(requested_time, gravity_time * 0.25)

    # Energy-density-inspired velocity scale, bounded to avoid singular behavior
    # at tiny reference energies. The floor is a numerical guard (1e-6), not a
    # physical minimum, so the scale stays proportional to radius/time_s across
    # all explosion sizes. (Previously 0.1 m/s absolute floor broke scale
    # invariance for small blasts.)
    energy_scale = max(config.reference_energy, 1e-9)
    velocity_energy = math.sqrt(2.0 * energy_scale / max(config.ambient.air_density * radius**3, 1e-9))
    velocity = min(max(radius / time_s, 1e-6), max(velocity_energy, radius / time_s))

    buoyancy = max(0.0, intensity) * min(5.0, radius / max(config.ambient.gravity * time_s**2, 1e-9))
    normalized_temperature = min(10.0, 1.0 + intensity)

    return DerivedPhysics(
        characteristic_radius_m=radius,
        characteristic_time_s=time_s,
        characteristic_velocity_mps=velocity,
        buoyancy_strength=buoyancy,
        normalized_temperature=normalized_temperature,
        intensity=intensity,
    )


def seconds_to_frames(seconds: float, fps: float, fps_base: float = 1.0) -> float:
    if fps <= 0 or fps_base <= 0:
        raise ValueError("FPS and FPS base must be positive.")
    return seconds * fps / fps_base


def validate_physical_config(config: PhysicalConfig) -> list[str]:
    errors = []
    if config.scale_m <= 0:
        errors.append("Physical scale must be greater than zero.")
    if config.reference_energy < 0:
        errors.append("Reference energy must not be negative.")
    if config.duration_s <= 0:
        errors.append("Physical duration must be greater than zero.")
    if config.ambient.gravity <= 0:
        errors.append("Gravity must be greater than zero.")
    if config.ambient.air_density <= 0:
        errors.append("Air density must be greater than zero.")
    if config.ambient.ambient_temperature_k <= 0:
        errors.append("Ambient temperature must be above absolute zero.")
    return errors
