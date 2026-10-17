import bpy


def _socket(node, name):
    return node.inputs.get(name)


def build_volume_material(name, config):
    """Create a Blender 5.x Principled Volume material driven by Mantaflow grids."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.location = (-220, 0)
    output.location = (120, 0)
    material_type = config.get("type")
    temperature_multiplier = {
        "LARGE": 520.0,
    }.get(material_type, 400.0)
    blackbody_intensity = {
        "LARGE": 0.18,
    }.get(material_type, 0.12)
    density_multiplier = {
        "LARGE": 0.10,
    }.get(material_type, 0.18)
    smoke_color = {
        "LARGE": (0.27, 0.20, 0.13, 1.0),
    }.get(material_type, (0.24, 0.08, 0.025, 1.0))

    # Volume Info is Blender's native interface to Mantaflow gas grids. Its
    # temperature output is normalized by Mantaflow, while Principled Volume
    # expects Kelvin for blackbody emission.
    volume_info = nodes.new("ShaderNodeVolumeInfo")
    density = volume_info.outputs.get("Density")
    temperature = volume_info.outputs.get("Temperature")
    if density is None or temperature is None:
        raise RuntimeError("Blender Volume Info lacks Mantaflow gas grid outputs")
    density_scale = nodes.new("ShaderNodeMath")
    density_scale.operation = "MULTIPLY"
    density_scale.inputs[1].default_value = density_multiplier
    links.new(density, density_scale.inputs[0])
    links.new(density_scale.outputs[0], volume.inputs["Density"])
    temperature_scale = nodes.new("ShaderNodeMath")
    temperature_scale.operation = "MULTIPLY"
    temperature_scale.inputs[1].default_value = temperature_multiplier
    links.new(temperature, temperature_scale.inputs[0])
    links.new(temperature_scale.outputs[0], volume.inputs["Temperature"])
    for socket_name in ("Density Attribute", "Temperature Attribute"):
        sock = _socket(volume, socket_name)
        if sock is not None:
            sock.default_value = ""
    sock = _socket(volume, "Blackbody Intensity")
    if sock is None:
        raise RuntimeError("Principled Volume Blackbody Intensity socket is unavailable")
    sock.default_value = blackbody_intensity
    tint = _socket(volume, "Blackbody Tint")
    if tint is not None:
        tint.default_value = (1.0, 0.18, 0.03, 1.0)
    color = _socket(volume, "Color")
    if color is not None:
        color.default_value = smoke_color
    sock = _socket(volume, "Temperature")
    if sock is None:
        raise RuntimeError("Principled Volume Temperature socket is unavailable")
    sock.default_value = 1000.0
    sock = _socket(volume, "Anisotropy")
    if sock is not None:
        sock.default_value = 0.0

    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    return mat
