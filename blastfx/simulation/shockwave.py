from ..core.froude import solver_scaling
from ..core.domain_envelope import longest_side
from ..utils.animation import action_fcurves
from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow
from .ground import ground_top_z


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
    # An annulus around the fireball: the shock raises dust from the ground
    # it sweeps. A filled cylinder stamped a dark pancake under the fireball.
    # It sits on the ground, not at the burst: an air burst's ring at burst
    # height rendered as a glowing disc around the fireball's middle.
    location = controller.location.copy()
    location.z = ground_top_z(config, controller)
    obj = primitive_flow(
        collection, name, location, "annulus",
        inner_radius=radius * 1.0, outer_radius=radius * 2.2,
        depth=max(radius * 0.25, numerical.voxel_size_m * 2.0), segments=96,
    )
    _, flow = configure_fluid_modifier(obj, "FLOW")
    configure_flow(
        flow, flow_type="SMOKE", temperature=0.005,
        density=numerical.density_scale * 0.6,
        # Lift so the raised dust billows into a skirt instead of lying as a
        # flat pancake on the ground (0.35 U still read as a disc at Final).
        velocity=(0.0, 0.0, scaling.flow_velocity(0.8 * physical.characteristic_velocity_mps)),
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
    # Raised dust sweeps outward from the fireball's edge: grow the emitter
    # ring from inside the fireball to full size instead of stamping the
    # whole annulus in one frame (which read as a flat disc at Final).
    sweep = max(2, int(round(plan.event_frames(profile.shock_sweep_T * physical.time_unit_s))))
    obj.scale = (0.45, 0.45, 1.0)
    obj.keyframe_insert("scale", frame=start)
    obj.scale = (1.0, 1.0, 1.0)
    obj.keyframe_insert("scale", frame=start + sweep)
    for fcurve in action_fcurves(obj):
        if fcurve.data_path == "scale":
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "emitter"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "shockwave"
    obj["blastfx_generated"] = True
    return obj
