import bpy
from mathutils import Vector

from ..utils.naming import component_name
from ..materials.shockwave import build_shockwave_material, build_shockwave_ring_mesh
from ..utils.animation import action_fcurves


def animate_shockwave(obj, start_frame, end_frame, config, max_radius_factor=None):
    """Expand and fade the dust front after the profile's shockwave delay."""
    physical = config["physical"]
    radius = physical.characteristic_radius_m
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)
    fps = config.get("_fps", 24.0)
    profile = config.get("profile")
    delay = max(0.0, min(0.9, float(getattr(profile, "shockwave_delay", 0.0))))
    total_frames = max(1.0, duration_s * fps)
    rise_start = start_frame + total_frames * delay
    end_fraction = max(
        delay + 0.01,
        min(1.0, float(getattr(profile, "shockwave_end_fraction", 1.0))),
    )
    fade_end = start_frame + total_frames * end_fraction
    remaining_frames = max(1.0, fade_end - rise_start)
    rise_end = rise_start + remaining_frames * 0.04
    expand_end = rise_start + remaining_frames * 0.62
    if max_radius_factor is None:
        max_radius_factor = float(getattr(profile, "shockwave_radius_factor", 3.0))
    max_radius = radius * max_radius_factor

    obj.scale = Vector((max_radius * 0.015, max_radius * 0.015, 0.01))
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=max(start_frame, rise_start - 1))
    obj.keyframe_insert("hide_render", frame=max(start_frame, rise_start - 1))
    obj.hide_viewport = False
    obj.hide_render = False
    obj.keyframe_insert("hide_viewport", frame=rise_start)
    obj.keyframe_insert("hide_render", frame=rise_start)
    obj.keyframe_insert("scale", frame=rise_start)

    obj.scale = Vector((max_radius * 0.22, max_radius * 0.22, 0.01))
    obj.keyframe_insert("scale", frame=rise_end)
    obj.scale = Vector((max_radius, max_radius, 0.01))
    obj.keyframe_insert("scale", frame=expand_end)
    obj.scale = Vector((max_radius * 1.2, max_radius * 1.2, 0.01))
    obj.keyframe_insert("scale", frame=fade_end)
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert("hide_viewport", frame=fade_end + 1)
    obj.keyframe_insert("hide_render", frame=fade_end + 1)

    # Set interpolation
    for fcurve in action_fcurves(obj):
        for kp in fcurve.keyframe_points:
            kp.interpolation = "LINEAR"


def build_shockwave_geometry(context, collection, controller, config):
    """Create the shockwave ring mesh object."""
    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "ShockwaveRing")

    physical = config["physical"]
    radius = physical.characteristic_radius_m
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)

    mesh = build_shockwave_ring_mesh(name, radius=1.0)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = controller.location
    obj.location.z += max(radius * 0.012, 0.01)
    obj.data.materials.append(build_shockwave_material(name + "_Dust", config))

    obj["blastfx_role"] = "shockwave_geometry"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "shockwave"
    obj["blastfx_generated"] = True

    # Animate it
    config["_fps"] = context.scene.render.fps / context.scene.render.fps_base
    start_frame = int(config.get("start_frame", 1))
    animate_shockwave(
        obj, start_frame, start_frame + int(duration_s * config["_fps"]), config
    )

    return obj
