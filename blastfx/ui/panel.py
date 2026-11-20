"""Sidebar panels (3D View > N panel > BlastFX).

Layout follows docs/UI_STYLE.md, identical in every OpenSimFX add-on.
"""

import time

import bpy
from bpy.types import Menu, Panel

from ..presets import registry
from ..presets.registry import all_presets
from ..core.cache import status
from ..core.bake_job import active_job, job_status, pending_bakes

_STATE_LABELS = {
    "BAKING_DATA": "Baking",
    "BAKING_NOISE": "Baking",
    "FINALIZING": "Finalizing",
    "COMPLETED": "Baked",
    "BAKED": "Baked",
    "FAILED": "Failed",
    "PARTIAL": "Partial",
    "CANCEL_REQUESTED": "Cancelling",
    "CANCELLED": "Cancelled",
    "NOT_BAKED": "Not baked",
    "READY_TO_BAKE": "Not baked",
    "STALE": "Out of date",
}


def _props(context):
    return context.scene.blastfx


def _split(layout):
    layout.use_property_split = True
    layout.use_property_decorate = False
    return layout


_STATUS_MEMO: dict = {}
_STATUS_TTL_S = 1.0


def _cached_status(props, blast_id, domain_settings, state_hash):
    """``cache.status`` lists the cache folder and opens every grid file; the panel redraws on every mouse
    move, so the answer is kept for a second (a running bake changes the key and is never stale)."""
    flags = tuple(
        bool(getattr(domain_settings, name, False))
        for name in ("is_cache_baking_data", "is_cache_baking_noise", "has_cache_baked_data", "has_cache_baked_noise")
    )
    key = (blast_id, state_hash, getattr(domain_settings, "cache_data_format", None), flags,
           props.cache_subdir, bpy.data.filepath)
    now = time.monotonic()
    hit = _STATUS_MEMO.get(key)
    if hit is not None and now - hit[0] < _STATUS_TTL_S:
        return hit[1]
    value = status(props, blast_id, domain_settings, state_hash)
    if len(_STATUS_MEMO) > 64:
        _STATUS_MEMO.clear()
    _STATUS_MEMO[key] = (now, value)
    return value


def _controller(context):
    obj = context.active_object
    return obj if obj is not None and obj.get("blastfx_controller") else None


def _domain_settings(controller):
    if not controller.users_collection:
        return None
    domain = next(
        (o for o in controller.users_collection[0].objects if o.get("blastfx_role") == "domain"),
        None,
    )
    if domain is None:
        return None
    mod = domain.modifiers.get("BlastFX Fluid") or domain.modifiers.get("Fluid")
    return mod.domain_settings if mod else None


def _plan(context):
    """The same plan Create would build, or None if the settings are invalid."""
    try:
        from ..core.blast_plan import plan_blast

        return plan_blast(_props(context), context.scene)
    except Exception:
        return None


def _wrapped(layout, text, icon="INFO", width=38):
    """Multi-line label: sidebar labels truncate long text instead of wrapping."""
    import textwrap

    for index, line in enumerate(textwrap.wrap(text, width) or [""]):
        layout.label(text=line, icon=icon if index == 0 else "BLANK1")


def _readout(layout, rows):
    col = layout.column(align=True)
    for label, value in rows:
        row = col.split(factor=0.5)
        row.label(text=label)
        row.label(text=value)


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlastFX"


class _Sub(_Base):
    bl_parent_id = "BLASTFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}


class BLASTFX_MT_presets(Menu):
    bl_label = "Presets"
    bl_idname = "BLASTFX_MT_presets"

    def draw(self, context):
        for preset in all_presets():
            op = self.layout.operator("blastfx.apply_preset", text=preset.label)
            op.preset_id = preset.id


class BLASTFX_PT_main(_Base, Panel):
    bl_label = "BlastFX"
    bl_idname = "BLASTFX_PT_main"

    def draw(self, context):
        props = _props(context)
        layout = self.layout
        running = active_job() is not None
        preset = registry.PRESETS.get(props.preset_id)

        layout.menu("BLASTFX_MT_presets", text=preset.label if preset else "Choose a Preset", icon="PRESET")
        if preset and preset.description:
            _wrapped(layout.column(align=True), preset.description)

        col = layout.column()
        col.enabled = not running
        col.scale_y = 1.4
        col.operator("blastfx.create", icon="ADD")
        layout.operator("blastfx.create_batch", text="Create Batch...", icon="DUPLICATE")

        controller = _controller(context)
        if controller is None:
            layout.label(text="Select a blast controller to edit it.", icon="RESTRICT_SELECT_OFF")
            return
        box = layout.box()
        box.label(text=controller.name, icon="OUTLINER_OB_EMPTY")
        row = box.row(align=True)
        row.enabled = not running
        row.operator("blastfx.rebuild", icon="FILE_REFRESH")
        row.operator("blastfx.duplicate", icon="DUPLICATE", text="Duplicate")
        box.separator()
        remove = box.row()
        remove.enabled = not running
        remove.operator("blastfx.remove", icon="TRASH")


class BLASTFX_PT_explosion(_Base, Panel):
    bl_label = "Explosion"
    bl_idname = "BLASTFX_PT_explosion"
    bl_parent_id = "BLASTFX_PT_main"

    def draw(self, context):
        props = _props(context)
        layout = _split(self.layout)
        layout.enabled = active_job() is None
        layout.prop(props, "explosion_type")
        col = layout.column(align=True)
        if props.explosion_type == "NUCLEAR":
            col.prop(props, "yield_kt")
        else:
            col.prop(props, "scale")
        col = layout.column(align=True)
        col.prop(props, "speed")
        col.prop(props, "duration")
        if props.duration <= 0.0:
            plan = _plan(context)
            if plan is not None:
                layout.label(text=f"Automatic: {plan.physical.characteristic_time_s:.1f} s of event", icon="INFO")
        col = layout.column(align=True)
        col.prop(props, "start_frame")
        col.prop(props, "seed")


class BLASTFX_PT_components(_Base, Panel):
    bl_label = "Components"
    bl_idname = "BLASTFX_PT_components"
    bl_parent_id = "BLASTFX_PT_main"

    def draw(self, context):
        props = _props(context)
        layout = _split(self.layout)
        layout.enabled = active_job() is None
        col = layout.column(heading="Simulation", align=True)
        col.prop(props, "use_fireball")
        col.prop(props, "use_stem")
        col.prop(props, "use_dust")
        col.prop(props, "use_shockwave")
        col.prop(props, "use_debris")
        if props.explosion_type == "NUCLEAR":
            col.prop(props, "use_rapatronic")
        col = layout.column(heading="Cinematic", align=True)
        col.prop(props, "use_flash")
        col.prop(props, "use_camera_fx")
        sub = col.row()
        sub.active = props.use_camera_fx
        sub.prop(props, "camera_fx_active")
        col.prop(props, "use_exposure")
        col.prop(props, "use_heat_distortion")
        camera = context.scene.camera
        if props.use_camera_fx and camera is not None:
            owner = "BlastFX" if camera.get("blastfx_generated") else "yours"
            layout.label(text=f"Scene camera: {camera.name} ({owner})", icon="CAMERA_DATA")


class BLASTFX_PT_look(_Sub, Panel):
    bl_label = "Look"
    bl_idname = "BLASTFX_PT_look"

    def draw(self, context):
        props = _props(context)
        layout = _split(self.layout)
        layout.enabled = active_job() is None
        col = layout.column(align=True)
        col.prop(props, "fire_temperature")
        col.prop(props, "smoke_density")
        col.prop(props, "turbulence")
        col.prop(props, "intensity")


class BLASTFX_PT_cache(_Base, Panel):
    bl_label = "Cache and Bake"
    bl_idname = "BLASTFX_PT_cache"
    bl_parent_id = "BLASTFX_PT_main"

    def draw(self, context):
        props = _props(context)
        layout = _split(self.layout)
        running = active_job() is not None

        settings = layout.column()
        settings.enabled = not running
        settings.prop(props, "quality", expand=True)
        col = settings.column(align=True)
        col.prop(props, "resolution")
        noise = col.row()
        noise.active = props.quality == "FINAL"
        noise.prop(props, "noise_upres")
        settings.prop(props, "cache_subdir")
        if props.quality != "FINAL":
            settings.label(text="Draft and Preview skip the noise pass.", icon="INFO")

        controller = _controller(context)
        if controller is None:
            if not running:
                layout.operator("blastfx.bake_all", icon="RENDER_ANIMATION")
            return

        domain_settings = _domain_settings(controller)
        cache_state = _cached_status(props, controller.get("blastfx_id"), domain_settings,
                                     controller.get("blastfx_physics_state"))
        worker = job_status(controller)
        state = worker.get("state") if worker else cache_state
        box = layout.box()
        _readout(box, [("State", _STATE_LABELS.get(state, state.replace("_", " ").title()))])
        if domain_settings is not None:
            _readout(box, [
                ("Resolution", str(domain_settings.resolution_max)),
                ("Frames", f"{domain_settings.cache_frame_start}-{domain_settings.cache_frame_end}"),
            ])
        if worker and running:
            elapsed = int(worker.get("elapsed_seconds", 0))
            rows = [("Elapsed", f"{elapsed // 60:02d}:{elapsed % 60:02d}")]
            if "current_frame" in worker and "frame_end" in worker:
                rows.append(("Frame", f"{worker['current_frame']} / {worker['frame_end']}"))
            if worker.get("eta_seconds") is not None:
                eta = int(worker["eta_seconds"])
                rows.append(("Remaining", f"~{eta // 60:02d}:{eta % 60:02d}"))
            _readout(box, rows)
            if "progress" in worker:
                box.progress(factor=float(worker["progress"]), text=f"{worker['progress'] * 100:.0f}%")
        if worker and worker.get("message") and state in {"FAILED", "PARTIAL"}:
            box.alert = True
            box.label(text=worker["message"][:96], icon="ERROR")
        if pending_bakes():
            box.label(text=f"Queue: {len(pending_bakes())} pending", icon="SORTTIME")

        if running:
            layout.operator("blastfx.cancel_bake", icon="CANCEL")
            return
        col = layout.column()
        col.scale_y = 1.2
        col.operator("blastfx.bake", icon="REC")
        layout.operator("blastfx.bake_all", icon="RENDER_ANIMATION")
        layout.separator()
        layout.operator("blastfx.free", icon="TRASH")


class BLASTFX_PT_readout(_Sub, Panel):
    bl_label = "Readout"
    bl_idname = "BLASTFX_PT_readout"

    def draw(self, context):
        layout = self.layout
        plan = _plan(context)
        if plan is None:
            layout.label(text="Settings are invalid; see Diagnostics.", icon="ERROR")
            return
        physical, numerical = plan.physical, plan.numerical
        radius = physical.characteristic_radius_m
        voxels_per_radius = radius / max(numerical.voxel_size_m, 1e-9)
        frames = plan.frame_end - plan.frame_start
        _readout(layout, [
            ("Fireball diameter", f"{plan.scale_m:.1f} m"),
            ("Time unit (T)", f"{physical.time_unit_s:.2f} s"),
            ("Event length", f"{physical.characteristic_time_s:.1f} s"),
            ("Shot", f"{frames} frames at {plan.fps:g} fps"),
            ("Solver time scale", f"{numerical.time_scale_multiplier:.2f}"),
            ("Resolution", f"{numerical.domain_resolution}"),
            ("Voxels per radius", f"{voxels_per_radius:.0f}"),
            ("Voxel size", f"{numerical.voxel_size_m:.2f} m"),
            ("Noise pass", f"x{numerical.noise_upres}" if numerical.noise_upres > 1 else "off"),
        ])
        for warning in plan.warnings:
            box = layout.box()
            box.alert = True
            box.label(text=warning[:90], icon="ERROR")


class BLASTFX_PT_diagnostics(_Sub, Panel):
    bl_label = "Diagnostics"
    bl_idname = "BLASTFX_PT_diagnostics"

    def draw(self, context):
        from ..core.validation import validate_props, validate_scene

        layout = self.layout
        props = _props(context)
        result = validate_props(props)
        scene_result = validate_scene(context.scene)
        plan = _plan(context)
        errors = result.errors + scene_result.errors
        warnings = result.warnings + scene_result.warnings + list(plan.warnings if plan else ())
        if not errors and not warnings:
            layout.label(text="No issues found.", icon="CHECKMARK")
        for message in errors:
            layout.label(text=message[:90], icon="ERROR")
        for message in warnings:
            layout.label(text=message[:90], icon="INFO")
        layout.operator("blastfx.validate", icon="CHECKMARK")


class BLASTFX_PT_presets(_Sub, Panel):
    bl_label = "Preset Files"
    bl_idname = "BLASTFX_PT_presets"

    def draw(self, context):
        self.layout.operator("blastfx.save_preset", icon="EXPORT")


CLASSES = (
    BLASTFX_MT_presets,
    BLASTFX_PT_main,
    BLASTFX_PT_explosion,
    BLASTFX_PT_components,
    BLASTFX_PT_look,
    BLASTFX_PT_cache,
    BLASTFX_PT_readout,
    BLASTFX_PT_diagnostics,
    BLASTFX_PT_presets,
)
