"""Particle systems for debris and sparks.

Three bugs kept every particle off screen before (all measured in 5.2.3):
the emitters were ``hide_render``, which hides their instances too; sparks
used the HALO render type, which Cycles does not draw; and debris shards
were sized twice (mesh ~R*0.06 x particle_size R*0.05: centimetre specks).
Emitters now stay render-visible with ``show_instancer_for_render`` off and
prototypes live in a view-layer-excluded collection, which still instances.

Speeds are multiples of U and lifetimes multiples of T like the rest of the
blast; gravity is scaled by playback^2 so slow-motion arcs stay correct.
"""

import bmesh
import bpy



def set_particle_seed(settings, seed):
    """ParticleSettings.seed is unavailable on some Blender builds (5.2); guard it."""
    if hasattr(settings, "seed"):
        settings.seed = int(seed) % 2147483647


def _add_particle_system(obj, name, settings_fn):
    """Add a particle system to an object and configure it."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.particle_system_add()
    ps = obj.particle_systems[-1]
    ps.name = name
    settings_fn(ps.settings)
    obj.select_set(False)
    return ps


def _mesh_object(collection, name, build):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    bm = bmesh.new()
    try:
        build(bm)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj["blastfx_generated"] = True
    return obj


def _emitter(collection, controller, name, radius, height, role, component):
    obj = _mesh_object(
        collection, name,
        lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius),
    )
    obj.location = controller.location
    obj.location.z += height
    obj.display_type = "WIRE"
    # Not hide_render: that hides the particles too. Hide only the emitter.
    obj.show_instancer_for_render = False
    obj["blastfx_role"] = role
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = component
    obj["blastfx_generated"] = True
    return obj


def _find_layer_collection(layer_collection, collection):
    if layer_collection.collection == collection:
        return layer_collection
    for child in layer_collection.children:
        found = _find_layer_collection(child, collection)
        if found is not None:
            return found
    return None


def _prototype_collection(parent, name):
    """Child collection for instanced prototypes, excluded from the view layer."""
    collection = bpy.data.collections.new(name)
    collection["blastfx_generated"] = True
    parent.children.link(collection)
    layer = _find_layer_collection(bpy.context.view_layer.layer_collection, collection)
    if layer is not None:
        layer.exclude = True
    return collection


def _frames(config, event_T):
    plan = config["plan"]
    return max(1, int(round(plan.event_frames(event_T * config["physical"].time_unit_s))))


def _emission_material(name, temperature_k, strength):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    blackbody = nodes.new("ShaderNodeBlackbody")
    blackbody.inputs["Temperature"].default_value = temperature_k
    emission.inputs["Strength"].default_value = strength
    links.new(blackbody.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs[0], out.inputs["Surface"])
    return material


def _charred_material(name):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (0.045, 0.035, 0.03, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.9
    material.diffuse_color = (0.12, 0.08, 0.05, 1.0)
    return material


def build_debris_particles(context, collection, controller, config):
    """Tumbling charred shards thrown out by the blast."""
    blast_id = controller["blastfx_id"]
    physical = config["physical"]
    numerical = config["numerical"]
    r = physical.characteristic_radius_m
    U = physical.characteristic_velocity_mps
    playback = numerical.playback_speed

    emitter = _emitter(collection, controller, f"Blast_{blast_id}_DebrisEmitter",
                       r * 0.15, r * 0.15, "debris_emitter", "debris_particles")
    shards = _prototype_collection(collection, f"Blast_{blast_id}_DebrisMeshes")
    material = _charred_material(f"Blast_{blast_id}_Debris_Material")
    builders = (
        lambda bm: bmesh.ops.create_cube(bm, size=r * 0.05),
        lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * 0.03),
        lambda bm: bmesh.ops.create_cone(bm, segments=5, radius1=r * 0.025, radius2=r * 0.006, depth=r * 0.08),
        lambda bm: bmesh.ops.create_cube(bm, size=r * 0.025),
    )
    for index, build in enumerate(builders):
        shard = _mesh_object(shards, f"Blast_{blast_id}_DebrisMesh_{index}", build)
        shard.data.materials.append(material)

    start = max(1, int(config.get("start_frame", 1)))

    def configure(settings):
        settings.type = "EMITTER"
        settings.count = 220
        settings.frame_start = start
        settings.frame_end = start + _frames(config, 0.08)
        settings.lifetime = _frames(config, 4.0)
        settings.lifetime_random = 0.3
        settings.physics_type = "NEWTON"
        settings.normal_factor = 1.6 * U * playback
        settings.factor_random = 0.9 * U * playback
        settings.particle_size = 1.0  # shard meshes are already sized to R
        settings.size_random = 0.6
        settings.use_rotations = True
        settings.use_dynamic_rotation = True
        settings.angular_velocity_mode = "RAND"
        settings.angular_velocity_factor = 6.0 * playback
        settings.render_type = "COLLECTION"
        settings.instance_collection = shards
        if hasattr(settings, "use_collection_pick_random"):
            settings.use_collection_pick_random = True
        settings.child_type = "NONE"
        settings.effector_weights.gravity = playback ** 2
        settings.mass = 0.5
        set_particle_seed(settings, numerical.seed)

    _add_particle_system(emitter, "DebrisParticles", configure)
    return emitter


def build_spark_particles(context, collection, controller, config):
    """Hot embers flung out of the fireball, cooling as they fall."""
    blast_id = controller["blastfx_id"]
    physical = config["physical"]
    numerical = config["numerical"]
    r = physical.characteristic_radius_m
    U = physical.characteristic_velocity_mps
    playback = numerical.playback_speed

    emitter = _emitter(collection, controller, f"Blast_{blast_id}_SparkEmitter",
                       r * 0.2, r * 0.25, "spark_emitter", "spark_particles")
    prototypes = _prototype_collection(collection, f"Blast_{blast_id}_SparkMeshes")
    spark = _mesh_object(
        prototypes, f"Blast_{blast_id}_Spark",
        lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * 0.008),
    )
    spark.data.materials.append(_emission_material(f"Blast_{blast_id}_Spark_Material", 1900.0, 40.0))

    start = max(1, int(config.get("start_frame", 1)))

    def configure(settings):
        settings.type = "EMITTER"
        settings.count = 300
        settings.frame_start = start
        settings.frame_end = start + _frames(config, 0.15)
        settings.lifetime = _frames(config, 1.5)
        settings.lifetime_random = 0.6
        settings.physics_type = "NEWTON"
        settings.normal_factor = 2.5 * U * playback
        settings.factor_random = 1.2 * U * playback
        settings.particle_size = 1.0
        settings.size_random = 0.7
        settings.render_type = "OBJECT"
        settings.instance_object = spark
        settings.child_type = "NONE"
        settings.effector_weights.gravity = playback ** 2
        settings.mass = 0.01
        set_particle_seed(settings, numerical.seed + 3)

    _add_particle_system(emitter, "SparkParticles", configure)
    return emitter
