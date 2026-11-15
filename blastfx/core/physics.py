from dataclasses import dataclass
import math

from .froude import time_unit, velocity_unit


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
    # Event length the shot covers (real seconds, before slow motion).
    characteristic_time_s: float
    # Froude velocity scale U = sqrt(g*R) (see core.froude).
    characteristic_velocity_mps: float
    buoyancy_strength: float
    normalized_temperature: float
    intensity: float
    # Froude time scale T = sqrt(R/g).
    time_unit_s: float = 0.0


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

    # The user duration is the event length the shot covers; gravity's own
    # time scale is only a floor so a sub-frame request stays solvable.
    gravity_time = math.sqrt(max(radius, 1e-9) / max(config.ambient.gravity, 1e-9))
    requested_time = max(config.duration_s, 1e-4)
    time_s = max(requested_time, gravity_time * 0.25)

    # Speeds come from Froude scaling (U = sqrt(g*R)), not from r/t: how fast
    # a fireball moves depends on its size, not on how long the shot is.
    # (reference_energy is kept as an artistic, cache-identity input only.)
    velocity = velocity_unit(radius, config.ambient.gravity)

    buoyancy = max(0.0, intensity) * min(5.0, radius / max(config.ambient.gravity * time_s**2, 1e-9))
    normalized_temperature = min(10.0, 1.0 + intensity)

    return DerivedPhysics(
        characteristic_radius_m=radius,
        characteristic_time_s=time_s,
        characteristic_velocity_mps=velocity,
        buoyancy_strength=buoyancy,
        normalized_temperature=normalized_temperature,
        intensity=intensity,
        time_unit_s=time_unit(radius, config.ambient.gravity),
    )


def nuclear_scale_m(yield_kt: float) -> float:
    """Cinematic nuclear fireball diameter (m) for a yield in kilotons.

    Real fireball diameters scale ~560 m per kt^(1/3) (cube-root law,
    Glasstone & Dolan); compressed 8x to 70 m per kt^(1/3) so a 15 kt
    burst reads ~173 m wide instead of filling several shots.
    """
    kt = max(float(yield_kt), 1e-6)
    return 70.0 * kt ** (1.0 / 3.0)


def effective_scale_m(props) -> float:
    """Nuclear yield drives the diameter; other types use the manual scale."""
    if getattr(props, "explosion_type", "") == "NUCLEAR":
        yield_kt = float(getattr(props, "yield_kt", 0.0) or 0.0)
        if yield_kt > 0:
            return nuclear_scale_m(yield_kt)
    return float(props.scale)


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
