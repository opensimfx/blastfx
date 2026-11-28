"""Sprite sheet export: a baked blast as one transparent flipbook atlas (rows x columns of frames) plus a JSON.

For cheap camera-facing cards (distant or repeated blasts, crowds of explosions) and game engines. Frames are
spaced evenly over the baked range and rendered with a transparent film through a temporary orthographic camera
framed on the blast's domain envelope from the side (above the ground for a surface blast). The scene's other
geometry is hidden and the compositor is off (bloom would fill each tile); the scene's lights and world still light
the blast. The atlas goes next to the .blend in ``blastfx_sprites/`` (the cache
folder is deleted with every re-bake). Scene settings, visibility and the camera are restored afterwards.
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import Operator

from .flipbook import _controller, _domain_settings, _restore, _snapshot

FOLDER = "blastfx_sprites"


def _blast_collection(controller):
    return next((c for c in controller.users_collection if c.name.startswith("Blast_")), None)


def _frame_box(controller):
    """World-space (min, max) the sprite frames: the domain envelope, cut at the ground for a surface blast."""
    env = controller.get("blastfx_domain_envelope")
    loc = controller.location
    lo = [loc[i] + float(env["min"][i]) for i in range(3)]
    hi = [loc[i] + float(env["max"][i]) for i in range(3)]
    coll = _blast_collection(controller)
    ground = next((o for o in coll.objects if o.get("blastfx_role") == "ground_effector"), None) if coll else None
    if ground is not None:
        top = max((ground.matrix_world @ v.co).z for v in ground.data.vertices)
        lo[2] = max(lo[2], top)
    return lo, hi


def sprite_frames(first: int, last: int, count: int) -> list[int]:
    """``count`` frames spread evenly from ``first`` to ``last`` (inclusive)."""
    if count <= 1 or last <= first:
        return [first] * max(count, 1)
    return [int(round(first + (last - first) * i / (count - 1))) for i in range(count)]


def export_sprite_sheet(context, controller, *, cols=6, rows=6, tile=256, engine="CYCLES", samples=32,
                        out_dir: Path | None = None) -> tuple[Path, Path]:
    """Render and pack the atlas; returns (png, json). Raises if the blast has no baked range."""
    import numpy as np

    scene = context.scene
    ds = _domain_settings(controller)
    if ds is None:
        raise RuntimeError("No BlastFX domain found for this controller.")
    coll = _blast_collection(controller)
    lo, hi = _frame_box(controller)
    width, height = hi[0] - lo[0], hi[2] - lo[2]
    frames = sprite_frames(int(ds.cache_frame_start), int(ds.cache_frame_end), cols * rows)

    base = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path(tempfile.gettempdir())
    out_dir = Path(out_dir) if out_dir else base / FOLDER
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{controller.name}_{cols}x{rows}"
    png, meta = out_dir / f"{stem}.png", out_dir / f"{stem}.json"

    snap = _snapshot(scene)
    r = scene.render
    saved = {"camera": scene.camera, "film": r.film_transparent, "res": (r.resolution_x, r.resolution_y),
             "comp": r.use_compositing, "seq": r.use_sequencer,
             "frame": scene.frame_current, "color_mode": r.image_settings.color_mode}
    # hide the scene's geometry, never its lights: the blast must still be lit by them and the world
    hidden = [o for o in scene.objects if not o.hide_render and o.type not in {"LIGHT", "CAMERA", "LIGHT_PROBE", "EMPTY"}
              and (coll is None or o.name not in coll.all_objects)]
    cam_data = bpy.data.cameras.new("BlastFX Sprite Camera")
    cam = bpy.data.objects.new("BlastFX Sprite Camera", cam_data)
    scene.collection.objects.link(cam)
    tmp = Path(tempfile.mkdtemp(prefix="blastfx_sprite_"))
    try:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(width, height) * 1.04
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        depth = hi[1] - lo[1]
        cam.location = (cx, lo[1] - depth, cz)                  # side view, looking along +Y
        cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
        cam_data.clip_end = depth * 4
        scene.camera = cam
        for o in hidden:
            o.hide_render = True
        r.film_transparent = True
        r.use_compositing = False      # bloom and glare would fill each tile's transparent background
        r.use_sequencer = False
        r.engine = engine
        r.resolution_percentage = 100
        r.resolution_x = r.resolution_y = int(tile)
        r.image_settings.file_format = "PNG"
        r.image_settings.color_mode = "RGBA"
        if engine == "CYCLES" and hasattr(scene, "cycles"):
            scene.cycles.samples = int(samples)
        elif hasattr(scene, "eevee"):
            scene.eevee.taa_render_samples = int(samples)
        atlas = np.zeros((rows * tile, cols * tile, 4), dtype=np.float32)
        for i, f in enumerate(frames):
            scene.frame_set(f)
            r.filepath = str(tmp / f"{i:04d}.png")
            bpy.ops.render.render(write_still=True)
            img = bpy.data.images.load(r.filepath)
            px = np.array(img.pixels[:], dtype=np.float32).reshape(tile, tile, 4)   # bottom row first
            bpy.data.images.remove(img)
            row, col = divmod(i, cols)
            y0 = (rows - 1 - row) * tile                                            # first frame at top-left
            atlas[y0:y0 + tile, col * tile:(col + 1) * tile] = px
        out = bpy.data.images.new(stem, cols * tile, rows * tile, alpha=True)
        out.pixels.foreach_set(atlas.ravel())
        out.filepath_raw = str(png)
        out.file_format = "PNG"
        out.save()
        bpy.data.images.remove(out)
        fps = scene.render.fps / (scene.render.fps_base or 1.0)
        meta.write_text(json.dumps({
            "image": png.name, "columns": cols, "rows": rows, "tile_px": int(tile), "frames": len(frames),
            "order": "left to right, top to bottom", "source_frames": frames,
            "fps": round(fps * (len(frames) - 1) / max(frames[-1] - frames[0], 1), 4) if len(frames) > 1 else fps,
            "world_size_m": [round(width, 4), round(height, 4)], "pivot": "bottom centre" if lo[2] > 0 else "centre",
        }, indent=2), encoding="utf-8")
    finally:
        for o in hidden:
            o.hide_render = False
        scene.camera = saved["camera"]
        r.film_transparent = saved["film"]
        r.use_compositing, r.use_sequencer = saved["comp"], saved["seq"]
        r.resolution_x, r.resolution_y = saved["res"]
        r.image_settings.color_mode = saved["color_mode"]
        _restore(scene, snap)
        scene.frame_set(saved["frame"])
        bpy.data.objects.remove(cam)
        bpy.data.cameras.remove(cam_data)
        for p in tmp.glob("*.png"):
            p.unlink()
        tmp.rmdir()
    return png, meta


class BLASTFX_OT_sprite_sheet(Operator):
    bl_idname = "blastfx.sprite_sheet"
    bl_label = "Export Sprite Sheet"
    bl_description = ("Render the baked blast into one transparent flipbook atlas (rows x columns of frames) plus a "
                      "JSON, for camera-facing cards and game engines. Saved in blastfx_sprites/ next to the .blend")
    bl_options = {"REGISTER"}

    grid: EnumProperty(name="Grid", items=(("4", "4 x 4", "16 frames"), ("6", "6 x 6", "36 frames"),
                                           ("8", "8 x 8", "64 frames")), default="6")
    tile: IntProperty(name="Frame Size", default=256, min=32, max=2048, description="Pixels per frame")
    samples: IntProperty(name="Samples", default=32, min=1, max=4096)
    engine: EnumProperty(name="Engine", items=(("CYCLES", "Cycles", ""), ("BLENDER_EEVEE", "EEVEE", "")),
                         default="CYCLES")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        controller = _controller(context)
        if controller is None:
            self.report({"ERROR"}, "Select a BlastFX controller.")
            return {"CANCELLED"}
        n = int(self.grid)
        try:
            png, _meta = export_sprite_sheet(context, controller, cols=n, rows=n, tile=self.tile,
                                             engine=self.engine, samples=self.samples)
        except Exception as exc:
            self.report({"ERROR"}, f"Sprite sheet failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Sprite sheet saved: {png}")
        return {"FINISHED"}


CLASSES = (BLASTFX_OT_sprite_sheet,)
