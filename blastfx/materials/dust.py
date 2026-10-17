import bpy


def build_dust_material(name, config):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.18, 0.14, 0.10, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
    return mat
