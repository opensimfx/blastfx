from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow


def build_stem(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "Stem")
    obj = primitive_flow(
        collection, name,
        controller.location + __import__("mathutils").Vector((0, 0, radius * 1.0)),
        "cone", radius1=radius * 0.35, radius2=radius * 0.22, depth=radius * 2.0,
    )
    _, flow = configure_fluid_modifier(obj, "FLOW")
    profile = config.get("profile")
    # Stem rise speed as a fraction of the characteristic velocity. Long
    # timelines shrink that velocity to a crawl (16 s nuclear: ~5 m/s), so
    # profiles that need a mushroom set a fast multiple instead.
    stem_speed = numerical.characteristic_velocity_mps * float(
        getattr(profile, "stem_velocity_factor", 0.8) or 0.8
    )
    configure_flow(
        flow, flow_type="SMOKE", temperature=numerical.temperature_scale * 1.0,
        density=numerical.density_scale * 2.0,
        velocity=(0.0, 0.0, stem_speed),
        velocity_random=0.2, surface_distance=0.5, volume_density=0.9, subframes=4,
    )
    duration_s = config.get("timeline_duration_s", config["duration"])
    # Feed the column through most of long timelines: a 16 s nuclear shot
    # otherwise starves its stem before the cap has risen, leaving a single
    # squat blob. Short shots keep their original ~2 s burst of column.
    frames = max(2, int(context.scene.render.fps * max(2.0, min(duration_s * 0.6, 10.0))))
    keyframe_inflow(flow, config["start_frame"], config["start_frame"] + frames)
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "stem"
    obj["blastfx_generated"] = True
    return obj
