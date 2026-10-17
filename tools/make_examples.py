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


def build_scene(filename, preset_id, seed):
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 1.0
    configure_render_settings(scene, "PREVIEW")
    scene.cursor.location = (0.0, 0.0, 0.0)

    props = scene.blastfx
    apply_preset(props, preset_id)
    props.quality = "PREVIEW"
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

    path = EXAMPLES / filename
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print(
        f"wrote {path} (preset={preset_id} seed={seed} "
        f"frames={scene.frame_start}-{scene.frame_end})",
        flush=True,
    )


def main():
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    register()
    try:
        for filename, preset_id, seed in SCENES:
            build_scene(filename, preset_id, seed)
    finally:
        unregister()
    print(f"EXAMPLES WRITTEN: {EXAMPLES}", flush=True)


if __name__ == "__main__":
    main()
