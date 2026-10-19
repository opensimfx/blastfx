from .flash import build_flash
from .shockwave import build_shockwave_geometry
from .camera import build_camera_fx
from .exposure import build_exposure
from .heat_distortion import build_heat_distortion, build_heat_distortion_compositor
from .dust_light import build_ground_dust_fill
from ..core.physics import AmbientConditions, PhysicalConfig, derive_physics, gravity_magnitude
from ..simulation.physical_config import build_simulation_config
from ..core.domain_envelope import build_domain_envelope
from ..core.explosion_profile import profile_for


def _animation_config(context, props):
    physical = derive_physics(PhysicalConfig(
        scale_m=float(props.scale),
        reference_energy=float(props.reference_energy),
        intensity=float(props.intensity),
        duration_s=float(props.duration),
        ambient=AmbientConditions(gravity=gravity_magnitude(context.scene.gravity)),
    ))
    profile = profile_for(props.explosion_type)
    fps = context.scene.render.fps
    timeline_duration_s = physical.characteristic_time_s / max(float(props.speed), 0.05)
    numerical = build_simulation_config(
        physical,
        props.quality,
        props.resolution,
        props.noise_upres,
        props.seed,
        props.turbulence,
        props.smoke_density,
        props.fire_temperature,
        profile,
        timeline_duration_s=timeline_duration_s,
        fps=context.scene.render.fps / context.scene.render.fps_base,
    )
    return {
        "type": props.explosion_type,
        "preset": props.preset_id,
        "scale": float(props.scale),
        "intensity": float(props.intensity),
        "speed": float(props.speed),
        "duration": float(props.duration),
        "start_frame": int(props.start_frame),
        "seed": int(props.seed),
        "quality": props.quality,
        "resolution": int(props.resolution),
        "noise": int(props.noise_upres),
        "turbulence": float(props.turbulence),
        "smoke_density": float(props.smoke_density),
        "fire_temperature": float(props.fire_temperature),
        "physical": physical,
        "numerical": numerical,
        "timeline_duration_s": timeline_duration_s,
        "domain_envelope": build_domain_envelope(
            physical,
            numerical,
            gravity_magnitude(context.scene.gravity),
            timeline_duration_s,
            profile,
        ),
        "profile": profile,
        "_fps": context.scene.render.fps / context.scene.render.fps_base,
    }


def build_animation(context, collection, controller, props):
    config = _animation_config(context, props)

    if props.use_flash:
        build_flash(context, collection, controller, config)
    if props.use_shockwave:
        build_shockwave_geometry(context, collection, controller, config)
    if (
        getattr(config.get("profile"), "ground_surge", False)
        and getattr(config.get("profile"), "shockwave_radius_factor", 3.0) > 3.0
    ):
        build_ground_dust_fill(context, collection, controller, config)

    if props.use_camera_fx:
        build_camera_fx(context, collection, controller, config)
    if props.use_exposure:
        build_exposure(context, collection, controller, config)
    if props.use_heat_distortion:
        build_heat_distortion(context, collection, controller, config)
        build_heat_distortion_compositor(context, controller, config)
    return config