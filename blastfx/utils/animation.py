"""Blender 5.x animation API helpers."""

from bpy_extras import anim_utils


def action_fcurves(id_block):
    """Return the F-Curves for an animated ID datablock in Blender 5.x.

    Blender 5.x stores Action F-Curves in a Channelbag selected by the
    datablock's Action Slot.  This helper centralizes that API detail and
    returns an empty tuple when the datablock has no usable animation.
    """
    anim_data = getattr(id_block, "animation_data", None)
    if anim_data is None:
        return ()

    action = getattr(anim_data, "action", None)
    slot = getattr(anim_data, "action_slot", None)
    if action is None or slot is None:
        return ()

    getter = getattr(anim_utils, "action_get_channelbag_for_slot", None)
    if getter is None:
        return getattr(action, "fcurves", ())
    channelbag = getter(action, slot)
    if channelbag is None:
        return ()

    return channelbag.fcurves
