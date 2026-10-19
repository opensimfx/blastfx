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
        elements.new(len(elements) and stops[len(elements)][0] or 0.0)
    for index, (position, color) in enumerate(stops):
        element = elements[index]
        element.position = position
        element.color = color


def build_volume_material(name, config):
    """Blender 5.x volume material: flame-grid fire + ramped smoke on grids.

    Smoke: Volume Info Density drives a ColorRamp (thin light wisps -> dense
    near-black core) with a Fresnel lightening pass on thin edges; Density is
    scaled per profile. Fire: the `flame` grid (Mantaflow burning) drives the
    Principled Volume emission sockets; the temperature/Blackbody path stays
    wired for calibration but ships off (double fire exposure otherwise).
    """
    shading = config["shading"]

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (420, 0)
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume.location = (160, 0)

    info = nodes.new("ShaderNodeVolumeInfo")
    info.location = (-620, 0)
    density_out = _require(
        info.outputs.get("Density"), "Mantaflow density grid", info, "volume_info",
    )
    flame_out = info.outputs.get("Flame")
    temperature_out = info.outputs.get("Temperature")
    if temperature_out is None:
        raise RuntimeError("Blender Volume Info lacks Mantaflow temperature grid")

    # Smoke color ramp: raw density (Manta grids peak well below 1.0) scaled
    # up so the ramp samples across its whole range -> ramp color.
    ramp_gain = nodes.new("ShaderNodeMath")
    ramp_gain.location = (-500, 120)
    ramp_gain.operation = "MULTIPLY"
    ramp_gain.inputs[1].default_value = 2.5
    links.new(density_out, ramp_gain.inputs[0])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (-380, 120)
    _configure_ramp(ramp, shading.smoke_ramp)
    links.new(ramp_gain.outputs[0], ramp.inputs["Fac"])

    volume.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    # Fresnel lightening on thin edges (CrossMind trick): grazing-angle
    # regions mix toward the ramp's light end so the silhouette stays soft.
    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.location = (-620, -160)
    fresnel = nodes.new("ShaderNodeFresnel")
    fresnel.location = (-620, -320)
    fresnel.inputs["IOR"].default_value = 1.45
    links.new(geometry.outputs["Normal"], fresnel.inputs["Normal"])
    fresnel_scale = nodes.new("ShaderNodeMath")
    fresnel_scale.location = (-380, -320)
    fresnel_scale.operation = "MULTIPLY"
    fresnel_scale.inputs[1].default_value = 0.35
    links.new(fresnel.outputs.get("Fac"), fresnel_scale.inputs[0])
    try:
        edge_mix = nodes.new("ShaderNodeMixRGB")
        color1_socket, color2_socket, fac_socket = "Color1", "Color2", "Fac"
    except RuntimeError:
        # Newer Blender renamed the legacy MixRGB to ShaderNodeMix (RGBA).
        edge_mix = nodes.new("ShaderNodeMix")
        edge_mix.data_type = "RGBA"
        color1_socket, color2_socket, fac_socket = "A", "B", "Factor"
    edge_mix.location = (-160, -160)
    edge_mix.blend_type = "SCREEN"
    links.new(fresnel_scale.outputs[0], edge_mix.inputs[fac_socket])
    links.new(ramp.outputs["Color"], edge_mix.inputs[color1_socket])
    edge_mix.inputs[color2_socket].default_value = (0.40, 0.38, 0.34, 1.0)
    links.new(edge_mix.outputs.get("Color"), _socket(volume, "Color"))

    # Density socket: raw grid scaled by the profile multiplier.
    density_scale = nodes.new("ShaderNodeMath")
    density_scale.location = (-380, 0)
    density_scale.operation = "MULTIPLY"
    density_scale.inputs[1].default_value = shading.density_multiplier
    links.new(density_out, density_scale.inputs[0])
    links.new(density_scale.outputs[0], _require(
        _socket(volume, "Density"), "volume density socket", volume, "density",
    ))

    # Fire: flame grid -> Emission Strength (multiplied), orange color.
    if flame_out is not None:
        flame_scale = nodes.new("ShaderNodeMath")
        flame_scale.location = (-380, -520)
        flame_scale.operation = "MULTIPLY"
        flame_scale.inputs[1].default_value = shading.flame_multiplier
        links.new(flame_out, flame_scale.inputs[0])
        links.new(flame_scale.outputs[0], _require(
            _socket(volume, "Emission Strength"),
            "volume emission strength socket", volume, "emission_strength",
        ))
        emission_color = _socket(volume, "Emission Color")
        _require(emission_color, "volume emission color socket", volume, "emission_color")
        emission_color.default_value = shading.flame_color

    # Blackbody path wired (Kelvin-scaled temperature grid) but intensity 0
    # by default: flame emission already carries the fire (calibration note).
    temperature_scale = nodes.new("ShaderNodeMath")
    temperature_scale.location = (-380, -140)
    temperature_scale.operation = "MULTIPLY"
    temperature_scale.inputs[1].default_value = shading.temperature_multiplier
    links.new(temperature_out, temperature_scale.inputs[0])
    temperature_socket = _socket(volume, "Temperature")
    _require(temperature_socket, "volume temperature socket", volume, "temperature")
    temperature_socket.default_value = 1000.0
    links.new(temperature_scale.outputs[0], temperature_socket)
    blackbody_socket = _socket(volume, "Blackbody Intensity")
    _require(blackbody_socket, "volume blackbody socket", volume, "blackbody")
    blackbody_socket.default_value = shading.blackbody_intensity
    tint = _socket(volume, "Blackbody Tint")
    if tint is not None:
        tint.default_value = (1.0, 0.18, 0.03, 1.0)

    for socket_name in ("Density Attribute", "Temperature Attribute"):
        sock = _socket(volume, socket_name)
        if sock is not None:
            sock.default_value = ""
    anisotropy = _socket(volume, "Anisotropy")
    if anisotropy is not None:
        anisotropy.default_value = shading.anisotropy

    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    return mat
