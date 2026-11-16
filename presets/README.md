# Presets

Built-in presets live in code:

`blastfx/presets/registry.py`

JSON files in this directory (e.g. `medium.json`, `large_ground.json`) are
loaded when BlastFX runs from source (development, tests). Installed as an
extension, **Save as Preset** writes to the add-on's user data folder instead
(`bpy.utils.extension_path_user`). The `simulation` dictionary accepts
either `resolution` (built-in style) or the legacy `preview_resolution` /
`final_resolution` key pair; `presets/apply.py` resolves both.

Do not duplicate the same defaults in UI code.
