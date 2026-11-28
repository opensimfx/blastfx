"""Fire look layer: material only, neutral by default, never part of the cache identity.

    blender -b --factory-startup --python-exit-code 1 --python tools/look_smoke.py

Creates a blast (no bake) and checks: the volume material carries the look nodes at neutral values (exposure x1,
contrast 1, no break-up, the fire lights the scene x1); moving the Fire look sliders updates the material in place
and leaves the controller's physics state (the cache identity) unchanged; the break-up noise is animated.
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
from blastfx.materials.volume import LOOK_TAG, _look_nodes  # noqa: E402
from blastfx.presets.apply import apply_preset  # noqa: E402

fails: list[str] = []


def check(ok: bool, what: str) -> None:
    print(f"[look] {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        fails.append(what)


RP.clear_scene()
scene = bpy.context.scene
props = scene.blastfx
apply_preset(props, "small")
props.quality = "DRAFT"
check("FINISHED" in bpy.ops.blastfx.create(), "create a blast")
controller = next(o for o in scene.objects if o.get("blastfx_controller"))
state0 = controller.get("blastfx_physics_state")
mats = [m for m in bpy.data.materials if m.get(LOOK_TAG)]
check(len(mats) == 1, f"one tagged volume material ({len(mats)})")
n = _look_nodes(mats[0])
check(all(v is not None for v in n.values()), "look nodes present")
check(abs(n["Exposure"].outputs[0].default_value - 1.0) < 1e-6
      and abs(n["Contrast"].inputs[1].default_value - 1.0) < 1e-6
      and n["Breakup"].inputs[0].default_value == 0.0
      and abs(n["Light Scene"].inputs["A"].default_value - 1.0) < 1e-6, "defaults are neutral")

props.fire_exposure = 1.0
props.fire_contrast = 1.5
props.flame_breakup = 0.6
props.fire_light_scene = 2.5
check(abs(n["Exposure"].outputs[0].default_value - 2.0) < 1e-6, "+1 stop doubles the fire")
check(abs(n["Contrast"].inputs[1].default_value - 1.5) < 1e-6, "contrast reaches the material")
check(abs(n["Breakup"].inputs[0].default_value - 0.6) < 1e-6, "break-up reaches the material")
check(abs(n["Light Scene"].inputs["A"].default_value - 2.5) < 1e-6, "light-scene factor reaches the material")
check(controller.get("blastfx_physics_state") == state0, "look sliders leave the cache identity alone")

# the strength chain really ends in the volume's emission strength through the look nodes
vol = next(nd for nd in mats[0].node_tree.nodes if nd.bl_idname == "ShaderNodeVolumePrincipled")
src = vol.inputs["Emission Strength"].links[0].from_node
check(src.bl_idname == "ShaderNodeMath" and src.operation == "MULTIPLY", "emission strength is graded")
noise = next(nd for nd in mats[0].node_tree.nodes if nd.bl_idname == "ShaderNodeTexNoise")
w = []
for f in (1, 25):
    scene.frame_set(f)
    w.append(noise.inputs["W"].default_value)
check(w[1] > w[0], f"break-up noise evolves over time (W {w[0]:.2f} -> {w[1]:.2f})")

if fails:
    raise SystemExit(f"look smoke FAILED: {fails}")
print("LOOK SMOKE OK")
