"""Re-bake Noise: keep the baked simulation data, bake only the noise pass again (modular, resumable cache).

    blender -b --factory-startup --python-exit-code 1 --python tools/noise_rebake_smoke.py

A small Final-quality blast (noise on, low resolution, short) is baked through the add-on's worker. Checks:
the cache is MODULAR and resumable, and the full bake's noise grids carry smoke (Blender 5.2.3 writes ~1.4 KB
empty noise files for a non-resumable modular cache). Changing only Noise (upres 2 -> 3) and running Re-bake
Noise must leave every data file untouched, write non-empty noise at the finer voxel size (x 2/3) and leave the
cache Baked with the new identity. Control: after a change to the simulation itself (seed), it refuses.
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
from blastfx.core import bake_job  # noqa: E402
from blastfx.core.cache import active_cache_path, status  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402

fails: list[str] = []
EMPTY_NOISE_BYTES = 4000      # an empty noise VDB is ~1.4 KB


def check(ok: bool, what: str) -> None:
    print(f"[noise] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


def wait() -> None:
    t0 = time.time()
    while bake_job.active_job() is not None and time.time() - t0 < 1500:
        bake_job._poll()
        time.sleep(0.5)


def noise_files(gen: Path):
    return sorted((gen / "noise").rglob("*.vdb"))


def noise_voxel(path: Path) -> float:
    # Blender caches VDB grids by file path, and the re-bake rewrites the same file names: read a unique copy
    copy = work / f"probe_{time.monotonic_ns()}.vdb"
    shutil.copyfile(path, copy)
    vol = bpy.data.volumes.new("probe")
    vol.filepath = str(copy)
    vol.grids.load()
    g = vol.grids.get("density_noise")
    size = g.matrix_object.to_scale()[0]
    bpy.data.volumes.remove(vol)
    return size


work = Path(tempfile.mkdtemp(prefix="blastfx_noise_"))
try:
    RP.clear_scene()
    scene = bpy.context.scene
    props = scene.blastfx
    apply_preset(props, "small")
    props.quality = "FINAL"
    props.resolution = 40
    props.noise_upres = 2
    props.duration = 0.3
    bpy.ops.wm.save_as_mainfile(filepath=str(work / "scene.blend"))
    check("FINISHED" in bpy.ops.blastfx.create(), "create a Final blast with noise")
    ctrl = next(o for o in scene.objects if o.get("blastfx_controller"))
    dom = next(o for o in scene.objects if o.get("blastfx_role") == "domain")
    ds = dom.modifiers["BlastFX Fluid"].domain_settings
    check(ds.cache_type == "MODULAR" and ds.cache_resumable and ds.use_noise,
          f"modular, resumable cache with noise ({ds.cache_type}, resumable={ds.cache_resumable})")
    bpy.context.view_layer.objects.active = ctrl
    check("FINISHED" in bpy.ops.blastfx.bake(), "bake started")
    wait()
    gen = active_cache_path(props, ctrl["blastfx_id"])
    data = {p: p.stat().st_mtime_ns for p in (gen / "data").rglob("*.vdb")}
    nf = noise_files(gen)
    check(bool(data) and bool(nf), f"data and noise baked ({len(data)} data, {len(nf)} noise files)")
    check(nf and nf[-1].stat().st_size > EMPTY_NOISE_BYTES, f"full bake's noise has smoke ({nf[-1].stat().st_size} bytes)")
    check(status(props, ctrl["blastfx_id"], ds, ctrl["blastfx_physics_state"], ctrl["blastfx_data_state"]) == "BAKED",
          "cache is Baked")
    v2 = noise_voxel(nf[-1])
    state0, data0 = ctrl["blastfx_physics_state"], ctrl["blastfx_data_state"]

    props.noise_upres = 3
    check("FINISHED" in bpy.ops.blastfx.rebake_noise(), "Re-bake Noise started")
    wait()
    check(active_cache_path(props, ctrl["blastfx_id"]) == gen, "same cache generation (the data was kept)")
    after = {p: p.stat().st_mtime_ns for p in (gen / "data").rglob("*.vdb")}
    check(after == data, "every data file untouched")
    nf3 = noise_files(gen)
    check(nf3 and nf3[-1].stat().st_size > EMPTY_NOISE_BYTES, f"re-baked noise has smoke ({nf3[-1].stat().st_size} bytes)")
    v3 = noise_voxel(nf3[-1])
    check(abs(v3 / v2 - 2.0 / 3.0) < 1e-3, f"noise voxels at the new upres ({v2:.4f} -> {v3:.4f})")
    check(ctrl["blastfx_physics_state"] != state0 and ctrl["blastfx_data_state"] == data0,
          "identity updated, data identity unchanged")
    check(status(props, ctrl["blastfx_id"], ds, ctrl["blastfx_physics_state"], ctrl["blastfx_data_state"]) == "BAKED",
          "cache is Baked again")

    state1 = ctrl["blastfx_physics_state"]
    props.seed += 1
    try:
        refused = "CANCELLED" in bpy.ops.blastfx.rebake_noise()
    except RuntimeError as exc:    # background mode raises on an error report
        refused = "data changed" in str(exc)
    check(refused, "a simulation change refuses a noise-only re-bake")
    check(ctrl["blastfx_physics_state"] == state1 and ctrl["blastfx_data_state"] == data0,
          "refused re-bake leaves the identity as it was")
    check(status(props, ctrl["blastfx_id"], ds, state1, data0) == "BAKED", "and the cache stays Baked")
finally:
    shutil.rmtree(work, ignore_errors=True)

if fails:
    raise SystemExit(f"noise re-bake smoke FAILED: {fails}")
print("NOISE REBAKE SMOKE OK")
