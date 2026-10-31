import bpy


def build_rapatronic_material(name, radius):
    """Shader-only speck shell for the first-milliseconds nuclear fireball.

    Two Voronoi fields at different scales pick random surface points; a
    mask lights only those points with white-hot Emission, everything else
    stays Transparent so the manta fireball core shows through. (Rapatronic
    cameras recorded vaporized debris specks mottling the early surface.)
    Scales are radius-relative: a cell is ~4% of the fireball, so the
    mottling reads at any yield.
    """
    # Cell size = 1/scale in object coords; radius-relative sizes.
    scale_coarse = 1.0 / max(radius * 0.04, 1e-6)
    scale_fine = 1.0 / max(radius * 0.023, 1e-6)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    mix = nodes.new("ShaderNodeMixShader")

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (1.0, 0.93, 0.78, 1.0)
    emission.inputs["Strength"].default_value = 80.0

    coords = nodes.new("ShaderNodeTexCoord")
    v1 = nodes.new("ShaderNodeTexVoronoi")
    v1.inputs["Scale"].default_value = scale_coarse
    v2 = nodes.new("ShaderNodeTexVoronoi")
    v2.inputs["Scale"].default_value = scale_fine

    closest = nodes.new("ShaderNodeMath")
    closest.operation = "MINIMUM"

    mask = nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = 0.0
    # Voronoi distances are normalized to cell size now (cells ~1.0 wide);
    # only points well inside a cell read as a speck, or the shell lights.
    mask.inputs["From Max"].default_value = 0.08
    mask.inputs["To Min"].default_value = 1.0
    mask.inputs["To Max"].default_value = 0.0

    links.new(coords.outputs["Object"], v1.inputs["Vector"])
    links.new(coords.outputs["Object"], v2.inputs["Vector"])
    links.new(v1.outputs["Distance"], closest.inputs[0])
    links.new(v2.outputs["Distance"], closest.inputs[1])
    links.new(closest.outputs[0], mask.inputs["Value"])
    links.new(mask.outputs["Result"], mix.inputs["Fac"])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])

    return mat
