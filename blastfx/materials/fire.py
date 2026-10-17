import bpy


def build_fire_material(name, config):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 0.18, 0.015, 1.0)
    emission.inputs["Strength"].default_value = 8.0
    links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat
