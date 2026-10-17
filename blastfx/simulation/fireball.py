from mathutils import Vector
from ..utils.naming import component_name
from .fluid import primitive_flow, configure_fluid_modifier, configure_flow, keyframe_inflow


def build_fireball(context, collection, controller, config):
    physical = config["physical"]
    numerical = config["numerical"]
    radius = physical.characteristic_radius_m
    profile = config.get("profile")
    source_radius = radius * (profile.source_radius if profile else 1.0)
    source_duration = profile.source_duration if profile else 0.15
    lobes = [(Vector((0.0, 0.0, 0.0)), 1.0, 1.0)]
    if profile and config.get("type") == "FUEL":
        lobes = [
            (Vector((0.0, 0.0, 0.0)), 1.0, 1.0),
            (Vector((source_radius * 0.42, -source_radius * 0.18, source_radius * 0.08)), 0.72, 1.08),
            (Vector((source_radius * -0.35, source_radius * 0.22, source_radius * 0.18)), 0.64, 0.92),
        ]
    first = None
    for index, (offset, scale, duration_scale) in enumerate(lobes):
        suffix = "Fireball" if index == 0 else f"FireballLobe{index}"
        obj = primitive_flow(
            collection, component_name(controller["blastfx_id"], suffix),
            controller.location + offset, "icosphere",
            radius=source_radius * scale, subdivisions=3,
        )
        _, flow = configure_fluid_modifier(obj, "FLOW")
        configure_flow(
            flow,
            flow_type="BOTH",
            temperature=numerical.temperature_scale,
            density=numerical.density_scale * (1.0 if index == 0 else 0.85),
            fuel=profile.fuel_amount if profile else 1.0,
            velocity=(0.0, 0.0, numerical.characteristic_velocity_mps * (profile.velocity_factor if profile else 0.35)),
            velocity_normal=numerical.characteristic_velocity_mps * (profile.velocity_factor if profile else 0.15),
            velocity_random=profile.velocity_random if profile else 0.35,
            surface_distance=0.5,
            volume_density=1.0,
            subframes=4,
        )
        keyframe_inflow(
            flow,
            config["start_frame"],
            config["start_frame"] + max(2, int(context.scene.render.fps * source_duration * duration_scale)),
        )
        obj.hide_render = True
        obj.display_type = "WIRE"
        obj["blastfx_role"] = "emitter"
        obj["blastfx_id"] = controller["blastfx_id"]
        obj["blastfx_component"] = "fireball" if index == 0 else "fireball_lobe"
        obj["blastfx_generated"] = True
        first = first or obj
    return first
