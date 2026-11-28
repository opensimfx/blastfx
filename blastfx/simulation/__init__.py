from .domain import build_domain
from .ground import build_ground
from .burst import build_burst
from .rapatronic import build_rapatronic
from .stem import build_stem
from .dust import build_dust
from .shockwave import build_shockwave
from .particles import build_debris_particles, build_spark_particles
from .physical_config import build_simulation_config
from .cache import configure_cache
from ..core.blast_plan import plan_blast


def build_explosion(context, collection, controller, props, plan=None):
    plan = plan or plan_blast(props, context.scene)
    config = plan.config_dict(props)

    # Build order matters: domain first, emitters second.
    domain = build_domain(context, collection, controller, config)

    # Configure cache after domain is built
    domain["blastfx_physics_state"] = controller.get("blastfx_physics_state", "")
    configure_cache(domain, context, collection, controller, config, props.quality)

    # Conventional explosion components
    build_ground(context, collection, controller, config, domain)

    if props.use_fireball:
        build_burst(context, collection, controller, config)

    # Rapatronic skin frames sit inside the innermost fireball (first
    # milliseconds), so it follows the burst whenever both are on.
    if getattr(props, "use_rapatronic", False) and props.use_fireball:
        build_rapatronic(context, collection, controller, config)

    if props.use_stem:
        build_stem(context, collection, controller, config)

    if props.use_dust:
        build_dust(context, collection, controller, config)

    if props.use_shockwave:
        build_shockwave(context, collection, controller, config)

    if props.use_debris:
        # One collection-variant particle system (4 tumbling shard meshes)
        # covers debris; the old single-shard emitter was merged into it.
        build_debris_particles(context, collection, controller, config,
                               smoke_trails=bool(getattr(props, "use_debris_smoke", True)))
    build_spark_particles(context, collection, controller, config)

    path = getattr(props, "fire_path", None)
    if path is not None and path.type == "CURVE":
        from .fire_path import build_fire_path
        build_fire_path(context, collection, controller, config, path, float(props.fire_path_speed))

    return domain