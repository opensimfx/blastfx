bl_info = {
    "name": "Blast FX",
    "author": "arsh342",
    "version": (0, 2, 0),
    "blender": (5, 2, 0),
    "location": "3D Viewport > Sidebar > Blast FX",
    "description": "Procedural cinematic explosion authoring system",
    "category": "Physics",
}


def register():
    from .addon.registration import register as _register
    _register()


def unregister():
    from .addon.registration import unregister as _unregister
    _unregister()


if __name__ == "__main__":
    register()
