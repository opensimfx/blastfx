import bpy
import bmesh
from ..utils.naming import component_name
from ..animation.physical_timing import phase_frames


def build_heat_distortion(context, collection, controller, config):
    physical = config["physical"]
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)
    name = component_name(controller["blastfx_id"], "HeatDistortion")
    bm = bmesh.new()
    try:
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=physical.characteristic_radius_m * 0.8)
        mesh = bpy.data.meshes.new(name + "_Mesh")
        bm.to_mesh(mesh)
    finally:
        bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = controller.location
    mat = bpy.data.materials.new(name + "_Mat")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    vol = nodes.new("ShaderNodeVolumePrincipled")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 5.0
    if vol.inputs.get("Density"):
        vol.inputs["Density"].default_value = 0.0
    links.new(vol.outputs["Volume"], out.inputs["Volume"])
    obj.data.materials.append(mat)

    frames = phase_frames(context.scene, int(config["start_frame"]), {
        "rise": duration_s * 0.05,
        "peak": duration_s * 0.3,
        "decay": duration_s * 0.65,
    })
    density = vol.inputs.get("Density")
    if density:
        for frame, value in ((frames["rise"][0],0.0),(frames["rise"][1],0.08),(frames["peak"][1],0.05),(frames["decay"][1],0.0)):
            density.default_value = value
            density.keyframe_insert("default_value", frame=frame)
    obj["blastfx_role"] = "heat_distortion"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "heat_distortion"
    obj["blastfx_generated"] = True
    return obj


def build_heat_distortion_compositor(context, controller, config):
    """Wire up compositor: glare on flash, color grading, denoising, DOF."""
    scene = context.scene
    scene.use_nodes = True
    if scene.compositing_node_group is None:
        tree = bpy.data.node_groups.new("BlastFX_Compositor", "CompositorNodeTree")
        scene.compositing_node_group = tree
    else:
        tree = scene.compositing_node_group
    nodes = tree.nodes
    links = tree.links
    nodes.clear()

    rlayers = nodes.new("CompositorNodeRLayers")
    rlayers.location = (-400, 0)

    # Glare/bloom on bright flash areas.
    glare = nodes.new("CompositorNodeGlare")
    glare.location = (-200, 0)
    glare.inputs["Threshold"].default_value = 0.8
    glare.inputs["Size"].default_value = 8
    links.new(rlayers.outputs["Image"], glare.inputs["Image"])

    # Brightness/contrast for thermal punch.
    bc = nodes.new("CompositorNodeBrightContrast")
    bc.location = (0, 0)
    bc.inputs["Brightness"].default_value = 0.05
    bc.inputs["Contrast"].default_value = 0.1
    links.new(glare.outputs["Image"], bc.inputs["Image"])

    # Hue/saturation for warm thermal tint.
    hue = nodes.new("CompositorNodeHueSat")
    hue.location = (200, 0)
    hue.inputs["Hue"].default_value = 0.52
    hue.inputs["Saturation"].default_value = 1.1
    hue.inputs["Value"].default_value = 1.05
    hue.inputs["Factor"].default_value = 1.0
    links.new(bc.outputs["Image"], hue.inputs["Image"])

    # Denoise (if available).
    denoise = nodes.new("CompositorNodeDenoise")
    denoise.location = (400, 0)
    links.new(hue.outputs["Image"], denoise.inputs["Image"])

    # Viewer for preview (compositor output is the terminal node).
    viewer = nodes.new("CompositorNodeViewer")
    viewer.location = (600, 0)
    links.new(denoise.outputs["Image"], viewer.inputs["Image"])

    return viewer