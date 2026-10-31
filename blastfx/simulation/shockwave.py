from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow


def build_shockwave(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "Shockwave")
    obj = primitive_flow(
        collection, name, controller.location,
        "cylinder", radius=radius * 2.0, depth=max(radius * 0.2, 0.1), segments=96,
    )
    _, flow = configure_fluid_modifier(obj, "FLOW")
    configure_flow(
        flow, flow_type="SMOKE", temperature=0.005,
        density=numerical.density_scale * 3.0,
        velocity=(0.0, 0.0, numerical.characteristic_velocity_mps * 0.02),
        velocity_normal=numerical.characteristic_velocity_mps * 0.9,
        velocity_random=0.5, surface_distance=0.25, volume_density=0.8, subframes=6,
    )
    duration_s = config.get("timeline_duration_s", config["duration"])
    frames = max(2, int(context.scene.render.fps * min(duration_s * 0.22, 1.5)))
    profile = config.get("profile")
    delay = getattr(profile, "shockwave_delay", 0.0)
    start = config["start_frame"] + int(context.scene.render.fps * duration_s * delay)
    keyframe_inflow(flow, start, start + frames)
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "shockwave"
    obj["blastfx_generated"] = True
    return obj
