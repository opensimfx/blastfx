"""Fire along a path: the flame front travels the curve in order, at the set speed; the path is in the identity.

    blender -b --factory-startup --python-exit-code 1 --python tools/fire_path_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_preview as RP  # noqa: E402

blastfx = RP.load_package()
blastfx.register()
from blastfx.core.blast_plan import plan_blast  # noqa: E402
from blastfx.core.domain_envelope import envelope_state  # noqa: E402
from blastfx.core.explosion_profile import profile_state  # noqa: E402
from blastfx.core.physical_state import build_physical_state, state_hash  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402
from blastfx.simulation.fire_path import path_length, path_points  # noqa: E402

fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"[fire-path] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


RP.clear_scene()
sc = bpy.context.scene
p = sc.blastfx
apply_preset(p, "small")
p.quality = "DRAFT"
cd = bpy.data.curves.new("Trail", "CURVE")
cd.dimensions = "3D"
sp = cd.splines.new("POLY")
sp.points.add(1)
sp.points[0].co, sp.points[1].co = (-4.0, 0.0, 0.05, 1.0), (4.0, 0.0, 0.05, 1.0)
trail = bpy.data.objects.new("Trail", cd)
sc.collection.objects.link(trail)
p.fire_path, p.fire_path_speed = trail, 4.0
check("FINISHED" in bpy.ops.blastfx.create(), "create a blast with a fire path")
em = next(o for o in sc.objects if o.get("blastfx_role") == "fire_path_emitter")
fs = next(m for m in em.modifiers if m.type == "FLUID").flow_settings
check(fs.flow_source == "PARTICLES" and fs.flow_type == "BOTH" and fs.fuel_amount > 0, "fuel flow fed by the path")
pts = path_points(trail, 0.24)
check(abs(path_length(pts) - 8.0) < 0.3, f"resampled path keeps its length ({path_length(pts):.2f} m)")
f0, f1 = em["blastfx_fire_path_frames"]
plan = plan_blast(p, sc)
want = plan.event_frames(8.0 / 4.0)
check(abs((f1 - f0) - want) <= 1, f"front takes length / speed ({f1 - f0} frames, want {want:.1f})")
front = []
for f in range(1, f1 + 2):
    sc.frame_set(f)
    if f in (f0 + 2, (f0 + f1) // 2, f1):
        ps = em.evaluated_get(bpy.context.evaluated_depsgraph_get()).particle_systems[0]
        xs = [pt.location.x for pt in ps.particles if pt.alive_state == "ALIVE"]
        front.append(max(xs) if xs else float("nan"))
check(front[0] < -3.0 and abs(front[1]) < 1.0 and front[2] > 3.0, f"front runs along the path {front}")


def ident():
    pl = plan_blast(p, sc)
    return state_hash(build_physical_state(p, sc, "x", pl.physical, pl.numerical, pl.frame_start, pl.frame_end,
                                           envelope_state(pl.envelope), profile_state(pl.profile)))


a = ident()
trail.location.y += 0.5
bpy.context.view_layer.update()
check(ident() != a, "editing the path changes the cache identity")
p.fire_path_speed = 8.0
b = ident()
p.fire_path = None
check(ident() not in (a, b), "speed and path on/off are part of the identity")

if fails:
    raise SystemExit(f"fire path smoke FAILED: {fails}")
print("FIRE PATH SMOKE OK")
