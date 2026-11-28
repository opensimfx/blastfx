"""Preview flipbook: renders the baked range small and fast into the blast's cache folder, restores settings.

    blender -b --factory-startup --python-exit-code 1 --python tools/flipbook_smoke.py

Uses Cycles (works on GPU-less CI); EEVEE is the UI default. Bakes a tiny DRAFT blast through the add-on first.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_preview as RP  # noqa: E402

blastfx = RP.load_package()
blastfx.register()
from blastfx.addon import flipbook as FB  # noqa: E402
from blastfx.core import bake_job  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402

fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"[flipbook] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


work = Path(tempfile.mkdtemp(prefix="blastfx_flip_"))
try:
    RP.clear_scene()
    scene = bpy.context.scene
    props = scene.blastfx
    apply_preset(props, "small")
    props.quality = "DRAFT"
    props.duration = 0.25
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "scene.blend"))
    check("FINISHED" in bpy.ops.blastfx.create(), "create a blast")
    controller = next(o for o in scene.objects if o.get("blastfx_controller"))
    bpy.context.view_layer.objects.active = controller
    check("FINISHED" in bpy.ops.blastfx.bake(), "bake started")
    t0 = time.time()
    while bake_job.active_job() is not None and time.time() - t0 < 900:
        bake_job._poll()
        time.sleep(0.5)
    ds = FB._domain_settings(controller)
    n_frames = int(ds.cache_frame_end) - int(ds.cache_frame_start) + 1

    scene.render.resolution_x, scene.render.resolution_y = 320, 180
    before = FB._snapshot(scene)
    folder = FB.render_flipbook(bpy.context, controller, engine="CYCLES", percent=50, samples=2, blocking=True)
    shots = FB.frames(folder)
    check(len(shots) == n_frames, f"one frame per cached frame ({len(shots)} of {n_frames})")
    check(folder.parent.name == controller["blastfx_id"] or controller["blastfx_id"] in str(folder),
          "flipbook lives in the blast's cache folder")
    img = bpy.data.images.load(str(shots[0]))
    check(tuple(img.size) == (160, 90), f"rendered at 50 % ({tuple(img.size)})")
    check(FB._snapshot(scene) == before, "scene render settings restored")
finally:
    shutil.rmtree(work, ignore_errors=True)

if fails:
    raise SystemExit(f"flipbook smoke FAILED: {fails}")
print("FLIPBOOK SMOKE OK")
