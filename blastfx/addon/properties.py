import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    PointerProperty,
)

EXPLOSION_TYPES = [
    ("GROUND", "Ground Explosion", "Ground-based conventional explosion"),
    ("FUEL", "Fuel Explosion", "Fuel or vehicle-scale explosion"),
    ("LARGE", "Large Ground Blast", "Large conventional ground blast"),
    ("AIRBURST", "Airburst", "Explosion occurring above the ground"),
    ("CUSTOM", "Custom", "User-authored configuration"),
]

QUALITY_PROFILES = [
    ("DRAFT", "Draft", "Fast structural iteration"),
    ("PREVIEW", "Preview", "Motion and shape validation"),
    ("FINAL", "Final", "Production-quality bake"),
]


class BLASTFX_Props(PropertyGroup):
    explosion_type: EnumProperty(
        name="Type",
        items=EXPLOSION_TYPES,
        default="FUEL",
    )

    preset_id: StringProperty(
        name="Preset",
        default="medium",
    )

    scale: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.01,
        max=1000.0,
        soft_max=20.0,
    )

    intensity: FloatProperty(
        name="Intensity",
        default=1.0,
        min=0.0,
        max=10.0,
    )

    speed: FloatProperty(
        name="Speed",
        default=1.0,
        min=0.05,
        max=10.0,
    )

    start_frame: IntProperty(
        name="Start Frame",
        default=1,
        min=0,
    )

    duration: FloatProperty(
        name="Duration",
        default=8.0,
        min=0.1,
        max=120.0,
        description="Physical event duration in seconds; converted to Blender frames using scene FPS",
    )

    reference_energy: FloatProperty(
        name="Reference Energy",
        default=1.0,
        min=0.0,
        max=1e12,
        description="Internal normalized reference energy for physically coherent scaling; not an engineering yield calculator",
    )

    seed: IntProperty(
        name="Seed",
        default=12345,
        min=0,
        max=2147483647,
    )

    quality: EnumProperty(
        name="Quality",
        items=QUALITY_PROFILES,
        default="PREVIEW",
    )

    resolution: IntProperty(
        name="Resolution Override",
        default=0,
        min=0,
        max=2048,
    )

    noise_upres: IntProperty(
        name="Noise",
        default=2,
        min=1,
        max=8,
    )

    use_fireball: BoolProperty(name="Fireball", default=True)
    use_stem: BoolProperty(name="Rising Column", default=True)
    use_dust: BoolProperty(name="Ground Surge", default=True)
    use_shockwave: BoolProperty(name="Shockwave", default=True)
    use_debris: BoolProperty(name="Debris", default=False)
    use_flash: BoolProperty(name="Flash", default=True)
    use_camera_fx: BoolProperty(name="Camera FX", default=False)
    use_exposure: BoolProperty(name="Exposure Impulse", default=False)
    use_heat_distortion: BoolProperty(name="Heat Distortion", default=False)

    turbulence: FloatProperty(
        name="Turbulence",
        default=1.0,
        min=0.0,
        max=10.0,
    )

    smoke_density: FloatProperty(
        name="Smoke Density",
        default=1.0,
        min=0.0,
        max=10.0,
    )

    fire_temperature: FloatProperty(
        name="Fire Temperature",
        default=1.0,
        min=0.0,
        max=10.0,
    )

    cache_subdir: StringProperty(
        name="Cache Folder",
        default="blastfx_cache",
    )


def register_properties():
    bpy.utils.register_class(BLASTFX_Props)
    bpy.types.Scene.blastfx = PointerProperty(type=BLASTFX_Props)


def unregister_properties():
    del bpy.types.Scene.blastfx
    bpy.utils.unregister_class(BLASTFX_Props)
