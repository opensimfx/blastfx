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



DIRECTED_DRIVE = 2.0   # sideways drive of a fully tilted blast, as a share of each system's launch speed


def directed_bias(config, launch_speed):
    """Directed blast: extra world-space velocity (x, y, 0) for a particle system that launches at
    ``launch_speed``: the horizontal part of the blast direction x DIRECTED_DRIVE x launch speed. Straight up it
    is zero (the blast as before); the more the blast is tilted, the harder everything leans that way. Emitters
    are unrotated, so their object space is world space."""
    if not config.get("directed"):
        return (0.0, 0.0, 0.0)
    dx, dy, _ = config.get("direction", (0.0, 0.0, 1.0))
    k = DIRECTED_DRIVE * float(launch_speed)
    return (dx * k, dy * k, 0.0)


def _local_bias(config, launch_speed):
    """directed_bias in the (rotated) emitter's object space."""
    bias = directed_bias(config, launch_speed)
    if not config.get("directed"):
        return bias
    from mathutils import Vector
    rot = Vector(config["direction"]).to_track_quat("Z", "Y").to_matrix()
    return tuple(rot.inverted() @ Vector(bias))


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


def _upper_hemisphere(bm, radius):
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=radius)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -1e-6], context="VERTS")


def _emitter(collection, controller, name, radius, height, role, component, dome=False, direction=None):
    """Emitter sphere; ``dome``: only its upper half, so particles launch up and out (normals point away)."""
    obj = _mesh_object(
        collection, name,
        (lambda bm: _upper_hemisphere(bm, radius)) if dome
        else (lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=2, radius=radius)),
    )
    obj.location = controller.location
    obj.location.z += height
    if direction is not None:  # directed blast: the emitter faces the blast direction
        from mathutils import Vector
        obj.rotation_euler = Vector(direction).to_track_quat("Z", "Y").to_euler()
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


# Spark cooling (modelled): ejected embers start near 1900 K and cool towards the Draper point (~800 K, where
# visible glow ends) over their life; radiance follows Stefan-Boltzmann (T^4), so a cooling spark dims as it
# reddens. T(t) = T_end + (T_start - T_end) exp(-k t), t = age / lifetime.
SPARK_T_START_K, SPARK_T_END_K, SPARK_COOLING_K = 1900.0, 800.0, 3.0


def _cooling_spark_material(name, strength):
    """Emission from a blackbody that cools over each particle's life (Particle Info age / lifetime)."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    info = nodes.new("ShaderNodeParticleInfo")

    def math(op, a=None, b=None, clamp=False):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = float(v)
            else:
                links.new(v, n.inputs[i])
        return n.outputs[0]

    t = math("DIVIDE", info.outputs["Age"], math("MAXIMUM", info.outputs["Lifetime"], 1.0), clamp=True)
    decay = math("EXPONENT", math("MULTIPLY", t, -SPARK_COOLING_K))
    temp = math("ADD", math("MULTIPLY", decay, SPARK_T_START_K - SPARK_T_END_K), SPARK_T_END_K)
    blackbody = nodes.new("ShaderNodeBlackbody")
    links.new(temp, blackbody.inputs["Temperature"])
    rel = math("DIVIDE", temp, SPARK_T_START_K)
    radiance = math("MULTIPLY", math("POWER", rel, 4.0), float(strength))
    emission = nodes.new("ShaderNodeEmission")
    links.new(blackbody.outputs["Color"], emission.inputs["Color"])
    links.new(radiance, emission.inputs["Strength"])
    links.new(emission.outputs[0], out.inputs["Surface"])
    material["blastfx_spark_cooling"] = True
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


# Debris smoke trails: each shard drags a thin smoke trail through the domain (a particle-source smoke flow on the
# debris system). The trail is left behind in the air, so it takes only a tenth of the shard's speed.
DEBRIS_TRAIL_DENSITY = 1.2
DEBRIS_TRAIL_HEAT = 0.3          # warm smoke: rises a little, never ignites (no fuel)
DEBRIS_TRAIL_VELOCITY = 0.1      # share of the shard's velocity given to its trail
DEBRIS_TRAIL_SUBFRAMES = 4       # fast shards: sub-steps keep the trail continuous, not dotted
DEBRIS_TRAIL_GATE_T = 0.5        # trails start once the shards have left the fireball (~0.8 R at 1.6 U), so
                                 # the 220 shards do not dump one puff into its core at birth


def _add_debris_trails(emitter, psys, config, start):
    from .fluid import configure_fluid_modifier, configure_flow

    numerical = config["numerical"]
    _, flow = configure_fluid_modifier(emitter, "FLOW")
    configure_flow(
        flow,
        flow_type="SMOKE",
        flow_source="PARTICLES",
        particle_system=psys,
        temperature=DEBRIS_TRAIL_HEAT * numerical.temperature_scale,
        density=DEBRIS_TRAIL_DENSITY * numerical.density_scale,
        fuel=0.0,
        subframes=DEBRIS_TRAIL_SUBFRAMES,
        velocity_factor=DEBRIS_TRAIL_VELOCITY * numerical.particle_velocity_factor,
    )
    flow.use_particle_size = True
    flow.particle_size = max(1.0, 0.5 * float(numerical.burst_particle_size_cells))   # at least a cell wide
    # gate: Use Flow keyed off until the shards are clear of the fireball (Mantaflow reads it per frame)
    gate = start + _frames(config, DEBRIS_TRAIL_GATE_T)
    for frame, on in ((start, False), (gate - 1, False), (gate, True)):
        flow.use_inflow = on
        flow.keyframe_insert("use_inflow", frame=frame)
    flow.use_inflow = True
    emitter["blastfx_debris_trails"] = True
    emitter["blastfx_debris_trail_start"] = gate


def build_debris_particles(context, collection, controller, config, smoke_trails=True):
    """Tumbling charred shards thrown out by the blast, optionally trailing smoke."""
    blast_id = controller["blastfx_id"]
    physical = config["physical"]
    numerical = config["numerical"]
    r = physical.characteristic_radius_m
    U = physical.characteristic_velocity_mps
    playback = numerical.playback_speed

    # A surface blast throws its ejecta up and out (the ejecta curtain leaves at ~45 degrees); a full sphere
    # threw half the shards straight into the ground, where they landed within a few frames (measured).
    profile = config.get("profile")
    emitter = _emitter(collection, controller, f"Blast_{blast_id}_DebrisEmitter",
                       r * 0.15, r * 0.15, "debris_emitter", "debris_particles",
                       dome=bool(config.get("directed")) or (bool(getattr(profile, "ground_surge", False))
                                                             and config.get("preset") != "nuclear_airburst"),
                       direction=config["direction"] if config.get("directed") else None)
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
        settings.object_align_factor = _local_bias(config, 1.6 * U * playback)
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

    psys = _add_particle_system(emitter, "DebrisParticles", configure)
    if smoke_trails:
        _add_debris_trails(emitter, psys, config, start)
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
                       r * 0.2, r * 0.25, "spark_emitter", "spark_particles", dome=bool(config.get("directed")),
                       direction=config["direction"] if config.get("directed") else None)
    prototypes = _prototype_collection(collection, f"Blast_{blast_id}_SparkMeshes")
    spark = _mesh_object(
        prototypes, f"Blast_{blast_id}_Spark",
        lambda bm: bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r * 0.008),
    )
    spark.data.materials.append(_cooling_spark_material(f"Blast_{blast_id}_Spark_Material", 40.0))

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
        settings.object_align_factor = _local_bias(config, 2.5 * U * playback)
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
