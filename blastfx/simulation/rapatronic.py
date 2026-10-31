"""Rapatronic skin: the first-milliseconds speckled fireball shell.

Rapatronic cameras photographed nuclear fireballs within microseconds:
a not-yet-smooth glowing surface mottled by vaporized debris specks. The
shell is pure shader (bright specks + transparent elsewhere) with quick
scale/hide keys, so the manta fireball core reads through it and the
shell vanishes once the real simulation takes over.
"""

import bmesh
import bpy

from ..utils.naming import component_name
from ..utils.animation import action_fcurves
from ..materials.rapatronic import build_rapatronic_material
# Frames the skin is visible: rapatronics capture the first ~250 ms.
SKIN_FRAMES = 6
GROW_FROM = 0.35
GROW_TO = 1.15


def build_rapatronic(context, collection, controller, config):
    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "Rapatronic")

    physical = config["physical"]
    radius = physical.characteristic_radius_m
    start = int(config["start_frame"])
    end = start + SKIN_FRAMES

    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=radius * GROW_TO)
    mesh = bpy.data.meshes.new(name + "_Shell")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = controller.location
    obj.data.materials.append(build_rapatronic_material(name + "_Skin", radius))
    obj.hide_viewport = True
    obj.hide_render = True

    # Visible only in [start, end]: hide keys sit constant a frame outside.
    for prop in ("hide_viewport", "hide_render"):
        setattr(obj, prop, True)
        obj.keyframe_insert(prop, frame=start - 1)
        setattr(obj, prop, False)
        obj.keyframe_insert(prop, frame=start)
        setattr(obj, prop, False)
        obj.keyframe_insert(prop, frame=end)
        setattr(obj, prop, True)
        obj.keyframe_insert(prop, frame=end + 1)

    # Sub-frame growth mimics the shell expanding with the blast front.
    obj.scale = (GROW_FROM, GROW_FROM, GROW_FROM)
    obj.keyframe_insert("scale", frame=start)
    obj.scale = (GROW_TO, GROW_TO, GROW_TO)
    obj.keyframe_insert("scale", frame=end)
    for fcurve in action_fcurves(obj):
        if fcurve.data_path == "scale":
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "LINEAR"
        else:
            for keyframe in fcurve.keyframe_points:
                keyframe.interpolation = "CONSTANT"

    obj["blastfx_role"] = "shell"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "rapatronic"
    obj["blastfx_generated"] = True

    return obj
