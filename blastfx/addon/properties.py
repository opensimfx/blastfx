import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
    PointerProperty,
)

EXPLOSION_TYPES = [
    ("GROUND", "Ground Explosion", "Ground-based conventional explosion"),
    ("FUEL", "Fuel Explosion", "Fuel or vehicle-scale explosion"),
    ("LARGE", "Large Ground Blast", "Large conventional ground blast"),
    ("HEAVY", "Heavy Ground Burst", "Massive long-burning ground burst"),
    ("NUCLEAR", "Nuclear Burst", "Nuclear detonation; yield drives the fireball scale"),
    ("AIRBURST", "Airburst", "Explosion occurring above the ground"),
    ("CUSTOM", "Custom", "User-authored configuration"),
]

QUALITY_PROFILES = [
    ("DRAFT", "Draft", "Fast structural iteration"),
    ("PREVIEW", "Preview", "Motion and shape validation"),
    ("FINAL", "Final", "Production-quality bake"),
]


def _on_fire_look(self, context):
    """Look sliders: update every BlastFX volume material in place (no rebuild, no re-bake)."""
    from ..materials.volume import apply_fire_look_to_scene
    apply_fire_look_to_scene(context.scene, self)


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
        name="Fireball Size",
        default=10.0,
        min=0.01,
        max=1000.0,
        soft_max=200.0,
        subtype="DISTANCE",
        description="Fireball diameter in metres. Size sets how fast the blast moves (Froude scaling): bigger blasts rise and roll slower, as real ones do",
    )

    intensity: FloatProperty(
        name="Intensity",
        default=1.0,
        min=0.0,
        max=10.0,
    )

    speed: FloatProperty(
        name="Playback Speed",
        default=1.0,
        min=0.05,
        max=10.0,
        description="Shot speed relative to real time: 1 = real time, 0.5 = 2x slow motion (how practical explosions are filmed). Changes frame count, not the explosion",
    )

    start_frame: IntProperty(
        name="Start Frame",
        default=1,
        min=0,
    )

    duration: FloatProperty(
        name="Duration",
        default=8.0,
        min=0.0,
        max=120.0,
        unit="TIME_ABSOLUTE",
        description="Real event time the shot covers, in seconds (before slow motion); converted to frames using scene FPS and playback speed. 0 = automatic: the explosion type's natural length at this size",
    )

    reference_energy: FloatProperty(
        name="Reference Energy",
        default=1.0,
        min=0.0,
        max=1e12,
        description="Internal normalized reference energy for physically coherent scaling; not an engineering yield calculator",
    )

    yield_kt: FloatProperty(
        name="Yield (kt)",
        default=15.0,
        min=0.0,
        max=100000.0,
        description="Nuclear yield in kilotons; drives the fireball diameter (~70 m per kt^(1/3), cinematic 8x compression). Only used for the Nuclear Burst type",
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
        name="Resolution",
        default=0,
        min=0,
        max=2048,
        description="0 = automatic: resolution follows the fireball size so detail per fireball stays constant per quality tier",
    )

    noise_upres: IntProperty(
        name="Noise",
        default=2,
        min=1,
        max=8,
    )

    use_directed: BoolProperty(
        name="Directed Blast",
        default=False,
        description="A one-sided blast: the whole fireball, debris and sparks drive into the half-space the "
                    "Blast Direction faces (a charge against a wall, a vehicle hit from the side, a mortar "
                    "burst). Needs a re-bake",
    )
    blast_direction: FloatVectorProperty(
        name="Blast Direction",
        description="Where a directed blast drives (at most 75 degrees from straight up; the ground surge stays "
                    "put). Needs a re-bake",
        default=(0.0, 0.0, 1.0), size=3, subtype="DIRECTION",
    )
    fire_path: PointerProperty(
        name="Fire Path",
        type=bpy.types.Object,
        poll=lambda self, ob: ob.type == "CURVE",
        description="A curve the fire runs along, like a fuel trail igniting (keep it inside the blast's "
                    "domain). Editing the curve needs a re-bake",
    )
    fire_path_speed: FloatProperty(
        name="Path Speed",
        description="How fast the flame front runs along the Fire Path, in metres per second of event time",
        default=6.0, min=0.1, max=500.0, unit="VELOCITY",
    )
    use_fireball: BoolProperty(name="Fireball", default=True)
    use_stem: BoolProperty(name="Rising Column", default=True)
    use_dust: BoolProperty(name="Ground Surge", default=True)
    use_shockwave: BoolProperty(name="Shockwave", default=True)
    use_debris: BoolProperty(name="Debris", default=False)
    use_debris_smoke: BoolProperty(
        name="Smoking Debris",
        default=True,
        description="Debris shards drag thin smoke trails through the air (needs a re-bake)",
    )
    use_flash: BoolProperty(
        name="Fire Light",
        default=True,
        description="Detonation flash, then the fire's glow lighting the smoke and surroundings",
    )
    use_camera_fx: BoolProperty(
        name="Camera FX",
        default=True,
        description="Add a BlastFX camera framed on the blast, with a shake that arrives with the sound",
    )
    camera_fx_active: BoolProperty(
        name="Use BlastFX Camera",
        default=False,
        description="Make the BlastFX camera the scene camera. Off keeps your own camera active (a scene without a camera still gets the BlastFX one); removing the blast restores your camera",
    )
    use_exposure: BoolProperty(
        name="Exposure & Bloom",
        default=True,
        description="Camera exposure reacts to the flash (relative to the scene's exposure) and the compositor adds bloom. A scene with its own compositor tree is left untouched",
    )
    use_heat_distortion: BoolProperty(name="Heat Distortion", default=True)
    use_rapatronic: BoolProperty(
        name="Rapatronic Skin",
        default=False,
        description="Early-time speckled fireball skin (first ~6 frames), the classic rapatronic camera look",
    )

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

    # --- Fire look (material only: changes the render, never the bake)
    fire_exposure: FloatProperty(
        name="Fire Exposure",
        description="Brightness of the fire in stops (+1 = twice as bright). Material only: no re-bake",
        default=0.0, min=-4.0, max=4.0, step=10,
        update=_on_fire_look,
    )
    fire_contrast: FloatProperty(
        name="Fire Contrast",
        description="Above 1: a hotter core with darker, thinner flame edges; below 1: softer, fuller flames",
        default=1.0, min=0.25, max=3.0,
        update=_on_fire_look,
    )
    flame_breakup: FloatProperty(
        name="Flame Break-up",
        description="Breaks the fire into flickering tongues and holes (an evolving noise mask the fire moves "
                    "through). 0 = the simulated fire as is",
        default=0.0, min=0.0, max=1.0, subtype="FACTOR",
        update=_on_fire_look,
    )
    fire_light_scene: FloatProperty(
        name="Fire Lights Scene",
        description="How strongly the fire lights the ground, the smoke and the scene, independent of how bright "
                    "it looks to the camera (Cycles). 1 = physical",
        default=1.0, min=0.0, max=10.0,
        update=_on_fire_look,
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
