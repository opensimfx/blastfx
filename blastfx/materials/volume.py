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


# Artist look layer on top of the physical fire (material only: never touches the bake). Defaults are neutral, so
# a blast renders exactly as the physical shader alone.
LOOK_DEFAULTS = {"fire_exposure": 0.0, "fire_contrast": 1.0, "flame_breakup": 0.0, "fire_light_scene": 1.0}
LOOK_TAG = "blastfx_volume_material"
BREAKUP_NOISE_SCALE = 1.5      # features ~ the fire's depth: emission sums along each ray, so smaller holes average out
CONTRAST_PIVOT = 0.12          # flame**gamma value contrast pivots on (a typical visible flame keeps its brightness)
BREAKUP_FLICKER_PER_S = 1.5    # how fast the break-up pattern evolves (noise W per second)


def _look_nodes(mat):
    nodes = mat.node_tree.nodes
    return {k: nodes.get(f"BlastFX {k}") for k in ("Exposure", "Contrast", "Contrast Pivot", "Breakup", "Light Scene")}


def apply_fire_look(mat, fire_exposure=0.0, fire_contrast=1.0, flame_breakup=0.0, fire_light_scene=1.0):
    """Set the look layer of a BlastFX volume material; returns False if it has none (built by an older version)."""
    n = _look_nodes(mat)
    if any(v is None for v in n.values()):
        return False
    n["Exposure"].outputs[0].default_value = 2.0 ** float(fire_exposure)
    c = max(float(fire_contrast), 0.01)
    n["Contrast"].inputs[1].default_value = c
    n["Contrast Pivot"].inputs[1].default_value = CONTRAST_PIVOT ** (1.0 - c)  # (x / pivot)^c x pivot
    n["Breakup"].inputs[0].default_value = min(max(float(flame_breakup), 0.0), 1.0)
    n["Light Scene"].inputs["A"].default_value = max(float(fire_light_scene), 0.0)
    return True


def apply_fire_look_to_scene(scene, props):
    """Push the scene's look settings to every BlastFX volume material; returns how many were updated."""
    values = {k: getattr(props, k, v) for k, v in LOOK_DEFAULTS.items()}
    count = 0
    for mat in bpy.data.materials:
        if mat.get(LOOK_TAG) and mat.node_tree is not None and apply_fire_look(mat, **values):
            count += 1
    return count


def _build_look_layer(mat, nodes, links, flame_power, strength_out, radius):
    """flame**gamma -> contrast about a pivot; strength x 2^exposure x break-up mask x (camera ? 1 : light scene)."""
    contrast = _math(nodes, "POWER", 1.0, (-240, -600))
    contrast.name = "BlastFX Contrast"
    links.new(flame_power.outputs[0], contrast.inputs[0])
    pivot = _math(nodes, "MULTIPLY", 1.0, (-60, -600))
    pivot.name = "BlastFX Contrast Pivot"
    links.new(contrast.outputs[0], pivot.inputs[0])

    exposure = nodes.new("ShaderNodeValue")
    exposure.name = "BlastFX Exposure"
    exposure.location = (-240, -760)
    exposure.outputs[0].default_value = 1.0

    # Break-up: 4D noise in world space / R (scale-free), evolving over time; the fire moving through it flickers.
    geo = nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1060, -900)
    per_r = nodes.new("ShaderNodeVectorMath")
    per_r.operation = "SCALE"
    per_r.location = (-880, -900)
    per_r.inputs["Scale"].default_value = 1.0 / max(radius, 1e-6)
    links.new(geo.outputs["Position"], per_r.inputs[0])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.location = (-700, -900)
    noise.inputs["Scale"].default_value = BREAKUP_NOISE_SCALE
    noise.inputs["Detail"].default_value = 3.0
    links.new(per_r.outputs["Vector"], noise.inputs["Vector"])
    try:  # simple-expression driver: runs without Python auto-exec
        fcurve = noise.inputs["W"].driver_add("default_value")
        fcurve.driver.type = "SCRIPTED"
        fcurve.driver.expression = f"frame / fps * {BREAKUP_FLICKER_PER_S}"
        var = fcurve.driver.variables.new()
        var.name = "fps"
        var.type = "CONTEXT_PROP"
        var.targets[0].context_property = "ACTIVE_SCENE"
        var.targets[0].data_path = "render.fps"
    except (AttributeError, TypeError, RuntimeError):
        pass
    mask = nodes.new("ShaderNodeMapRange")
    mask.interpolation_type = "SMOOTHSTEP"
    mask.location = (-520, -900)
    mask.inputs["From Min"].default_value = 0.44
    mask.inputs["From Max"].default_value = 0.56
    links.new(noise.outputs["Fac"], mask.inputs["Value"])
    breakup = nodes.new("ShaderNodeMix")
    breakup.data_type = "FLOAT"
    breakup.name = "BlastFX Breakup"
    breakup.location = (-340, -900)
    breakup.inputs[0].default_value = 0.0
    breakup.inputs["A"].default_value = 1.0
    links.new(mask.outputs["Result"], breakup.inputs["B"])

    # Light Scene: camera rays see the fire at full strength; every other ray (lighting the ground, the smoke and
    # the scene) sees it x this factor. Cycles only; EEVEE has no ray types for volumes.
    path = nodes.new("ShaderNodeLightPath")
    path.location = (-520, -1100)
    light = nodes.new("ShaderNodeMix")
    light.data_type = "FLOAT"
    light.name = "BlastFX Light Scene"
    light.location = (-340, -1100)
    light.inputs["A"].default_value = 1.0
    light.inputs["B"].default_value = 1.0
    links.new(path.outputs["Is Camera Ray"], light.inputs[0])

    out = strength_out
    for i, factor in enumerate((exposure.outputs[0], breakup.outputs["Result"], light.outputs["Result"])):
        m = _math(nodes, "MULTIPLY", 1.0, (40 + 0 * i, -600 - 160 * i))
        links.new(out, m.inputs[0])
        links.new(factor, m.inputs[1])
        out = m.outputs[0]
    return pivot, out


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
    strength = nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.location = (-60, -420)
    links.new(brightness.outputs[0], strength.inputs[0])
    links.new(density_scale.outputs[0], strength.inputs[1])
    contrast, graded = _build_look_layer(mat, nodes, links, gamma, strength.outputs[0], radius)
    links.new(contrast.outputs[0], brightness.inputs[0])
    links.new(graded, _require(
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
    mat[LOOK_TAG] = True
    apply_fire_look(mat, **{k: config.get("look", {}).get(k, v) for k, v in LOOK_DEFAULTS.items()})
    return mat
