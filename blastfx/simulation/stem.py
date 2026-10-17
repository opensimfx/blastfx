from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow


def build_stem(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "Stem")
    obj = primitive_flow(
        collection, name,
        controller.location + __import__("mathutils").Vector((0, 0, radius * 0.75)),
        "cone", radius1=radius * 0.3, radius2=radius * 0.2, depth=radius * 1.5,
    )
    _, flow = configure_fluid_modifier(obj, "FLOW")
    configure_flow(
        flow, flow_type="SMOKE", temperature=numerical.temperature_scale * 0.6,
        density=numerical.density_scale * 1.5,
        velocity=(0.0, 0.0, numerical.characteristic_velocity_mps * 0.8),
        velocity_random=0.2, surface_distance=0.5, volume_density=0.9, subframes=4,
    )
    duration_s = config.get("timeline_duration_s", config["duration"])
    frames = max(2, int(context.scene.render.fps * min(duration_s, 2.0)))
    keyframe_inflow(flow, config["start_frame"], config["start_frame"] + frames)
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "stem"
    obj["blastfx_generated"] = True
    return obj
