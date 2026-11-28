"""Preview flipbook: a quick render of the baked blast to judge timing and shape before a full render.

Renders the cached frame range at a fraction of the output resolution with few samples into a ``flipbook``
folder inside the blast's own cache folder (so it goes away with the cache), then plays it in Blender's
animation player. The scene's render settings are restored afterwards, also when the render is cancelled.
In the UI the render runs like F12 animation (progress, Esc cancels); in background mode it blocks.
"""
from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import Operator

from ..core.cache import cache_path

FOLDER = "flipbook"
_saved: dict | None = None      # render settings of the scene being flipbooked, restored on complete/cancel


def _controller(context):
    ob = context.active_object
    return ob if ob is not None and ob.get("blastfx_controller") else None


def _domain_settings(controller):
    for ob in controller.users_collection[0].objects if controller.users_collection else ():
        if ob.get("blastfx_role") == "domain":
            mod = ob.modifiers.get("BlastFX Fluid") or ob.modifiers.get("Fluid")
            return mod.domain_settings if mod else None
    return None


def flipbook_dir(props, blast_id: str) -> Path:
    return cache_path(props, blast_id) / FOLDER


def frames(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.png")) if folder.is_dir() else []


def _snapshot(scene) -> dict:
    r = scene.render
    snap = {
        "engine": r.engine, "resolution_percentage": r.resolution_percentage, "filepath": r.filepath,
        "file_format": r.image_settings.file_format, "frame_start": scene.frame_start,
        "frame_end": scene.frame_end, "use_file_extension": r.use_file_extension,
    }
    if hasattr(scene, "cycles"):
        snap["cycles_samples"] = scene.cycles.samples
    if hasattr(scene, "eevee"):
        snap["eevee_samples"] = scene.eevee.taa_render_samples
    return snap


def _restore(scene, snap: dict) -> None:
    r = scene.render
    r.engine = snap["engine"]
    r.resolution_percentage = snap["resolution_percentage"]
    r.filepath = snap["filepath"]
    r.image_settings.file_format = snap["file_format"]
    r.use_file_extension = snap["use_file_extension"]
    scene.frame_start, scene.frame_end = snap["frame_start"], snap["frame_end"]
    if "cycles_samples" in snap:
        scene.cycles.samples = snap["cycles_samples"]
    if "eevee_samples" in snap:
        scene.eevee.taa_render_samples = snap["eevee_samples"]


def _apply(scene, folder: Path, frame_range, engine: str, percent: int, samples: int) -> None:
    r = scene.render
    r.engine = engine
    r.resolution_percentage = int(percent)
    r.filepath = str(folder / "####")
    r.use_file_extension = True
    r.image_settings.file_format = "PNG"
    scene.frame_start, scene.frame_end = frame_range
    if engine == "CYCLES" and hasattr(scene, "cycles"):
        scene.cycles.samples = int(samples)
    elif hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = int(samples)


def _on_done(scene, *_args):
    global _saved
    if _saved is not None and _saved.get("scene") == scene.name:
        _restore(scene, _saved["settings"])
    _saved = None
    for handlers in (bpy.app.handlers.render_complete, bpy.app.handlers.render_cancel):
        if _on_done in handlers:
            handlers.remove(_on_done)


def render_flipbook(context, controller, *, engine="BLENDER_EEVEE", percent=50, samples=16, blocking=None) -> Path:
    """Render the blast's cached frames as a flipbook; returns the folder. Raises if nothing is baked."""
    global _saved
    scene = context.scene
    ds = _domain_settings(controller)
    if ds is None:
        raise RuntimeError("No BlastFX domain found for this controller.")
    folder = flipbook_dir(scene.blastfx, controller["blastfx_id"])
    folder.mkdir(parents=True, exist_ok=True)
    for old in frames(folder):
        old.unlink()
    snap = _snapshot(scene)
    _apply(scene, folder, (int(ds.cache_frame_start), int(ds.cache_frame_end)), engine, percent, samples)
    blocking = bpy.app.background if blocking is None else blocking
    if blocking:
        try:
            bpy.ops.render.render(animation=True)
        finally:
            _restore(scene, snap)
        return folder
    _saved = {"scene": scene.name, "settings": snap}
    for handlers in (bpy.app.handlers.render_complete, bpy.app.handlers.render_cancel):
        if _on_done not in handlers:
            handlers.append(_on_done)
    try:
        bpy.ops.render.render("INVOKE_DEFAULT", animation=True)
    except RuntimeError:
        _on_done(scene)
        raise
    return folder


class BLASTFX_OT_flipbook(Operator):
    bl_idname = "blastfx.flipbook"
    bl_label = "Render Flipbook"
    bl_description = ("Quick render of the baked blast (reduced size, few samples) into the blast's cache folder, "
                      "to check timing and shape before the full render. Play it with Play Flipbook")
    bl_options = {"REGISTER"}

    engine: EnumProperty(name="Engine", items=(("BLENDER_EEVEE", "EEVEE", "Fast (GPU)"),
                                               ("CYCLES", "Cycles", "Matches the final render")),
                         default="BLENDER_EEVEE")
    percent: IntProperty(name="Size %", default=50, min=10, max=100)
    samples: IntProperty(name="Samples", default=16, min=1, max=1024)

    def execute(self, context):
        controller = _controller(context)
        if controller is None:
            self.report({"ERROR"}, "Select a BlastFX controller.")
            return {"CANCELLED"}
        try:
            folder = render_flipbook(context, controller, engine=self.engine, percent=self.percent,
                                     samples=self.samples)
        except Exception as exc:
            self.report({"ERROR"}, f"Flipbook failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Flipbook rendering to {folder}")
        return {"FINISHED"}


class BLASTFX_OT_play_flipbook(Operator):
    bl_idname = "blastfx.play_flipbook"
    bl_label = "Play Flipbook"
    bl_description = "Play the blast's flipbook in Blender's animation player"
    bl_options = {"REGISTER"}

    def execute(self, context):
        controller = _controller(context)
        if controller is None:
            self.report({"ERROR"}, "Select a BlastFX controller.")
            return {"CANCELLED"}
        folder = flipbook_dir(context.scene.blastfx, controller["blastfx_id"])
        shots = frames(folder)
        if not shots:
            self.report({"ERROR"}, "No flipbook yet: Render Flipbook first.")
            return {"CANCELLED"}
        scene = context.scene
        snap = _snapshot(scene)
        try:   # the player reads the scene's output path and range: point them at the flipbook for the call
            scene.render.filepath = str(folder / "####")
            scene.render.image_settings.file_format = "PNG"
            nums = [int(p.stem) for p in shots if p.stem.isdigit()]
            scene.frame_start, scene.frame_end = min(nums), max(nums)
            bpy.ops.render.play_rendered_anim()
        except RuntimeError as exc:
            self.report({"ERROR"}, f"Could not start the player: {exc}")
            return {"CANCELLED"}
        finally:
            _restore(scene, snap)
        return {"FINISHED"}


CLASSES = (BLASTFX_OT_flipbook, BLASTFX_OT_play_flipbook)
