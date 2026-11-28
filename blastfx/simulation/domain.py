import bpy
from mathutils import Vector

from ..utils.naming import component_name
from ..utils.compatibility import set_required_rna
from ..core.physics import seconds_to_frames
from ..materials.volume import build_volume_material
from .fluid import add_mesh_object, configure_fluid_modifier


def apply_noise_settings(domain, numerical):
    """The noise pass settings (also used by Re-bake Noise on an existing domain)."""
    set_required_rna(domain,
        use_noise=bool(numerical.noise_upres > 1),
        noise_scale=max(1, min(100, int(numerical.noise_upres))),
        noise_strength=max(0.0, min(10.0, numerical.noise_strength)),
        noise_pos_scale=max(0.0001, min(10.0, numerical.noise_pos_scale)),
        noise_time_anim=max(0.0001, min(10.0, numerical.noise_time_anim)),
    )


def build_domain(context, collection, controller, config):
    """Create and configure a Blender 5.2 Mantaflow gas domain."""
    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "Domain")
    physical = config["physical"]
    numerical = config["numerical"]
    envelope = config["domain_envelope"]
    size = Vector(envelope["size"])
    center = Vector(envelope["center"])
    obj = add_mesh_object(
        collection, name,
        lambda bm: __import__("bmesh").ops.create_cube(bm, size=2.0),
        controller.location + center,
    )
    obj.scale = size / 2.0
    # Refresh derived dimensions so obj.dimensions is valid immediately even
    # when Blender runs headless (no automatic depsgraph eval after scale set).
    bpy.context.view_layer.update()
    obj.display_type = "WIRE"
    # The domain carries the rendered Mantaflow volume and must remain renderable.
    obj.hide_render = False

    mod, domain = configure_fluid_modifier(obj, "DOMAIN")
    set_required_rna(domain, domain_type="GAS")

    fps = context.scene.render.fps / context.scene.render.fps_base
    start_frame = int(config.get("start_frame", 1))
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)
    end_frame = start_frame + max(1, int(round(seconds_to_frames(duration_s, fps))))

    cache_dir = config.get("cache_dir")
    if not cache_dir:
        cache_dir = f"//blastfx_cache/{blast_id}"

    set_required_rna(domain,
        resolution_max=numerical.domain_resolution,
        time_scale=max(0.0001, min(10.0, numerical.time_scale_multiplier)),
        use_adaptive_domain=bool(numerical.use_adaptive_domain),
        adapt_threshold=float(numerical.adapt_threshold),
        adapt_margin=int(numerical.adapt_margin),
        # MODULAR with a noise pass, so the noise alone can be re-baked (Re-bake Noise). Resumable is required:
        # in Blender 5.2.3 a modular noise pass writes empty grids without it (1.4 KB against 367 KB per frame,
        # measured); it costs ~2.6x the data cache's disk, not bake time.
        cache_type="MODULAR" if numerical.noise_upres > 1 else "ALL",
        cache_resumable=bool(numerical.noise_upres > 1),
        cache_directory=str(cache_dir),
        cache_frame_start=start_frame,
        cache_frame_end=end_frame,
        cache_data_format="OPENVDB",
        cache_noise_format="OPENVDB",
        use_collision_border_bottom=True,
        use_collision_border_top=bool(getattr(config["profile"], "ceiling", False)),
        use_collision_border_front=False,
        use_collision_border_back=False,
        use_collision_border_left=False,
        use_collision_border_right=False,
        gravity=Vector(context.scene.gravity),
        alpha=max(-5.0, min(5.0, numerical.buoyancy_density)),
        beta=max(-5.0, min(5.0, numerical.buoyancy_heat)),
        vorticity=max(0.0, min(0.2, numerical.turbulence_strength)),
        burning_rate=max(0.01, min(4.0, numerical.burning_rate)),
        flame_smoke=max(0.0, min(8.0, numerical.flame_smoke)),
        flame_vorticity=max(0.0, min(2.0, numerical.flame_vorticity)),
        flame_ignition=max(0.5, min(5.0, numerical.flame_ignition)),
        flame_max_temp=max(1.0, min(10.0, numerical.flame_max_temp)),
        use_dissolve_smoke=bool(numerical.use_dissolve_smoke),
        use_dissolve_smoke_log=True,
        dissolve_speed=max(1, int(numerical.dissolve_speed)),
        use_fractions=True,
        fractions_distance=0.5,
        fractions_threshold=0.05,
        cfl_condition=float(numerical.cfl_condition),
        additional_res=int(numerical.additional_res),
        timesteps_min=max(1, int(numerical.timesteps_min)),
        timesteps_max=max(int(numerical.timesteps_min), int(numerical.timesteps_max)),
        use_adaptive_timesteps=True,
    )

    apply_noise_settings(domain, numerical)
    mat = build_volume_material(f"{name}_Volume", config)
    props = getattr(context.scene, "blastfx", None)
    if props is not None:  # artist look layer (material only, not part of the cache identity)
        from ..materials.volume import LOOK_DEFAULTS, apply_fire_look
        apply_fire_look(mat, **{k: getattr(props, k, v) for k, v in LOOK_DEFAULTS.items()})
    obj.data.materials.append(mat)

    obj["blastfx_role"] = "domain"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "domain"
    obj["blastfx_generated"] = True

    return obj
