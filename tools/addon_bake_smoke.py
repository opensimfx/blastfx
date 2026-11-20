"""End-to-end smoke test of the add-on itself, on any OS:

    blender -b --factory-startup --python-exit-code 1 --python tools/addon_bake_smoke.py

Registers BlastFX from the source tree, saves a project, creates a blast and bakes it through the add-on's
background worker (a second Blender process: the path that broke on Windows when the worker imported the
POSIX-only ``resource`` module). Also checks the safety rules a crafted .blend must not get around:

- cache recovery, invalidate and prepare_cache never touch folders outside the cache root or without a marker;
- the bake status is read from a path derived from validated IDs, never from a path stored in the file;
- Free Cache refuses a domain whose cache folder is not its own BlastFX cache;
- the load handler survives a file load (recovery runs) and the relative-paths preference is restored.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_preview as RP  # noqa: E402  (loads the package from the source tree)

blastfx = RP.load_package()
blastfx.register()
from blastfx.addon import registration as REG  # noqa: E402
from blastfx.core import bake_job, cache  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402
from blastfx.simulation import cache as simcache  # noqa: E402

TIMEOUT_S = 1200
fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"[addon-smoke] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


work = Path(tempfile.mkdtemp(prefix="blastfx_smoke_"))
try:
    victim = work / "victim"
    (victim / "precious").mkdir(parents=True)
    (victim / "precious" / "keep.txt").write_text("keep", encoding="utf-8")
    (victim / ".blastfx_generation").write_text("broken", encoding="utf-8")

    prefs = bpy.context.preferences.filepaths
    prefs.use_relative_paths = True

    RP.clear_scene()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 6
    props = scene.blastfx
    apply_preset(props, "small")
    props.quality = "DRAFT"
    blend = work / "proj" / "scene.blend"
    blend.parent.mkdir()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))

    # 1. crafted IDs: nothing outside the cache is touched
    for bad in ("..", str(victim), "../victim"):
        ob = bpy.data.objects.new("evil", None)
        scene.collection.objects.link(ob)
        ob["blastfx_controller"] = True
        ob["blastfx_id"] = bad
    cache.recover_caches(bpy.context)
    for bad in ("..", str(victim)):
        cache.invalidate(props, bad)
    check((victim / "precious" / "keep.txt").exists() and blend.exists(), "crafted IDs delete nothing")
    for ob in [o for o in bpy.data.objects if o.name.startswith("evil")]:
        bpy.data.objects.remove(ob)

    # 2. a real bake through the background worker
    check("FINISHED" in bpy.ops.blastfx.create(), "create a blast")
    controller = bpy.context.active_object
    uid = controller["blastfx_id"]
    check("FINISHED" in bpy.ops.blastfx.bake(), "start the background bake")
    t0 = time.monotonic()
    while bake_job.active_job() is not None and time.monotonic() - t0 < TIMEOUT_S:
        bake_job._poll()
        time.sleep(0.5)
    st = bake_job.job_status(controller) or {}
    print(f"[addon-smoke] bake {st.get('state')} in {time.monotonic() - t0:.1f} s", flush=True)
    check(st.get("state") == "COMPLETED", "background bake completes")
    check(prefs.use_relative_paths is True, "relative-paths preference restored")

    # 3. status never follows a path stored in the file
    controller["blastfx_bake_status_path"] = str(victim / "precious" / "keep.txt")
    job = controller["blastfx_bake_job_id"]
    controller["blastfx_bake_job_id"] = "../../x"
    check(bake_job.job_status(controller) is None, "crafted status path ignored")
    controller["blastfx_bake_job_id"] = job
    del controller["blastfx_bake_status_path"]

    # 4. Free Cache only frees this blast's own cache
    domain = next(o for o in bpy.data.objects if o.get("blastfx_role") == "domain" and o.get("blastfx_id") == uid)
    ds = (domain.modifiers.get("BlastFX Fluid") or domain.modifiers.get("Fluid")).domain_settings
    own = ds.cache_directory
    other = work / "other"
    (other / "data").mkdir(parents=True)
    (other / "data" / "important.vdb").write_bytes(b"x" * 64)
    ds.cache_directory = str(other)
    try:
        simcache.free(bpy.context, domain)
        refused = False
    except RuntimeError:
        refused = True
    check(refused and (other / "data" / "important.vdb").exists(), "Free Cache refuses a foreign folder")
    ds.cache_directory = own

    # 5. recovery runs on load (the handler is persistent) and cleans stale bake snapshots
    stale = cache.active_cache_path(props, uid) / "job" / ("ab" * 16)
    stale.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
    check(REG._recover_caches_on_load in bpy.app.handlers.load_post, "load handler survives a file load")
    check(not stale.exists(), "recovery cleaned a stale bake snapshot")

    # 6. invalidate removes a real cache, never an unmarked folder with a valid name
    props = bpy.context.scene.blastfx
    cache.invalidate(props, uid)
    check(not (cache.project_cache_root(props) / uid).exists(), "invalidate removes the blast's cache")
    fake = cache.project_cache_root(props) / "deadbeef"
    (fake / "data").mkdir(parents=True)
    (fake / "data" / "x.txt").write_text("x", encoding="utf-8")
    cache.invalidate(props, "deadbeef")
    check((fake / "data" / "x.txt").exists(), "invalidate leaves an unmarked folder")
except Exception as exc:  # report, then fail the run
    import traceback
    traceback.print_exc()
    fails.append(f"{type(exc).__name__}: {exc}")
finally:
    try:
        blastfx.unregister()
    except Exception:
        pass
    shutil.rmtree(work, ignore_errors=True)

print(f"[addon-smoke] {sys.platform}: {'PASS' if not fails else 'FAIL: ' + '; '.join(fails)}", flush=True)
sys.stdout.flush()
os._exit(0 if not fails else 1)
