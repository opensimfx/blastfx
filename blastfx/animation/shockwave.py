import math

import bmesh
import bpy

from ..utils.naming import component_name
from ..utils.animation import action_fcurves
from .heat_distortion import _camera_only, build_heat_haze_material

SPEED_OF_SOUND_MPS = 343.0
# Cinematic floor (Tier C): a real shock crosses a small scene in under a
# frame; keep the ripple on screen long enough to read.
MIN_VISIBLE_FRAMES = 3


def _ring_wall(name, height, segments=96):
    """Open cylinder wall of radius 1 standing on z = 0 (scaled in x/y)."""
    bm = bmesh.new()
    try:
        bottom = [bm.verts.new((math.cos(2 * math.pi * i / segments),
                                math.sin(2 * math.pi * i / segments), 0.0)) for i in range(segments)]
        top = [bm.verts.new((v.co.x, v.co.y, height)) for v in bottom]
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
        mesh = bpy.data.meshes.new(name + "_Mesh")
        bm.to_mesh(mesh)
    finally:
        bm.free()
    return mesh


def build_shockwave_geometry(context, collection, controller, config):
    """The visible shock: a refraction ripple sweeping out at sound speed.

    Replaces a flat dusty disc that crawled outward over most of the shot
    (about 1 m/s on small blasts). The shock front is seen as distortion,
    not as a surface; the dust it raises comes from the annulus flow.
    """
    from ..simulation.shockwave import shock_start_frame

    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "ShockwaveRing")
    physical = config["physical"]
    plan = config["plan"]
    profile = config["profile"]
    radius = physical.characteristic_radius_m
    max_radius = radius * float(profile.shockwave_radius_factor)

    obj = bpy.data.objects.new(name, _ring_wall(name, height=radius * 0.35))
    collection.objects.link(obj)
    obj.location = controller.location
    _camera_only(obj)
    material = build_heat_haze_material(name + "_Refraction", radius)
    obj.data.materials.append(material)

    start = shock_start_frame(config)
    travel = max(MIN_VISIBLE_FRAMES, int(round(
        plan.event_frames((max_radius - radius) / SPEED_OF_SOUND_MPS)
    )))
    end = start + travel

    for frame, ring_radius in ((start, radius), (end, max_radius)):
        obj.scale = (ring_radius, ring_radius, 1.0)
        obj.keyframe_insert("scale", frame=frame)
    mix = material.node_tree.nodes["BlastFX Haze Strength"].outputs[0]
    for frame, value in ((start, 1.0), (end, 0.0)):
        mix.default_value = value
        mix.keyframe_insert("default_value", frame=frame)
    for prop in ("hide_render", "hide_viewport"):
        for frame, hidden in ((start - 1, True), (start, False), (end, False), (end + 1, True)):
            setattr(obj, prop, hidden)
            obj.keyframe_insert(prop, frame=frame)
    for fcurve in action_fcurves(obj):
        interpolation = "LINEAR" if fcurve.data_path == "scale" else "CONSTANT"
        for kp in fcurve.keyframe_points:
            kp.interpolation = interpolation

    obj["blastfx_role"] = "shockwave_geometry"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "shockwave"
    obj["blastfx_generated"] = True
    return obj
