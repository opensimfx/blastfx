from mathutils import Vector

from ..core.froude import solver_scaling
from ..core.domain_envelope import longest_side
from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow


def build_stem(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    profile = config["profile"]
    plan = config["plan"]
    scaling = solver_scaling(longest_side(config["domain_envelope"]), numerical.playback_speed)
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "Stem")
    obj = primitive_flow(
        collection, name,
        controller.location + Vector((0.0, 0.0, radius * 1.0)),
        "cone", radius1=radius * 0.35, radius2=radius * 0.22, depth=radius * 2.0,
    )
    _, flow = configure_fluid_modifier(obj, "FLOW")
    # Column rise speed in multiples of U, handed to the solver as true m/s
    # divided by the Froude time scale (core.froude).
    solver_speed = scaling.flow_velocity(profile.stem_speed_U * physical.characteristic_velocity_mps)
    configure_flow(
        flow, flow_type="SMOKE", temperature=numerical.temperature_scale * 1.0,
        density=numerical.density_scale,
        velocity=(0.0, 0.0, solver_speed),
        velocity_random=0.2, surface_distance=0.5, volume_density=0.9, subframes=4,
    )
    time_unit = physical.time_unit_s
    start = int(config["start_frame"]) + int(round(plan.event_frames(profile.stem_delay_T * time_unit)))
    frames = max(2, int(round(plan.event_frames(profile.stem_feed_T * time_unit))))
    keyframe_inflow(flow, start, start + frames)
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "stem"
    obj["blastfx_generated"] = True
    return obj
