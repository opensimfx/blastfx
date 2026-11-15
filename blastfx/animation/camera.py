import bpy
from mathutils import Vector
from ..utils.naming import component_name
from ..utils.animation import action_fcurves

SPEED_OF_SOUND_MPS = 343.0


def _add_shake(cam, config, distance_m):
    """Blast-wave camera shake: noise on rotation, arriving at sound speed.

    The jolt starts when the blast wave reaches the camera
    (distance / 343 m/s of event time, stretched by slow motion), is
    stronger the closer the camera is relative to the fireball, and decays
    over about a second of event time with a fast, irregular wiggle.
    """
    plan = config["plan"]
    radius = config["physical"].characteristic_radius_m
    start = int(config.get("start_frame", 1))
    distance = max(distance_m, radius)
    arrival = start + int(round(plan.event_frames(distance / SPEED_OF_SOUND_MPS)))
    duration = max(4, int(round(plan.event_frames(1.0))))
    amplitude = max(0.002, min(0.03, 0.25 * radius / distance))  # radians
    period = max(1.0, plan.event_frames(0.06))
    for fcurve in action_fcurves(cam):
        if fcurve.data_path != "rotation_euler" or fcurve.array_index == 1:
            continue
        noise = fcurve.modifiers.new("NOISE")
        noise.strength = amplitude * 2.0
        noise.scale = period
        noise.phase = 7.0 * fcurve.array_index + 1.0
        noise.use_restricted_range = True
        noise.frame_start = arrival
        noise.frame_end = arrival + duration
        noise.blend_in = 1.0
        noise.blend_out = duration * 0.85


# Framing in fireball radii: distance = CAMERA_BASE_R x profile factor,
# looking slightly up at a point CAMERA_TARGET_TOP of the way up the domain.
CAMERA_BASE_R = 6.0
CAMERA_TARGET_TOP = 0.3
CAMERA_ELEVATION = 0.12  # radians above the target


def camera_placement(radius_m, profile):
    """(offset from blast origin, target offset) for the generated camera.

    One rule for every profile in units of R. The old rules mixed a
    radius-based branch (tuned for 0.5 m blasts; it parked the camera ~2.4 R
    out, inside Large Ground's smoke) and an envelope-based one that cropped
    small blasts off the bottom of the frame.
    """
    import math

    distance = CAMERA_BASE_R * float(getattr(profile, "camera_distance_factor", 2.0)) * radius_m
    target_z = CAMERA_TARGET_TOP * float(getattr(profile, "envelope_top_R", 6.0)) * radius_m
    horizontal = distance * math.cos(CAMERA_ELEVATION)
    offset = Vector((-0.6 * horizontal, -0.8 * horizontal,
                     target_z + distance * math.sin(CAMERA_ELEVATION)))
    return offset, Vector((0.0, 0.0, target_z))


def build_camera_fx(context, collection, controller, config):
    physical = config["physical"]
    profile = config.get("profile")
    radius = physical.characteristic_radius_m
    name = component_name(controller["blastfx_id"], "CameraFX")
    cam = context.scene.camera
    blast_id = controller["blastfx_id"]
    can_reuse = (
        cam is not None
        and cam.get("blastfx_generated", False)
        and cam.get("blastfx_id") == blast_id
    )
    offset, target_offset = camera_placement(radius, profile)
    if not can_reuse:
        data = bpy.data.cameras.new(name + "_Camera")
        cam = bpy.data.objects.new(name, data)
        collection.objects.link(cam)
        cam.location = controller.location + offset
        context.scene.camera = cam
    cam.data.lens = 35.0
    cam.data.clip_start = max(0.01, radius * 0.01)
    cam.data.clip_end = max(1000.0, radius * 200.0)
    target = controller.location + target_offset
    base = cam.location.copy()
    start = int(config.get("start_frame", 1))
    cam.rotation_euler = (target - base).to_track_quat("-Z", "Y").to_euler()
    cam.keyframe_insert("location", frame=start)
    cam.keyframe_insert("rotation_euler", frame=start)
    _add_shake(cam, config, (target - base).length)
    cam["blastfx_role"] = "camera_fx"
    cam["blastfx_id"] = controller["blastfx_id"]
    cam["blastfx_component"] = "camera_fx"
    cam["blastfx_generated"] = True
    return cam
