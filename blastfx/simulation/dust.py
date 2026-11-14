from ..core.froude import solver_scaling
from ..core.domain_envelope import longest_side
from ..utils.animation import action_fcurves
from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow
from .ground import ground_top_z


def build_dust(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    profile = config["profile"]
    plan = config["plan"]
    scaling = solver_scaling(longest_side(config["domain_envelope"]), numerical.playback_speed)
    radius = physical.characteristic_radius_m
    velocity_unit = physical.characteristic_velocity_mps
    name = component_name(controller["blastfx_id"], "Dust")
    depth = max(radius * 0.3, 0.02)

    # Ground-surge blasts spawn their dust shell at the ground surface and
    # keep it hugging the floor with negative (cool) air temperature
    # (Iridesium: initial temperature about -3 = cool ground dust).
    location = controller.location
    if profile.ground_surge:
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
        temperature=numerical.temperature_scale * profile.dust_temperature,
        density=numerical.density_scale * profile.dust_density_factor,
        velocity=(0.0, 0.0, scaling.flow_velocity(profile.dust_lift_U * velocity_unit)),
        # velocity_normal is in grid units, not m/s (measured): convert so the
        # surge spreads at the same real speed at every resolution.
        velocity_normal=scaling.flow_normal_velocity(
            profile.dust_spread_U * velocity_unit, numerical.voxel_size_m
        ),
        velocity_random=profile.dust_velocity_random,
        surface_distance=0.25, volume_density=1.0, subframes=3,
    )
    time_unit = physical.time_unit_s
    frames = max(2, int(round(plan.event_frames(profile.dust_feed_T * time_unit))))
    start_frame = config["start_frame"]
    keyframe_inflow(flow, start_frame, start_frame + frames)

    # Expanding dust donut: grow the emitter ring outward so smoke injection
    # sweeps a visible ground ring instead of a static cylinder puff.
    ring_frames = max(2, int(round(plan.event_frames(profile.dust_ring_T * time_unit))))
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
