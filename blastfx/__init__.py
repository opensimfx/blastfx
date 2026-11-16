"""BlastFX: procedural cinematic explosions for Blender. Metadata lives in blender_manifest.toml."""


def register():
    from .addon.registration import register as _register
    _register()


def unregister():
    from .addon.registration import unregister as _unregister
    _unregister()


if __name__ == "__main__":
    register()
