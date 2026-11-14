from ..core.froude import solver_scaling
from ..core.domain_envelope import longest_side
from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow


def shock_start_frame(config) -> int:
    """Frame the shock-driven dust kicks off (shared with the visible ring)."""
    plan = config["plan"]
    delay = config["profile"].shock_delay_T * config["physical"].time_unit_s
    return int(config["start_frame"]) + int(round(plan.event_frames(delay)))


def build_shockwave(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    profile = config["profile"]
    plan = config["plan"]
    scaling = solver_scaling(longest_side(config["domain_envelope"]), numerical.playback_speed)
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
        # velocity_normal is in grid units (measured): convert from m/s.
        velocity_normal=scaling.flow_normal_velocity(
            profile.shock_spread_U * physical.characteristic_velocity_mps,
            numerical.voxel_size_m,
        ),
        velocity_random=0.5, surface_distance=0.25, volume_density=0.8, subframes=6,
    )
    start = shock_start_frame(config)
    frames = max(2, int(round(plan.event_frames(profile.shock_feed_T * physical.time_unit_s))))
    keyframe_inflow(flow, start, start + frames)
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "shockwave"
    obj["blastfx_generated"] = True
    return obj
