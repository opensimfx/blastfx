from .registry import get_preset, save_preset_to_json, Preset


def apply_preset(props, preset_id: str) -> None:
    preset = get_preset(preset_id)

    props.preset_id = preset.id
    props.explosion_type = preset.explosion_type

    for key, value in preset.defaults.items():
        if hasattr(props, key):
            setattr(props, key, value)

    component_map = {
        "fireball": "use_fireball",
        "stem": "use_stem",
        "dust": "use_dust",
        "shockwave": "use_shockwave",
        "flash": "use_flash",
        "debris": "use_debris",
    }

    for key, prop_name in component_map.items():
        if key in preset.components and hasattr(props, prop_name):
            setattr(props, prop_name, preset.components[key])

    if "resolution" in preset.simulation:
        props.resolution = preset.simulation["resolution"]

    if "noise" in preset.simulation:
        props.noise_upres = preset.simulation["noise"]


def preset_from_props(props, preset_id: str, label: str, description: str = "") -> Preset:
    """Create a Preset dataclass from current property settings."""
    component_map = {
        "fireball": "use_fireball",
        "stem": "use_stem",
        "dust": "use_dust",
        "shockwave": "use_shockwave",
        "flash": "use_flash",
        "debris": "use_debris",
        "camera_fx": "use_camera_fx",
    }

    defaults = {}
    for key in ["scale", "intensity", "speed", "duration", "seed"]:
        if hasattr(props, key):
            defaults[key] = getattr(props, key)

    components = {}
    for key, prop_name in component_map.items():
        if hasattr(props, prop_name):
            components[key] = getattr(props, prop_name)

    simulation = {}
    if hasattr(props, "resolution"):
        simulation["resolution"] = props.resolution
    if hasattr(props, "noise_upres"):
        simulation["noise"] = props.noise_upres

    return Preset(
        id=preset_id,
        label=label,
        description=description,
        explosion_type=props.explosion_type,
        defaults=defaults,
        components=components,
        simulation=simulation,
    )


def save_current_as_preset(props, preset_id: str, label: str, description: str = "") -> str:
    """Save current settings as a new preset JSON file."""
    preset = preset_from_props(props, preset_id, label, description)
    save_preset_to_json(preset)
    return preset_id
