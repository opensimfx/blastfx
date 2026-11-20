from .registry import get_preset, save_preset_to_json, Preset


# The only settings a preset may carry. A saved preset is a JSON file anyone can share, so it must not be able to
# set unrelated scene settings (the cache folder, for instance); a value of the wrong type is skipped.
DEFAULT_KEYS = ("scale", "intensity", "speed", "duration", "seed", "yield_kt")
COMPONENT_MAP = {
    "fireball": "use_fireball",
    "stem": "use_stem",
    "dust": "use_dust",
    "shockwave": "use_shockwave",
    "flash": "use_flash",
    "debris": "use_debris",
    "camera_fx": "use_camera_fx",
    "rapatronic": "use_rapatronic",
}


def _set(props, name: str, value) -> None:
    if not hasattr(props, name):
        return
    try:
        setattr(props, name, value)
    except (TypeError, ValueError) as exc:
        print(f"[BlastFX] Preset value for {name!r} ignored: {exc}")


def apply_preset(props, preset_id: str) -> None:
    preset = get_preset(preset_id)

    props.preset_id = preset.id
    props.explosion_type = preset.explosion_type

    for key in DEFAULT_KEYS:
        if key in preset.defaults:
            _set(props, key, preset.defaults[key])

    for key, prop_name in COMPONENT_MAP.items():
        if key in preset.components:
            _set(props, prop_name, bool(preset.components[key]))

    if "resolution" in preset.simulation:
        resolution = preset.simulation["resolution"]
    else:
        # JSON presets carry preview/final keys; prefer final as the base
        # resolution (quality factor still scales it at build time).
        resolution = preset.simulation.get(
            "final_resolution",
            preset.simulation.get("preview_resolution"),
        )

    if resolution is not None:
        # Draft previews at half the preset resolution immediately, so the
        # build-time quality factor never halves manual resolution edits.
        if getattr(props, "quality", "") == "DRAFT" and isinstance(resolution, (int, float)):
            resolution = max(16, int(resolution * 0.5))
        _set(props, "resolution", resolution)
    else:
        # No pinned resolution: clear any old override so the size-derived
        # automatic resolution applies (0 = auto).
        props.resolution = 0

    if "noise" in preset.simulation:
        _set(props, "noise_upres", preset.simulation["noise"])


def preset_from_props(props, preset_id: str, label: str, description: str = "") -> Preset:
    """Create a Preset dataclass from current property settings."""
    component_map = COMPONENT_MAP

    defaults = {}
    for key in DEFAULT_KEYS:
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
