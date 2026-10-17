import bpy
from mathutils import Vector
from ..utils.naming import component_name
from ..animation.physical_timing import phase_frames
from ..utils.animation import action_fcurves


def build_camera_fx(context, collection, controller, config):
    physical = config["physical"]
    envelope = config.get("domain_envelope", {})
    profile = config.get("profile")
    camera_factor = getattr(profile, "camera_distance_factor", 1.0)
    envelope_size = Vector(envelope.get("size", (physical.characteristic_radius_m * 6.0,) * 3))
    envelope_center = Vector(envelope.get("center", (0.0, 0.0, physical.characteristic_radius_m)))
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)
    name = component_name(controller["blastfx_id"], "CameraFX")
    frames = phase_frames(context.scene, int(config.get("start_frame", 1)), {
        "rise": duration_s * 0.05,
        "peak": duration_s * 0.20,
        "decay": duration_s * 0.75,
    })
    cam = context.scene.camera
    blast_id = controller["blastfx_id"]
    can_reuse = (
        cam is not None
        and cam.get("blastfx_generated", False)
        and cam.get("blastfx_id") == blast_id
    )
    if not can_reuse:
        data = bpy.data.cameras.new(name + "_Camera")
        cam = bpy.data.objects.new(name, data)
        collection.objects.link(cam)
        if (
            getattr(profile, "ground_surge", False)
            and getattr(profile, "shockwave_radius_factor", 3.0) > 3.0
        ):
            radius = physical.characteristic_radius_m
            cam.location = controller.location + Vector((
                radius * 6.0,
                -radius * 12.0,
                radius * 8.0,
            ))
        else:
            cam.location = controller.location + Vector((
                envelope_size.x * 0.65 * camera_factor,
                envelope_size.y * 0.65 * camera_factor,
                envelope_size.z * 0.45 * camera_factor,
            ))
        context.scene.camera = cam
    cam.data.lens = (
        36.0
        if getattr(profile, "ground_surge", False)
        and getattr(profile, "shockwave_radius_factor", 3.0) > 3.0
        else 50.0
    )
    cam.data.clip_start = max(0.01, physical.characteristic_radius_m * 0.01)
    cam.data.clip_end = max(1000.0, physical.characteristic_radius_m * 100.0)
    if (
        getattr(profile, "ground_surge", False)
        and getattr(profile, "shockwave_radius_factor", 3.0) > 3.0
    ):
        target_offset = Vector((0.0, 0.0, physical.characteristic_radius_m * 1.2))
    else:
        target_offset = envelope_center
    target = controller.location + target_offset
    base = cam.location.copy()
    amount = physical.characteristic_radius_m * 0.02
    keys = [
        (frames["rise"][0], base),
        (frames["rise"][1], base + Vector((amount, -amount*0.5, amount*0.3))),
        (frames["peak"][1], base + Vector((-amount*0.5, amount*0.3, -amount*0.2))),
        (frames["decay"][1], base),
    ]
    for frame, loc in keys:
        cam.location = loc
        cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=frame)
        cam.keyframe_insert("rotation_euler", frame=frame)
    if cam.animation_data and cam.animation_data.action:
        for fc in action_fcurves(cam):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
    cam["blastfx_role"] = "camera_fx"
    cam["blastfx_id"] = controller["blastfx_id"]
    cam["blastfx_component"] = "camera_fx"
    cam["blastfx_generated"] = True
    return cam
