import bpy
from ..utils.naming import component_name
from .fluid import primitive_flow


def build_debris(context, collection, controller, config):
    """Create a conventional Blender particle debris emitter on a real mesh."""
    physical = config["physical"]
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "Debris")
    obj = primitive_flow(collection, name, controller.location, "sphere", radius=max(radius * 0.2, 0.02), segments=24, rings=12)

    for selected in context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    try:
        bpy.ops.object.particle_system_add()
    except RuntimeError as exc:
        raise RuntimeError(f"Could not create debris particle system: {exc}") from exc

    if not obj.particle_systems:
        raise RuntimeError("Blender did not create the debris particle system")
    pset = obj.particle_systems[-1].settings
    pset.name = name + "_Settings"
    pset.count = 200
    pset.frame_start = int(config["start_frame"])
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)
    pset.frame_end = pset.frame_start + max(1, int(context.scene.render.fps * duration_s * 0.3))
    pset.lifetime = max(1.0, context.scene.render.fps * duration_s * 0.5)
    pset.emit_from = "VOLUME"
    pset.physics_type = "NEWTON"
    pset.mass = 0.1
    pset.particle_size = max(radius * 0.02, 0.005)
    pset.size_random = 0.5
    pset.use_rotations = True
    pset.angular_velocity_mode = "RAND"
    pset.angular_velocity_factor = 5.0
    pset.normal_factor = 0.0
    if hasattr(pset, "factor_random"):
        pset.factor_random = 0.5
    if hasattr(pset, "effector_weights") and pset.effector_weights:
        pset.effector_weights.gravity = 1.0
    pset.effector_weights.gravity = 1.0
    pset.normal_factor = 1.0
    pset.brownian_factor = 0.1 if hasattr(pset, "brownian_factor") else 0.0
    pset.seed = config["numerical"].seed + 11

    shard = primitive_flow(
        collection,
        name + "_Shard",
        controller.location,
        "icosphere",
        radius=max(radius * 0.025, 0.005),
        subdivisions=1,
    )
    shard.hide_render = True
    shard.hide_viewport = True
    shard["blastfx_role"] = "debris_instance"
    shard["blastfx_id"] = controller["blastfx_id"]
    shard["blastfx_component"] = "debris"
    shard["blastfx_generated"] = True
    material = bpy.data.materials.new(name + "_Material")
    material.diffuse_color = (0.12, 0.08, 0.05, 1.0)
    shard.data.materials.append(material)
    pset.render_type = "OBJECT"
    pset.instance_object = shard
    obj.hide_render = True
    obj.hide_viewport = True

    obj["blastfx_role"] = "debris"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "debris"
    obj["blastfx_generated"] = True
    return obj
