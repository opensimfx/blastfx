"""Sprite sheet export: a baked blast packed into one transparent atlas plus a JSON; settings restored.

    blender -b --factory-startup --python-exit-code 1 --python tools/sprite_smoke.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_preview as RP  # noqa: E402

blastfx = RP.load_package()
blastfx.register()
from blastfx.addon import flipbook as FB  # noqa: E402
from blastfx.addon import sprites as SP  # noqa: E402
from blastfx.core import bake_job  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402

fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"[sprites] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


check(SP.sprite_frames(1, 13, 4) == [1, 5, 9, 13], "frames spread evenly over the baked range")
work = Path(tempfile.mkdtemp(prefix="blastfx_sprite_test_"))
try:
    RP.clear_scene()
    scene = bpy.context.scene
    props = scene.blastfx
    apply_preset(props, "small")
    props.quality = "DRAFT"
    props.duration = 0.25
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "scene.blend"))
    check("FINISHED" in bpy.ops.blastfx.create(), "create a blast")
    ctrl = next(o for o in scene.objects if o.get("blastfx_controller"))
    bpy.context.view_layer.objects.active = ctrl
    check("FINISHED" in bpy.ops.blastfx.bake(), "bake started")
    t0 = time.time()
    while bake_job.active_job() is not None and time.time() - t0 < 900:
        bake_job._poll()
        time.sleep(0.5)
    floor = bpy.data.objects.new("UserFloor", bpy.data.meshes.new("UserFloor"))
    scene.collection.objects.link(floor)
    sun = bpy.data.objects.new("UserSun", bpy.data.lights.new("UserSun", "SUN"))
    scene.collection.objects.link(sun)
    scene.render.use_compositing = True
    before, cam_before, n_obj = FB._snapshot(scene), scene.camera, len(bpy.data.objects)
    png, meta = SP.export_sprite_sheet(bpy.context, ctrl, cols=2, rows=2, tile=48, samples=2)
    img = bpy.data.images.load(str(png))
    a = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)
    check(tuple(img.size) == (96, 96), f"atlas is 2 x 2 frames of 48 px ({tuple(img.size)})")
    check(a[..., 3].max() > 0.2 and a[0, 0, 3] < 0.05, "transparent background around a visible blast")
    info = json.loads(meta.read_text())
    check(info["columns"] == 2 and info["rows"] == 2 and info["frames"] == 4 and info["tile_px"] == 48,
          "JSON describes the grid")
    check(png.parent.name == SP.FOLDER and png.parent.parent == work, "saved in blastfx_sprites/ next to the .blend")
    check(FB._snapshot(scene) == before and scene.camera == cam_before and not floor.hide_render
          and len(bpy.data.objects) == n_obj and scene.render.use_compositing,
          "scene, camera, compositing and visibility restored; temporary camera removed")
finally:
    shutil.rmtree(work, ignore_errors=True)

if fails:
    raise SystemExit(f"sprite smoke FAILED: {fails}")
print("SPRITE SMOKE OK")
