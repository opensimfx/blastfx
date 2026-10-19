# Presets

Built-in presets live in code:

`blastfx/presets/registry.py`

JSON files in this directory (e.g. `medium.json`, `large_ground.json`) are
user-external overrides loaded on import. The `simulation` dictionary accepts
either `resolution` (built-in style) or the legacy `preview_resolution` /
`final_resolution` key pair; `presets/apply.py` resolves both.

Do not duplicate the same defaults in UI code.
