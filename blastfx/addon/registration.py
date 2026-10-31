import bpy

from .properties import register_properties, unregister_properties
from .operators import CLASSES as OPERATOR_CLASSES
from ..ui.panel import CLASSES as UI_CLASSES
from ..core.cache import recover_caches


def _recover_caches_on_load(*_args):
    # Runs inside a load_post handler: recovery must never abort file opening.
    try:
        recover_caches(bpy.context)
    except Exception as exc:
        print(f"Blast FX cache recovery skipped: {exc}")


def register():
    register_properties()

    for cls in OPERATOR_CLASSES:
        bpy.utils.register_class(cls)

    for cls in UI_CLASSES:
        bpy.utils.register_class(cls)

    if _recover_caches_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_recover_caches_on_load)


def unregister():
    for cls in reversed(UI_CLASSES):
        bpy.utils.unregister_class(cls)

    for cls in reversed(OPERATOR_CLASSES):
        bpy.utils.unregister_class(cls)

    if _recover_caches_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_recover_caches_on_load)

    unregister_properties()
