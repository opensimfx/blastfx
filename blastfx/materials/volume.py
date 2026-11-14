import bpy


def _socket(node, name):
    return node.inputs.get(name)


def _require(socket, what, node, name):
    if socket is None:
        raise RuntimeError(f"Blender 5.2 nodes lack {what} ({name})")
    return socket


def _configure_ramp(color_ramp, stops):
    """Map ((position, rgba), ...) stops onto a ValToRGB ramp."""
    elements = color_ramp.color_ramp.elements
    while len(elements) < len(stops):
        elements.new(stops[len(elements)][0])
    while len(elements) > len(stops):
        elements.remove(elements[-1])
    for index, (position, color) in enumerate(stops):
        element = elements[index]
        element.position = position
        element.color = color


def _math(nodes, operation, value, location):
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.inputs[1].default_value = value
    node.location = location
    return node


def build_volume_material(name, config):
    """Scale-free Mantaflow volume material (see ShadingConfig).

    Smoke: density grid x (optical_depth / R) is the extinction per metre,
    so the smoke reads the same at every blast size; a density ColorRamp
    sets the scattering albedo. Fire: flame grid -> temperature -> Blackbody
    colour; emission = extinction x fire_brightness x flame**gamma.
    """
    shading = config["shading"]
    radius = max(float(config["physical"].characteristic_radius_m), 1e-6)
    view = getattr(getattr(bpy.context.scene, "view_settings", None), "view_transform", "")
    agx = str(view).startswith("AgX")

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (500, 0)
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.location = (240, 0)

    info = nodes.new("ShaderNodeVolumeInfo")
    info.location = (-700, 0)
    density_out = _require(info.outputs.get("Density"), "Mantaflow density grid", info, "volume_info")
    flame_out = _require(info.outputs.get("Flame"), "Mantaflow flame grid", info, "volume_info")

    # --- Smoke: extinction per metre, normalised by the fireball radius.
    density_scale = _math(nodes, "MULTIPLY", shading.optical_depth / radius, (-420, 40))
    links.new(density_out, density_scale.inputs[0])
    links.new(density_scale.outputs[0], _require(
        _socket(volume, "Density"), "volume density socket", volume, "density",
    ))

    # Albedo by local density: thin edges scatter light, dense soot absorbs.
    ramp_gain = _math(nodes, "MULTIPLY", shading.ramp_gain, (-420, 220))
    links.new(density_out, ramp_gain.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-240, 220)
    _configure_ramp(ramp, shading.smoke_ramp)
    links.new(ramp_gain.outputs[0], ramp.inputs["Fac"])
    # Burning soot is black and glows by its own emission: darken the albedo
    # where flame is present, or the scattered sky turns the fire pink.
    soot = _math(nodes, "MULTIPLY", shading.burning_soot, (-240, 380))
    links.new(flame_out, soot.inputs[0])
    unburnt = nodes.new("ShaderNodeMath")
    unburnt.operation = "SUBTRACT"
    unburnt.use_clamp = True
    unburnt.inputs[0].default_value = 1.0
    unburnt.location = (-60, 380)
    links.new(soot.outputs[0], unburnt.inputs[1])
    albedo = nodes.new("ShaderNodeVectorMath")
    albedo.operation = "SCALE"
    albedo.location = (60, 220)
    links.new(ramp.outputs["Color"], albedo.inputs[0])
    links.new(unburnt.outputs[0], albedo.inputs["Scale"])
    links.new(albedo.outputs["Vector"], _require(
        _socket(volume, "Color"), "volume color socket", volume, "color",
    ))

    # --- Fire: blackbody colour from a flame-mapped temperature.
    low_k, high_k = shading.fire_temperature_k
    to_kelvin = nodes.new("ShaderNodeMapRange")
    to_kelvin.location = (-420, -220)
    to_kelvin.clamp = True
    to_kelvin.inputs["From Min"].default_value = 0.0
    to_kelvin.inputs["From Max"].default_value = 1.0
    to_kelvin.inputs["To Min"].default_value = low_k
    to_kelvin.inputs["To Max"].default_value = high_k
    links.new(flame_out, to_kelvin.inputs["Value"])
    blackbody = nodes.new("ShaderNodeBlackbody")
    blackbody.location = (-240, -220)
    links.new(to_kelvin.outputs["Result"], blackbody.inputs["Temperature"])
    # AgX compensation (see ShadingConfig.agx_*); neutral for other views.
    grade = nodes.new("ShaderNodeHueSaturation")
    grade.name = "BlastFX Fire Grade"
    grade.location = (-60, -220)
    grade.inputs["Hue"].default_value = 0.5 + (shading.agx_hue_shift if agx else 0.0)
    grade.inputs["Saturation"].default_value = shading.agx_saturation if agx else 1.0
    links.new(blackbody.outputs["Color"], grade.inputs["Color"])
    links.new(grade.outputs["Color"], _require(
        _socket(volume, "Emission Color"), "volume emission color socket", volume, "emission_color",
    ))

    # Strength follows Kirchhoff's law: a volume emits in proportion to how
    # strongly it absorbs. Emission = extinction x brightness x flame**gamma,
    # so an optically thick burning core glows at ``fire_brightness`` at any
    # size and density (per-metre emission left dense fireballs as dim as
    # the sky, measured), while thin flame edges stay dim.
    gamma = _math(nodes, "POWER", shading.fire_gamma, (-420, -420))
    links.new(flame_out, gamma.inputs[0])
    brightness = _math(
        nodes, "MULTIPLY",
        shading.fire_brightness * (shading.agx_brightness if agx else 1.0), (-240, -420),
    )
    links.new(gamma.outputs[0], brightness.inputs[0])
    strength = nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.location = (-60, -420)
    links.new(brightness.outputs[0], strength.inputs[0])
    links.new(density_scale.outputs[0], strength.inputs[1])
    links.new(strength.outputs[0], _require(
        _socket(volume, "Emission Strength"), "volume emission strength socket", volume, "emission_strength",
    ))

    # The flame-driven emission replaces Principled's own blackbody path.
    blackbody_intensity = _socket(volume, "Blackbody Intensity")
    if blackbody_intensity is not None:
        blackbody_intensity.default_value = 0.0
    for socket_name in ("Density Attribute", "Temperature Attribute"):
        sock = _socket(volume, socket_name)
        if sock is not None:
            sock.default_value = ""
    anisotropy = _socket(volume, "Anisotropy")
    if anisotropy is not None:
        anisotropy.default_value = shading.anisotropy

    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    return mat
