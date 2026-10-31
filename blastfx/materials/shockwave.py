import bpy
from math import cos, pi, sin


def build_shockwave_ring_mesh(name, radius, segments=128, thickness=0.32):
    """Create a thin, slightly irregular, renderable annular dust-front mesh."""
    vertices = []
    faces = []
    inner_radius = radius * (1.0 - thickness)
    for ring_radius in (inner_radius, radius):
        for index in range(segments):
            angle = 2.0 * pi * index / segments
            irregularity = (
                1.0
                + 0.035 * sin(3.0 * angle + 0.4)
                + 0.018 * sin(7.0 * angle - 0.8)
                + 0.012 * cos(11.0 * angle + 1.1)
            )
            current_radius = ring_radius * irregularity
            vertices.append((current_radius * cos(angle), current_radius * sin(angle), 0.0))
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append((index, next_index, segments + next_index, segments + index))
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def build_shockwave_material(name, config):
    """Build a translucent, noise-broken dusty front for the expanding ring."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    dust = nodes.new("ShaderNodeBsdfPrincipled")
    dust.inputs["Base Color"].default_value = (0.30, 0.22, 0.14, 1.0)
    dust.inputs["Roughness"].default_value = 1.0
    emission = dust.inputs.get("Emission Color")
    if emission is not None:
        emission.default_value = (0.40, 0.28, 0.16, 1.0)
    emission_strength = dust.inputs.get("Emission Strength")
    if emission_strength is not None:
        emission_strength.default_value = 0.8
    texcoord = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.72
    links.new(texcoord.outputs["Generated"], noise.inputs["Vector"])
    alpha = nodes.new("ShaderNodeMapRange")
    alpha.clamp = True
    alpha.inputs["From Min"].default_value = 0.28
    alpha.inputs["From Max"].default_value = 0.78
    alpha.inputs["To Min"].default_value = 0.10
    alpha.inputs["To Max"].default_value = 0.42
    links.new(noise.outputs["Fac"], alpha.inputs["Value"])
    mix = nodes.new("ShaderNodeMixShader")
    links.new(alpha.outputs["Result"], mix.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix.inputs[1])
    links.new(dust.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat
