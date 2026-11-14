import bpy
from ..utils.animation import action_fcurves

from ..utils.naming import component_name

# Light energy per R^2 (W / m^2): inverse-square falloff means a light that
# reads the same at every blast size must scale with the radius squared.
# The glow is the fire lighting its own smoke; the flash is the detonation.
FLASH_W_PER_R2 = 2400.0
GLOW_W_PER_R2 = 260.0


def _keys(light_data, keys):
    for frame, energy in keys:
        light_data.energy = energy
        light_data.keyframe_insert("energy", frame=frame)


def build_flash(context, collection, controller, config):
    """Fire light: a 1-2 frame detonation flash, then the fire's glow.

    Timing follows the event, not the shot: the flash peaks one frame after
    detonation and the glow fades over the profile's fire lifetime
    (shading.fire_light_T, measured from the flame grid per profile). The
    old pulse took 5 % of the shot to rise and lasted 35 % of it at a fixed
    50 kW per metre, which washed out every frame.
    """
    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "Flash")
    physical = config["physical"]
    plan = config["plan"]
    shading = config["shading"]
    radius = physical.characteristic_radius_m
    T = physical.time_unit_s
    start = int(config.get("start_frame", 1))

    def frame_at(event_T):
        return start + max(1, int(round(plan.event_frames(event_T * T))))

    light_data = bpy.data.lights.new(name=name + "_Light", type="POINT")
    light_data.use_temperature = True
    light_data.temperature = shading.fire_light_k
    light_data.shadow_soft_size = radius * 0.4
    light_obj = bpy.data.objects.new(name, light_data)
    collection.objects.link(light_obj)
    light_obj.location = controller.location
    light_obj.location.z += radius * 0.5

    flash = FLASH_W_PER_R2 * radius * radius
    glow = GLOW_W_PER_R2 * radius * radius
    peak = start + 1
    keys = [(start - 1, 0.0), (start, 0.0), (peak, flash)]
    if config.get("type") == "NUCLEAR":
        # Double flash: the shock front overtakes and hides the fireball,
        # then it breaks back out (bhangmeter signature).
        keys += [(max(peak + 1, frame_at(0.11)), flash * 0.35),
                 (max(peak + 2, frame_at(0.22)), flash * 1.1)]
    glow_start = max(keys[-1][0] + 1, frame_at(0.15))
    glow_end = max(glow_start + 1, frame_at(shading.fire_light_T))
    keys += [(glow_start, glow), (glow_end, 0.0)]
    _keys(light_data, keys)

    for fcurve in action_fcurves(light_data):
        for kp in fcurve.keyframe_points:
            kp.interpolation = "LINEAR"

    light_obj["blastfx_role"] = "flash"
    light_obj["blastfx_id"] = blast_id
    light_obj["blastfx_component"] = "flash"
    light_obj["blastfx_generated"] = True

    return light_obj
