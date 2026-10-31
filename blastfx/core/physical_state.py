import hashlib
import json
from dataclasses import asdict
from .physics import gravity_magnitude


def build_physical_state(
    props,
    scene,
    blast_id,
    physical,
    numerical,
    frame_start,
    frame_end,
    domain_envelope=None,
    explosion_profile=None,
):
    """Create the complete identity for a Mantaflow simulation cache.

    Cosmetic-only controls are intentionally excluded. Any value that can
    change emitted fields, solver settings, timing, or cache resolution must
    be represented here so a changed configuration cannot reuse old output.

    ``quality`` and ``numerical`` are deliberately included even though derived
    physics (radius, time, velocity) is quality-independent: a quality or
    solver change must invalidate the cache, so they are part of the identity
    by design (see plan section D). This is a cache identity, not a pure
    physics descriptor.
    """
    return {
        "blast_id": str(blast_id),
        "explosion_type": str(props.explosion_type),
        "preset_id": str(props.preset_id),
        "scale_m": float(props.scale),
        "reference_energy": float(props.reference_energy),
        "intensity": float(props.intensity),
        "duration_s": float(props.duration),
        "speed": float(props.speed),
        "start_frame": int(props.start_frame),
        "frame_start": int(frame_start),
        "frame_end": int(frame_end),
        "component_toggles": {
            "fireball": bool(props.use_fireball),
            "stem": bool(props.use_stem),
            "dust": bool(props.use_dust),
            "shockwave": bool(props.use_shockwave),
            "debris": bool(props.use_debris),
        },
        "turbulence": float(props.turbulence),
        "smoke_density": float(props.smoke_density),
        "fire_temperature": float(props.fire_temperature),
        "gravity": gravity_magnitude(scene.gravity),
        "fps": float(scene.render.fps),
        "fps_base": float(scene.render.fps_base),
        "unit_scale": float(scene.unit_settings.scale_length),
        "addon_version": "0.2.0",
        "blender_version": tuple(__import__("bpy").app.version),
        "seed": int(props.seed),
        "quality": props.quality,
        "physical": asdict(physical),
        "numerical": asdict(numerical),
        "domain_envelope": domain_envelope or {},
        "explosion_profile": explosion_profile or {},
    }


def state_hash(state) -> str:
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]
