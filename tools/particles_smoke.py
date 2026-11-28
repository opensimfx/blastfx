"""Debris smoke trails, cooling sparks and ground collision (no bake).

    blender -b --factory-startup --python-exit-code 1 --python tools/particles_smoke.py

Checks: with Debris and Smoking Debris on, the debris emitter carries a smoke flow fed by its particle system;
off, it has none; the toggle is part of the cache identity only while debris is on; sparks use the cooling
blackbody material; the ground collision damps and slows what lands on it.
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
from blastfx.presets.apply import apply_preset  # noqa: E402

fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"[particles] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


def build(debris: bool, smoke: bool):
    RP.clear_scene()
    props = bpy.context.scene.blastfx
    apply_preset(props, "small")
    props.quality = "DRAFT"
    props.seed = 7
    props.use_debris = debris
    props.use_debris_smoke = smoke
    assert "FINISHED" in bpy.ops.blastfx.create()
    ctrl = next(o for o in bpy.context.scene.objects if o.get("blastfx_controller"))
    return ctrl, {o.get("blastfx_role"): o for o in bpy.context.scene.objects if o.get("blastfx_role")}


ctrl, roles = build(True, True)
em = roles.get("debris_emitter")
flow = next((m for m in em.modifiers if m.type == "FLUID"), None) if em else None
fs = flow.flow_settings if flow else None
check(fs is not None and fs.flow_source == "PARTICLES" and fs.flow_type == "SMOKE"
      and fs.particle_system is not None and fs.particle_system.name == "DebrisParticles",
      "debris emitter carries a smoke flow fed by its particles")
check(fs is not None and fs.fuel_amount == 0.0 and fs.subframes >= 4, "trails are smoke only and sub-stepped")
state_on = ctrl["blastfx_physics_state"]

ctrl, roles = build(True, False)
em = roles.get("debris_emitter")
check(em is not None and not any(m.type == "FLUID" for m in em.modifiers), "Smoking Debris off: no trail flow")
check(ctrl["blastfx_physics_state"] != state_on, "smoke toggle changes the cache identity while debris is on")

def identity(debris: bool, smoke: bool) -> str:
    """Cache identity for a fixed blast id (create would mint a new id each time)."""
    from blastfx.core.blast_plan import plan_blast
    from blastfx.core.domain_envelope import envelope_state
    from blastfx.core.explosion_profile import profile_state
    from blastfx.core.physical_state import build_physical_state, state_hash
    scene = bpy.context.scene
    props = scene.blastfx
    props.use_debris, props.use_debris_smoke = debris, smoke
    plan = plan_blast(props, scene)
    return state_hash(build_physical_state(props, scene, "fixed", plan.physical, plan.numerical, plan.frame_start,
                                           plan.frame_end, envelope_state(plan.envelope), profile_state(plan.profile)))


check(identity(False, True) == identity(False, False), "without debris the smoke toggle leaves the identity alone")
check(identity(True, True) != identity(True, False), "with debris the smoke toggle is part of the identity")
ctrl, roles = build(False, False)

spark_mats = [m for m in bpy.data.materials if m.get("blastfx_spark_cooling")]
check(len(spark_mats) >= 1 and any(n.bl_idname == "ShaderNodeParticleInfo" for n in spark_mats[0].node_tree.nodes),
      "sparks cool over their life (Particle Info -> blackbody)")
ground = roles.get("ground_effector")
check(ground is not None and ground.collision.damping_factor > 0.3 and ground.collision.friction_factor > 0.3,
      "ground collision damps and slows landing particles")

if fails:
    raise SystemExit(f"particles smoke FAILED: {fails}")
print("PARTICLES SMOKE OK")
