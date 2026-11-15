import bpy
import bmesh
from ..utils.naming import component_name
from ..utils.animation import action_fcurves

COMPOSITOR_NAME = "BlastFX_Compositor"


def _camera_only(obj):
    """Cycles ray visibility: seen by the camera, invisible to all lighting."""
    for attr in ("visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        if hasattr(obj, attr):
            setattr(obj, attr, False)


def build_heat_haze_material(name, radius):
    """Refraction shell: Cycles volumes cannot refract, so haze needs a surface.

    A near-1 IOR Refraction BSDF with animated bump noise bends the view
    through the hot air; ``BlastFX Haze Mix`` fades it in and out (0 = clear).
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    refraction = nodes.new("ShaderNodeBsdfRefraction")
    refraction.inputs["IOR"].default_value = 1.02
    refraction.inputs["Roughness"].default_value = 0.0
    coords = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "BlastFX Haze Noise"
    noise.noise_dimensions = "4D"
    # Cells ~1/6 of the radius, independent of blast size.
    noise.inputs["Scale"].default_value = 6.0 / max(radius, 1e-6)
    noise.inputs["Detail"].default_value = 3.0
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    links.new(coords.outputs["Object"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], refraction.inputs["Normal"])
    # "BlastFX Haze Mix" Fac is the animated strength; it is multiplied by
    # a facing mask so the shell fades out toward its silhouette, where
    # refraction bends hardest and would draw a visible glass edge.
    strength = nodes.new("ShaderNodeValue")
    strength.name = "BlastFX Haze Strength"
    strength.outputs[0].default_value = 0.0
    facing = nodes.new("ShaderNodeLayerWeight")
    facing.inputs["Blend"].default_value = 0.5
    center = nodes.new("ShaderNodeMath")
    center.operation = "SUBTRACT"
    center.use_clamp = True
    center.inputs[0].default_value = 1.0
    links.new(facing.outputs["Facing"], center.inputs[1])
    soft = nodes.new("ShaderNodeMath")
    soft.operation = "POWER"
    soft.inputs[1].default_value = 3.0
    links.new(center.outputs[0], soft.inputs[0])
    masked = nodes.new("ShaderNodeMath")
    masked.operation = "MULTIPLY"
    links.new(strength.outputs[0], masked.inputs[0])
    links.new(soft.outputs[0], masked.inputs[1])
    mix = nodes.new("ShaderNodeMixShader")
    mix.name = "BlastFX Haze Mix"
    links.new(masked.outputs[0], mix.inputs["Fac"])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(refraction.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def build_heat_distortion(context, collection, controller, config):
    """Heat shimmer over the fireball for the fire's lifetime."""
    physical = config["physical"]
    plan = config["plan"]
    shading = config["shading"]
    radius = physical.characteristic_radius_m
    T = physical.time_unit_s
    name = component_name(controller["blastfx_id"], "HeatDistortion")
    bm = bmesh.new()
    try:
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=radius * 1.6)
        mesh = bpy.data.meshes.new(name + "_Mesh")
        bm.to_mesh(mesh)
    finally:
        bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = controller.location
    obj.location.z += radius * 0.6
    _camera_only(obj)
    mat = build_heat_haze_material(name + "_Mat", radius)
    obj.data.materials.append(mat)

    start = int(config["start_frame"])
    end = start + max(2, int(round(plan.event_frames(shading.fire_light_T * T * 1.5))))
    mix = mat.node_tree.nodes["BlastFX Haze Strength"].outputs[0]
    for frame, value in ((start, 0.0), (start + 1, 0.9), (end, 0.0)):
        mix.default_value = value
        mix.keyframe_insert("default_value", frame=frame)
    # Shimmer: the noise drifts through its 4th dimension about twice per T.
    w = mat.node_tree.nodes["BlastFX Haze Noise"].inputs["W"]
    w.default_value = 0.0
    w.keyframe_insert("default_value", frame=start)
    w.default_value = 2.0 * (end - start) / max(plan.event_frames(T), 1.0)
    w.keyframe_insert("default_value", frame=end)
    if mat.node_tree.animation_data and mat.node_tree.animation_data.action:
        for fcurve in action_fcurves(mat.node_tree):
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"

    # Hidden outside its window so it costs nothing to render.
    for prop in ("hide_render", "hide_viewport"):
        for frame, hidden in ((start - 1, True), (start, False), (end, False), (end + 1, True)):
            setattr(obj, prop, hidden)
            obj.keyframe_insert(prop, frame=frame)
    for fcurve in action_fcurves(obj):
        for kp in fcurve.keyframe_points:
            kp.interpolation = "CONSTANT"

    obj["blastfx_role"] = "heat_distortion"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "heat_distortion"
    obj["blastfx_generated"] = True
    return obj


def build_heat_distortion_compositor(context, controller, config):
    """Bloom + gentle grade, without touching an artist's own compositor.

    The old version cleared whatever compositor tree the scene had, added a
    hue shift, and denoised a second time without albedo/normal passes. Now
    a scene that already composites with its own tree is left alone.
    """
    scene = context.scene
    tree = scene.compositing_node_group
    if tree is not None and tree.name != COMPOSITOR_NAME and len(tree.nodes) > 0:
        return None
    if tree is None:
        tree = bpy.data.node_groups.get(COMPOSITOR_NAME) or bpy.data.node_groups.new(
            COMPOSITOR_NAME, "CompositorNodeTree"
        )
        scene.compositing_node_group = tree
    scene.use_nodes = True
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    rlayers = nodes.new("CompositorNodeRLayers")
    rlayers.location = (-400, 0)

    # Bloom (not the default Streaks star filter) on the fire's highlights.
    glare = nodes.new("CompositorNodeGlare")
    glare.location = (-150, 0)
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Threshold"].default_value = 1.0
    glare.inputs["Size"].default_value = 0.7
    glare.inputs["Strength"].default_value = 0.6
    links.new(rlayers.outputs["Image"], glare.inputs["Image"])

    output = nodes.new("NodeGroupOutput")
    output.location = (150, 100)
    if not any(
        s.item_type == "SOCKET" and s.in_out == "OUTPUT" and s.name == "Image"
        for s in tree.interface.items_tree
    ):
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    links.new(glare.outputs["Image"], output.inputs["Image"])

    viewer = nodes.new("CompositorNodeViewer")
    viewer.location = (150, -100)
    links.new(glare.outputs["Image"], viewer.inputs["Image"])
    return output
