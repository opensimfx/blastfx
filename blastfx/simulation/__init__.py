from .domain import build_domain
from .burst import build_burst
from .stem import build_stem
from .dust import build_dust
from .shockwave import build_shockwave
from .debris import build_debris
from .particles import build_debris_particles, build_spark_particles
from .physical_config import build_simulation_config
from .cache import configure_cache
from ..core.physics import AmbientConditions, PhysicalConfig, derive_physics, gravity_magnitude
from ..core.domain_envelope import build_domain_envelope
from ..core.explosion_profile import profile_for


def build_explosion(context, collection, controller, props):
    physical = derive_physics(
        PhysicalConfig(
            scale_m=float(props.scale),
            reference_energy=float(props.reference_energy),
            intensity=float(props.intensity),
            duration_s=float(props.duration),
            ambient=AmbientConditions(gravity=gravity_magnitude(context.scene.gravity)),
        )
    )

    profile = profile_for(props.explosion_type)
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
    )

    config = {
        "type": props.explosion_type,
        "preset": props.preset_id,
        "scale": props.scale,
        "intensity": props.intensity,
        "speed": props.speed,
        "duration": props.duration,
        "start_frame": props.start_frame,
        "seed": props.seed,
        "quality": props.quality,
        "resolution": props.resolution,
        "noise": props.noise_upres,
        "turbulence": props.turbulence,
        "smoke_density": props.smoke_density,
        "fire_temperature": props.fire_temperature,
        "physical": physical,
        "numerical": numerical,
        "timeline_duration_s": physical.characteristic_time_s / max(float(props.speed), 0.05),
        "profile": profile,
    }
    config["domain_envelope"] = build_domain_envelope(
        physical,
        numerical,
        gravity_magnitude(context.scene.gravity),
        config["timeline_duration_s"],
        profile,
    )

    # Build order matters: domain first, emitters second.
    domain = build_domain(context, collection, controller, config)

    # Configure cache after domain is built
    domain["blastfx_physics_state"] = controller.get("blastfx_physics_state", "")
    configure_cache(domain, context, collection, controller, config, props.quality)

    # Conventional explosion components
    if props.use_fireball:
        build_burst(context, collection, controller, config)

    if props.use_stem:
        build_stem(context, collection, controller, config)

    if props.use_dust:
        build_dust(context, collection, controller, config)

    if props.use_shockwave:
        build_shockwave(context, collection, controller, config)

    if props.use_debris:
        build_debris(context, collection, controller, config)
        build_debris_particles(context, collection, controller, config)
    build_spark_particles(context, collection, controller, config)

    return domain