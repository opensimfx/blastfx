"""Time a Blast FX bake so cost changes can be measured, not guessed.

Run in desktop Blender (Mantaflow needs the full build, not the bpy wheel):

    /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
        --python tools/bake_benchmark.py -- <preset> <quality> <work_dir> [max_frames]

    <preset>    small | medium | large | large_ground | nuclear_airburst | ...
    <quality>   DRAFT | PREVIEW | FINAL
    <work_dir>  where the scratch .blend and cache go (caches reach GBs)
    max_frames  optional: bake only the first N frames (quick A/B timing)

Writes <work_dir>/bench_<preset>_<quality>.json with wall seconds, peak RSS, cache
bytes, per-phase spans and the solver settings used. Nothing in the repository is
modified. Compare two runs of the same preset/tier to see if a change helped.
"""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import addon_utils  # noqa: E402

# Use this checkout, never a stale installed copy.
try:
    addon_utils.disable("blastfx", default_set=False)
except Exception as exc:  # noqa: BLE001
    print(f"note: addon_utils.disable raised {exc!r}; continuing")
for key in [k for k in list(sys.modules) if k == "blastfx" or k.startswith("blastfx.")]:
    del sys.modules[key]

import bpy  # noqa: E402
from blastfx.addon.registration import register, unregister  # noqa: E402
from blastfx.core.explosion import create_explosion  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402


def _peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024, 1)


def _domain_settings():
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type == "FLUID" and mod.fluid_type == "DOMAIN" and mod.domain_settings:
                return obj, mod.domain_settings
    raise RuntimeError("No fluid domain found.")


def _phases(cache_root: Path, t0: float) -> dict:
    out = {}
    for name in ("data", "noise"):
        folder = cache_root / name
        files = [p for p in folder.glob("*") if p.is_file()] if folder.exists() else []
        if files:
            times = sorted(p.stat().st_mtime for p in files)
            out[name] = {
                "files": len(files),
                "bytes": sum(p.stat().st_size for p in files),
                "last_s": round(times[-1] - t0, 1),
                "span_s": round(times[-1] - times[0], 1),
            }
    return out


def main() -> int:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) < 3:
        print(__doc__)
        return 2
    preset_id, quality, work = args[0], args[1].upper(), Path(args[2]).resolve()
    max_frames = int(args[3]) if len(args) > 3 else 0
    work.mkdir(parents=True, exist_ok=True)

    register()
    try:
        bpy.ops.wm.read_homefile(use_empty=True)
        scene = bpy.context.scene
        scene.unit_settings.scale_length = 1.0
        scene.cursor.location = (0.0, 0.0, 0.0)
        blend = work / f"bench_{preset_id}_{quality}.blend"
        # Save first: the cache root anchors to the blend's directory.
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))

        props = scene.blastfx
        props.quality = quality  # before apply_preset, as the examples do
        apply_preset(props, preset_id)
        props.seed = 1234
        props.start_frame = 1
        create_explosion(bpy.context)

        obj, dom = _domain_settings()
        if max_frames:
            dom.cache_frame_end = dom.cache_frame_start + max_frames - 1
        frames = int(dom.cache_frame_end) - int(dom.cache_frame_start) + 1
        cache_root = Path(bpy.path.abspath(dom.cache_directory))
        print(f"BENCH {preset_id} {quality}: {frames} frames, res {dom.resolution_max}, "
              f"noise {dom.use_noise}x{dom.noise_scale}", flush=True)

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        wall0, mono0 = time.time(), time.monotonic()
        result = bpy.ops.fluid.bake_all()
        seconds = time.monotonic() - mono0

        payload = {
            "preset": preset_id,
            "quality": quality,
            "result": sorted(result),
            "blender": bpy.app.version_string,
            "frames": frames,
            "bake_seconds": round(seconds, 1),
            "seconds_per_frame": round(seconds / max(frames, 1), 2),
            "peak_rss_mb": _peak_rss_mb(),
            "resolution_max": int(dom.resolution_max),
            "use_noise": bool(dom.use_noise),
            "noise_scale": int(dom.noise_scale),
            "adapt_margin": int(dom.adapt_margin),
            "adapt_threshold": float(dom.adapt_threshold),
            "additional_res": int(dom.additional_res),
            "timesteps": [int(dom.timesteps_min), int(dom.timesteps_max)],
            "cfl": float(dom.cfl_condition),
            "phases": _phases(cache_root, wall0),
            "cache_bytes": sum(p.stat().st_size for p in cache_root.rglob("*") if p.is_file())
            if cache_root.exists() else 0,
        }
        out = work / f"bench_{preset_id}_{quality}.json"
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("BENCH RESULT", json.dumps(payload), flush=True)
        return 0
    finally:
        unregister()


if __name__ == "__main__":
    raise SystemExit(main())
