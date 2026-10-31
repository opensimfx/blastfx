"""Generate the Blast FX regression scenes listed in docs/DEVELOPMENT.md plan F.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python tools/make_examples.py

Writes examples/test_small.blend, test_medium.blend, test_large.blend,
test_large_event.blend. Each scene has a deterministic seed, the blast at the
origin, PREVIEW quality, neutral sun + world lighting, a camera framed on the
domain envelope and NO baked cache, so the file stays small and bakes on open.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

# Blender auto-enables a stale installed copy of blastfx at startup (Oct 1
# snapshot under Application Support). Disable it and purge its modules so the
# repo checkout below is the code under test.
import addon_utils  # noqa: E402

try:
    addon_utils.disable("blastfx", default_set=False)
except Exception as exc:  # noqa: BLE001
    print(f"note: addon_utils.disable raised {exc!r}; continuing after purge")
for key in [
    k for k in list(sys.modules) if k == "blastfx" or k.startswith("blastfx.")
]:
    del sys.modules[key]

sys.path.insert(0, "/Users/arsh/Developer/Projects/blastfx")

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from blastfx.addon.registration import register, unregister  # noqa: E402
from blastfx.core.explosion import create_explosion  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402
from blastfx.animation import _animation_config  # noqa: E402
from blastfx.render.settings import configure_render_settings, configure_world, configure_camera_dof  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPO_ROOT / "examples"
# Hero-frame dir is env-overridable so "after" turntables can render beside
# (never over) the committed examples/before evidence.
BEFORE_DIR = Path(os.environ.get(
    "BLASTFX_HERO_DIR", str(EXAMPLES / "before")
))

# Hero frames rendered for visual before/after regression: offsets relative
# to the blast start frame (+5 fireball, +15 mature smoke, +40 decay).
HERO_FRAME_OFFSETS = (5, 15, 40)
TURN_WIDTH, TURN_HEIGHT = 1280, 720

# scene filename -> (preset id, deterministic seed)
SCENES = (
    ("test_small.blend", "small", 1001),
    ("test_medium.blend", "medium", 2002),
    ("test_large.blend", "large", 3003),
    ("test_large_event.blend", "large_ground", 4004),
)

SENSOR_WIDTH_MM = 36.0  # Blender camera default sensor width


def _domain_object(controller):
    collection = controller.users_collection[0]
    return next(o for o in collection.objects if o.get("blastfx_role") == "domain")


def _domain_settings(domain_obj):
    return next(
        m.domain_settings for m in domain_obj.modifiers
        if m.type == "FLUID" and m.domain_settings is not None
    )


def _add_neutral_world(scene):
    configure_world(scene, "BlastFX_Example_World")


def _add_sun(scene):
    data = bpy.data.lights.new("BlastFX_Sun", type="SUN")
    data.energy = 3.0
    data.angle = math.radians(2.0)
    sun = bpy.data.objects.new("BlastFX_Sun", data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(30.0))


def _add_camera(scene, envelope):
    size = Vector(envelope["size"])
    center = Vector(envelope["center"])
    lens = min(85.0, max(50.0, float(os.environ.get("BLASTFX_EXAMPLE_LENS", "50"))))
    # Frame the largest envelope extent: distance ~= object_size * lens / sensor.
    extent = max(size.x, size.y, size.z * 0.8)
    distance = extent * lens / SENSOR_WIDTH_MM * 1.1
    direction = Vector((0.45, -1.0, 0.35)).normalized()
    data = bpy.data.cameras.new("BlastFX_Camera")
    data.lens = lens
    camera = bpy.data.objects.new("BlastFX_Camera", data)
    scene.collection.objects.link(camera)
    camera.location = center + direction * distance
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    data.clip_start = 0.01
    data.clip_end = max(1000.0, distance + extent * 4.0)
    configure_camera_dof(camera, fstop=2.8, focus_distance=distance * 0.8)
    scene.camera = camera


def _bake_fluids():
    domain_obj = next(
        (obj for obj in bpy.data.objects for mod in obj.modifiers
         if mod.type == "FLUID" and mod.fluid_type == "DOMAIN" and mod.domain_settings),
        None,
    )
    if domain_obj is None:
        raise RuntimeError("No fluid domain to bake.")
    domain_settings = next(
        mod.domain_settings for mod in domain_obj.modifiers
        if mod.type == "FLUID" and mod.domain_settings
    )
    frame_count = (
        int(domain_settings.cache_frame_end) - int(domain_settings.cache_frame_start) + 1
    )
    print(
        f"BAKING {frame_count} frame(s) at resolution {domain_settings.resolution_max}...",
        flush=True,
    )
    # bake_all acts on the view layer's active object
    bpy.context.view_layer.objects.active = domain_obj
    domain_obj.select_set(True)
    bpy.ops.fluid.bake_all()
    print("BAKE DONE", flush=True)


def _render_hero_frames(stem):
    """Render the regression hero frames into the hero dir (BLASTFX_HERO_DIR)."""
    scene = bpy.context.scene
    scene.render.resolution_x = TURN_WIDTH
    scene.render.resolution_y = TURN_HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    for offset in HERO_FRAME_OFFSETS:
        frame = scene.frame_start + offset
        if frame > scene.frame_end:
            continue
        scene.frame_set(frame)
        filepath = BEFORE_DIR / f"{stem}_f{offset:03d}.png"
        scene.render.filepath = str(filepath)
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {filepath}", flush=True)


def build_scene(filename, preset_id, seed):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 1.0
    configure_render_settings(scene, "PREVIEW")
    scene.cursor.location = (0.0, 0.0, 0.0)

    path = EXAMPLES / filename
    # Save BEFORE creating the blast: the cache root anchors to the blend's
    # directory (project_cache_root). Created on an unsaved file, the bake
    # lands in a temp session dir and save_as_mainfile's relative-path remap
    # leaves the finished blend pointing at a dead folder (observed Oct 19:
    # reopened turntables rendered with 0 .vdb files on disk).
    bpy.ops.wm.save_as_mainfile(filepath=str(path))

    props = scene.blastfx
    props.quality = "PREVIEW"  # before apply_preset: keeps preset resolutions un-halved
    apply_preset(props, preset_id)
    props.seed = seed
    props.start_frame = 1

    controller, _ = create_explosion(bpy.context)
    domain = _domain_settings(_domain_object(controller))
    scene.frame_start = int(domain.cache_frame_start)
    scene.frame_end = int(domain.cache_frame_end)

    config = _animation_config(bpy.context, props)
    _add_camera(scene, config["domain_envelope"])
    _add_neutral_world(scene)
    _add_sun(scene)

    _bake_fluids()

    # Final save: the cache path becomes //blastfx_cache/... relative to the
    # blend's own directory - fully portable from here on.
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    # Hero renders run in a SECOND blender process (see main BLASTFX_RENDER_MODE):
    # an in-process bake holds the full sim resident and the follow-up Cycles
    # render was silently OOM-killed (observed on small, Oct 19). Saving first
    # keeps the baked scene even if the render process dies.
    print(
        f"wrote {path} (preset={preset_id} seed={seed} "
        f"frames={scene.frame_start}-{scene.frame_end})",
        flush=True,
    )


def render_scene(filename):
    """Render-only stage: open the saved .blend and render hero frames."""
    path = EXAMPLES / filename
    bpy.ops.wm.open_mainfile(filepath=str(path))
    _render_hero_frames(Path(filename).stem)


def main():
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    BEFORE_DIR.mkdir(parents=True, exist_ok=True)
    only = os.environ.get("BLASTFX_EXAMPLES")
    selected = SCENES if not only else tuple(
        s for s in SCENES if s[1] in only.split(",")
    )
    if os.environ.get("BLASTFX_RENDER_MODE") == "render-only":
        register()  # compat: custom props on saved scenes
        try:
            for filename, _preset_id, _seed in selected:
                render_scene(filename)
        finally:
            unregister()
        print("EXAMPLES RENDERED:", BEFORE_DIR, flush=True)
        return
    register()
    try:
        for filename, preset_id, seed in selected:
            build_scene(filename, preset_id, seed)
    finally:
        unregister()
    print(f"EXAMPLES WRITTEN: {EXAMPLES}", flush=True)


if __name__ == "__main__":
    main()
