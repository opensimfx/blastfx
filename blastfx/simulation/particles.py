"""Particle systems for debris, sparks, and embers in explosions."""

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


def build_debris_particles(context, collection, controller, config):
    """Emit debris meshes with Newtonian physics and gravity."""
    blast_id = controller["blastfx_id"]
    r = config["physical"].characteristic_radius_m
    duration_s = config.get("timeline_duration_s", config["physical"].characteristic_time_s)
    fps = context.scene.render.fps / context.scene.render.fps_base
    total_frames = max(1, int(duration_s * fps))

    # Emitter object (invisible sphere, raised above the ground line so
    # debris never starts underneath the ground collider).
    origin = controller.location
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=r * 0.1,
        location=(origin[0], origin[1], origin[2] + r * 0.1),
    )
    emitter = bpy.context.active_object
    emitter.name = f"Blast_{blast_id}_DebrisEmitter"
    emitter.hide_render = True
    emitter.display_type = "WIRE"
    collection.objects.link(emitter)
    # Unlink from scene collection if linked there.
    try:
        bpy.context.scene.collection.objects.unlink(emitter)
    except Exception:
        pass
    emitter["blastfx_role"] = "debris_emitter"
    emitter["blastfx_id"] = blast_id
    emitter["blastfx_component"] = "debris_particles"
    emitter["blastfx_generated"] = True

    # Create debris mesh variants for collection rendering.
    debris_col = bpy.data.collections.new(f"Blast_{blast_id}_DebrisMeshes")
    collection.children.link(debris_col)
    import bmesh
    variants = []
    for i in range(4):
        mesh = bpy.data.meshes.new(f"DebrisMesh_{i}")
        bm = bmesh.new()
        if i == 0:
            bmesh.ops.create_cube(bm, size=r * 0.06)
        elif i == 1:
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * 0.04)
        elif i == 2:
            bmesh.ops.create_cone(bm, segments=6, radius1=r * 0.03, radius2=r * 0.01, depth=r * 0.1)
        else:
            bmesh.ops.create_cube(bm, size=r * 0.03)
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(f"DebrisMesh_{i}", mesh)
        debris_col.objects.link(obj)
        # Charred dark material so shards read against smoke.
        material = bpy.data.materials.new(f"DebrisMesh_{i}_Material")
        material.diffuse_color = (0.12, 0.08, 0.05, 1.0)
        obj.data.materials.append(material)
        variants.append(obj)

    def configure(settings):
        settings.type = "EMITTER"
        settings.count = 200
        start = max(1, int(config.get("start_frame", 1)))
        settings.frame_start = start
        settings.frame_end = start + max(2, int(total_frames * 0.15))
        settings.lifetime = total_frames
        settings.lifetime_random = 0.4
        settings.physics_type = "NEWTON"
        settings.normal_factor = 2.0
        settings.factor_random = 0.8
        settings.tangent_factor = 0.5
        # Tumbling shards: random spin + dynamic rotation (CG Geek debris).
        settings.particle_size = max(r * 0.05, 0.01)
        settings.size_random = 0.5
        settings.use_rotations = True
        settings.use_dynamic_rotation = True
        settings.angular_velocity_mode = "RAND"
        settings.angular_velocity_factor = 5.0
        if hasattr(settings, "rotation_factor_random"):
            settings.rotation_factor_random = 1.0
        if hasattr(settings, "brownian_factor"):
            settings.brownian_factor = 0.2
        if hasattr(settings, "damping"):
            settings.damping = 0.05
        settings.render_type = "COLLECTION"
        settings.instance_collection = debris_col
        settings.use_collection_count = True
        if hasattr(settings, "use_collection_pick_random"):
            settings.use_collection_pick_random = True
        settings.child_type = "NONE"
        # Gravity and drag.
        settings.effector_weights.gravity = 1.0
        settings.mass = 0.5
        set_particle_seed(settings, config["numerical"].seed)

    _add_particle_system(emitter, "DebrisParticles", configure)
    return emitter


def build_spark_particles(context, collection, controller, config):
    """Emit bright spark/ember particles with Newtonian physics."""
    blast_id = controller["blastfx_id"]
    r = config["physical"].characteristic_radius_m
    duration_s = config.get("timeline_duration_s", config["physical"].characteristic_time_s)
    fps = context.scene.render.fps / context.scene.render.fps_base
    total_frames = max(1, int(duration_s * fps))

    spark_origin = controller.location
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=r * 0.05,
        location=(spark_origin[0], spark_origin[1], spark_origin[2] + r * 0.05),
    )
    emitter = bpy.context.active_object
    emitter.name = f"Blast_{blast_id}_SparkEmitter"
    emitter.hide_render = True
    emitter.display_type = "WIRE"
    collection.objects.link(emitter)
    try:
        bpy.context.scene.collection.objects.unlink(emitter)
    except Exception:
        pass
    emitter["blastfx_role"] = "spark_emitter"
    emitter["blastfx_id"] = blast_id
    emitter["blastfx_component"] = "spark_particles"
    emitter["blastfx_generated"] = True

    def configure(settings):
        settings.type = "EMITTER"
        settings.count = 200
        start = max(1, int(config.get("start_frame", 1)))
        settings.frame_start = start
        settings.frame_end = start + max(2, int(total_frames * 0.05))
        settings.lifetime = int(total_frames * 0.4)
        settings.lifetime_random = 0.6
        settings.physics_type = "NEWTON"
        settings.normal_factor = 5.0
        settings.factor_random = 1.0
        settings.tangent_factor = 1.0
        settings.render_type = "HALO"
        settings.child_size = r * 0.02
        settings.child_type = "NONE"
        settings.effector_weights.gravity = 0.3
        settings.mass = 0.01
        set_particle_seed(settings, config["numerical"].seed + 3)

    _add_particle_system(emitter, "SparkParticles", configure)
    return emitter