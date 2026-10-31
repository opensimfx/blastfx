import bpy
from mathutils import Color
from ..utils.animation import action_fcurves

from ..utils.naming import component_name
from ..animation.physical_timing import phase_frames


def build_flash(context, collection, controller, config):
    """Create and animate the explosion light pulse."""
    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "Flash")

    physical = config["physical"]
    start_frame = int(config.get("start_frame", 1))
    duration_s = config.get("timeline_duration_s", physical.characteristic_time_s)

    phases = {
        "flash_rise": duration_s * 0.05,
        "flash_peak": duration_s * 0.1,
        "flash_decay": duration_s * 0.35,
    }
    frames = phase_frames(context.scene, start_frame, phases)

    light_data = bpy.data.lights.new(name=name + "_Light", type="POINT")
    light_data.color = Color((1.0, 0.85, 0.4))
    light_data.energy = 0.0
    light_data.shadow_soft_size = 0.0

    light_obj = bpy.data.objects.new(name, light_data)
    collection.objects.link(light_obj)
    light_obj.location = controller.location
    light_obj.location.z += physical.characteristic_radius_m * 0.5

    # Animate energy: 0 -> peak -> 0
    peak_energy = physical.characteristic_radius_m * 50000.0

    fps = context.scene.render.fps / context.scene.render.fps_base
    light_data.keyframe_insert("energy", frame=frames["flash_rise"][0])
    light_data.energy = peak_energy
    light_data.keyframe_insert("energy", frame=frames["flash_rise"][1])

    # Nuclear double flash: the shock front overtakes and obscures the
    # fireball, so the light dips after the peak and re-brightens when the
    # fireball breaks back out (bhangmeter signature).
    if config.get("type") == "NUCLEAR":
        rise_end = frames["flash_rise"][1]
        dip = rise_end + max(1, round(0.02 * fps * duration_s))
        rebrighten = rise_end + max(1, round(0.04 * fps * duration_s))
        light_data.energy = peak_energy * 0.35
        light_data.keyframe_insert("energy", frame=dip)
        light_data.energy = peak_energy * 1.1
        light_data.keyframe_insert("energy", frame=rebrighten)

    light_data.energy = peak_energy * 0.8
    light_data.keyframe_insert("energy", frame=frames["flash_peak"][1])
    light_data.energy = 0.0
    light_data.keyframe_insert("energy", frame=frames["flash_decay"][1])

    # Set interpolation for smooth flash
    for fcurve in action_fcurves(light_data):
        for kp in fcurve.keyframe_points:
            kp.interpolation = "BEZIER"

    light_obj["blastfx_role"] = "flash"
    light_obj["blastfx_id"] = blast_id
    light_obj["blastfx_component"] = "flash"
    light_obj["blastfx_generated"] = True

    return light_obj
