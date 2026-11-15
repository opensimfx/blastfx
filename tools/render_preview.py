"""Render a BlastFX preset to a PNG in desktop Blender.

  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      --python tools/render_preview.py -- <preset_id> <out.png> [samples] [quality] [moment]

quality: DRAFT (default), PREVIEW or FINAL. moment: where in the shot to render,
0-1 of the baked frame range (default 0.5).

Presets: small, medium, large, large_ground, nuclear_airburst, nuclear_groundburst
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "blastfx"


def load_package():
    import importlib.util

    if "blastfx" in sys.modules:
        return sys.modules["blastfx"]
    spec = importlib.util.spec_from_file_location("blastfx", EXT / "__init__.py", submodule_search_locations=[str(EXT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["blastfx"] = mod
    spec.loader.exec_module(mod)
    return mod


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection" and collection.users == 0:
            bpy.data.collections.remove(collection)


def sky_world():
    world = bpy.data.worlds.new("BlastFX Sky")
    bpy.context.scene.world = world
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputWorld")
    bg = tree.nodes.new("ShaderNodeBackground")
    sky = tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "MULTIPLE_SCATTERING"
    sky.sun_elevation = 0.35
    sky.sun_rotation = 2.2
    # A dim daylight sky: enough to read the smoke's shape, the sun does the lighting.
    tree.links.new(sky.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.3
    tree.links.new(bg.outputs[0], out.inputs[0])


def sun_lamp(strength=5.0):
    data = bpy.data.lights.new("BlastFX Sun", "SUN")
    data.energy = strength
    data.angle = 0.02
    obj = bpy.data.objects.new("BlastFX Sun", data)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = (np.pi / 2 - 0.35, 0.0, 2.2)
    return obj


def ground(z, size):
    mesh = bpy.data.meshes.new("BlastFX Ground")
    mesh.from_pydata([(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("BlastFX Ground", mesh)
    bpy.context.scene.collection.objects.link(obj)
    mat = bpy.data.materials.new("BlastFX Ground")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.06, 0.07, 0.06, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    obj.data.materials.append(mat)
    return obj


def camera_for_blast(controller, radius):
    """Three-quarter view framed in fireball radii, so every size reads the same.

    15 R away at 35 mm, aimed 2.6 R up: the fireball, the column and a nuclear
    cap up to ~7 R all fit. (Framing on the domain put the camera inside it:
    the evaluated fluid domain is only the active smoke box.)
    """
    origin = Vector(controller.location)
    data = bpy.data.cameras.new("BlastFX Camera")
    data.lens = 35
    data.clip_start = radius * 0.05
    data.clip_end = radius * 2000
    cam = bpy.data.objects.new("BlastFX Camera", data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = origin + Vector((-9 * radius, -12 * radius, 2.2 * radius))
    target = origin + Vector((0.0, 0.0, 2.6 * radius))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def hide_helpers(uid):
    """Helper objects (sources, collision) are not things to look at."""
    for obj in bpy.data.objects:
        if obj.get("blastfx_id") == uid and obj.get("blastfx_role") not in {"controller", "domain", "camera_fx", "volumetric_light"}:
            if obj.get("blastfx_role") in {"emitter"}:
                obj.hide_render = True


def main(argv):
    preset_id = argv[0] if argv else "medium"
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "docs" / "img" / f"{preset_id}.png"
    samples = int(argv[2]) if len(argv) > 2 else 48
    quality = argv[3].upper() if len(argv) > 3 else "DRAFT"
    moment = float(argv[4]) if len(argv) > 4 else 0.5

    blastfx = load_package()
    blastfx.register()
    from blastfx.presets.apply import apply_preset
    from blastfx.core.explosion_profile import PROFILES

    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(out)

    scene.frame_start, scene.frame_end = 1, 24
    bpy.context.preferences.filepaths.use_relative_paths = False

    props = scene.blastfx
    apply_preset(props, preset_id)
    props.quality = quality
    props.use_camera_fx = True
    props.use_exposure = False
    props.use_heat_distortion = False

    if "FINISHED" not in bpy.ops.blastfx.create():
        raise SystemExit(f"Create failed for {preset_id}")

    controller = bpy.context.active_object
    uid = controller["blastfx_id"]

    # Start background bake
    if "FINISHED" not in bpy.ops.blastfx.bake():
        raise SystemExit(f"Bake start failed for {preset_id}")

    # Wait for bake to complete
    from blastfx.core import bake_job
    timeout = 1800
    started = time.monotonic()
    while bake_job.active_job() is not None:
        bake_job._poll()
        if time.monotonic() - started > timeout:
            raise SystemExit("Timed out waiting for bake")
        time.sleep(0.5)

    status = bake_job.job_status(controller) or {}
    if status.get("state") != "COMPLETED":
        raise SystemExit(f"Bake did not complete: {status}")

    # Find the domain for camera framing
    collection = next(c for c in controller.users_collection if c.name.startswith("Blast_"))
    domain_obj = next(obj for obj in collection.objects if obj.get("blastfx_role") == "domain")

    # Render at the chosen moment of the baked range.
    settings = domain_obj.modifiers["BlastFX Fluid"].domain_settings
    first, last = settings.cache_frame_start, settings.cache_frame_end
    scene.frame_set(int(round(first + moment * (last - first))))

    hide_helpers(uid)
    sky_world()
    sun_lamp()
    ground(0.0, 4000.0)
    camera_for_blast(controller, float(controller["blastfx_characteristic_radius_m"]))

    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"rendered {out} in {time.time() - t0:.1f}s", flush=True)

    save = os.environ.get("BLASTFX_SAVE_BLEND")
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=save)
        print(f"saved {save}", flush=True)

    blastfx.unregister()
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    code = main(argv)
    sys.stdout.flush()
    import os
    os._exit(code)