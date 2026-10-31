import bpy
from mathutils import Vector


def build_ground_dust_fill(context, collection, controller, config):
    """Backlight the Large Ground smoke and dust front throughout its event."""
    radius = config["physical"].characteristic_radius_m
    name = f"Blast_{controller['blastfx_id']}_GroundDustFill"
    data = bpy.data.lights.new(name=name + "_Light", type="AREA")
    data.energy = max(400.0, radius * 9000.0)
    data.color = (1.0, 0.78, 0.56)
    data.shape = "DISK"
    data.size = max(0.1, radius * 6.0)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = controller.location + Vector(
        (-radius * 6.0, -radius * 7.0, radius * 8.0)
    )
    target = controller.location + Vector((0.0, 0.0, radius * 1.2))
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    obj["blastfx_role"] = "volumetric_light"
    obj["blastfx_id"] = controller["blastfx_id"]
    obj["blastfx_component"] = "ground_dust_fill"
    obj["blastfx_generated"] = True
    return obj
