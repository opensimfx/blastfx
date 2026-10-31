from ..utils.animation import action_fcurves
from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow
from .ground import ground_top_z


def build_dust(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    profile = config.get("profile")
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "Dust")
    depth = max(radius * 0.3, 0.02)

    # Ground-surge blasts spawn their dust shell at the ground surface and
    # keep it hugging the floor with negative (cool) air temperature
    # (Iridesium: initial temperature about -3 = cool ground dust).
    location = controller.location
    if profile and profile.ground_surge:
        location = (
            location[0], location[1],
            ground_top_z(config, controller) + depth / 2.0,
        )

    obj = primitive_flow(
        collection, name, location,
        "cylinder", radius=radius * 2.5, depth=depth, segments=64,
    )
    _, flow = configure_fluid_modifier(obj, "FLOW")
    configure_flow(
        flow, flow_type="SMOKE",
        temperature=numerical.temperature_scale * (
            profile.dust_temperature if profile else -2.0
        ),
        density=numerical.density_scale * (
            profile.dust_density_factor if profile else 2.0
        ),
        velocity=(0.0, 0.0, numerical.characteristic_velocity_mps * 0.10),
        velocity_normal=numerical.characteristic_velocity_mps * (
            profile.dust_velocity_normal_factor if profile else 0.30
        ),
        velocity_random=profile.dust_velocity_random if profile else 0.65,
        surface_distance=0.25, volume_density=1.0, subframes=3,
    )
    duration_s = config.get("timeline_duration_s", config["duration"])
    duration_factor = profile.dust_duration_factor if profile else 0.35
    frames = max(2, int(context.scene.render.fps * duration_s * duration_factor))
    start_frame = config["start_frame"]
    keyframe_inflow(flow, start_frame, start_frame + frames)

    # Expanding dust donut: grow the emitter ring outward over its first
    # ~1-2 s so smoke injection sweeps a visible ground ring instead of a
    # static cylinder puff (same LINEAR keyframe pattern as the visible
    # shockwave ring in animation/shockwave.py).
    ring_frames = max(6, round(context.scene.render.fps * min(duration_s * duration_factor, 2.0)))
    obj.scale = (0.45, 0.45, 0.45)
    obj.keyframe_insert("scale", frame=start_frame)
    obj.scale = (1.0, 1.0, 1.0)
    obj.keyframe_insert("scale", frame=start_frame + ring_frames)
    for fcurve in action_fcurves(obj):
        if fcurve.data_path == "scale":
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"

    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "dust"
    obj["blastfx_generated"] = True
    return obj
