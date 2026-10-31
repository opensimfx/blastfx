from bpy.types import Panel

from ..presets.registry import all_presets
from ..core.cache import status
from ..core.bake_job import active_job, job_status, pending_bakes


class BLASTFX_PT_main(Panel):
    bl_label = "Blast FX"
    bl_idname = "BLASTFX_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blast FX"

    def draw(self, context):
        props = context.scene.blastfx
        layout = self.layout
        running = active_job() is not None
        settings = layout.column()
        settings.enabled = not running

        box = settings.box()
        box.label(text="Explosion")
        box.prop(props, "explosion_type")
        box.prop(props, "preset_id")
        box.prop(props, "scale")
        box.prop(props, "intensity")
        box.prop(props, "speed")
        box.prop(props, "start_frame")
        box.prop(props, "duration")
        box.prop(props, "seed")


        box = settings.box()
        box.label(text="Physical Model")
        box.prop(props, "reference_energy")
        box.label(text="SI scale is interpreted in metres.")
        box.label(text="Timing is converted from seconds using scene FPS.")

        box = settings.box()
        box.label(text="Components")
        box.prop(props, "use_fireball")
        box.prop(props, "use_stem")
        box.prop(props, "use_dust")
        box.prop(props, "use_shockwave")
        box.prop(props, "use_debris")
        box.prop(props, "use_flash")
        box.prop(props, "use_camera_fx")
        if props.use_camera_fx:
            camera = context.scene.camera
            if camera and camera.get("blastfx_generated"):
                box.label(text=f"Active Camera: {camera.name}")
        box.prop(props, "use_exposure")
        box.prop(props, "use_heat_distortion")

        box = settings.box()
        box.label(text="Simulation")
        box.prop(props, "quality")
        box.prop(props, "resolution")
        box.prop(props, "noise_upres")
        box.prop(props, "turbulence")
        box.prop(props, "smoke_density")
        box.prop(props, "fire_temperature")

        layout.operator("blastfx.create", icon="PHYSICS")
        layout.operator("blastfx.duplicate", icon="DUPLICATE")
        layout.operator("blastfx.create_batch", icon="RNA")
        layout.operator("blastfx.validate", icon="CHECKMARK")

        box = layout.box()
        box.label(text="Cache")
        if not running:
            box.operator("blastfx.bake_all", icon="RENDER_ANIMATION")
        if pending_bakes():
            box.label(text=f"Bake queue: {len(pending_bakes())} pending")
        controller = context.active_object if context.active_object and context.active_object.get("blastfx_controller") else None
        if controller:
            domain_obj = next((o for o in controller.users_collection[0].objects if o.get("blastfx_role") == "domain"), None) if controller.users_collection else None
            domain_settings = None
            if domain_obj:
                mod = domain_obj.modifiers.get("BlastFX Fluid") or domain_obj.modifiers.get("Fluid")
                if mod and mod.domain_settings:
                    domain_settings = mod.domain_settings
            cache_status = status(
                props,
                controller["blastfx_id"],
                domain_settings,
                controller.get("blastfx_physics_state"),
            )
            worker_status = job_status(controller)
            state = worker_status.get("state") if worker_status else cache_status
            state_labels = {
                "BAKING_DATA": "Baking",
                "BAKING_NOISE": "Baking",
                "FINALIZING": "Finalizing",
                "COMPLETED": "Completed",
                "FAILED": "Failed",
                "PARTIAL": "Partial",
                "CANCEL_REQUESTED": "Cancelling",
                "CANCELLED": "Cancelled",
            }
            display_state = state_labels.get(state, state.replace("_", " ").title())
            box.label(text="BAKE")
            box.label(text=f"State: {display_state}", icon="TIME" if running else "CHECKMARK")
            if worker_status:
                elapsed = int(worker_status.get("elapsed_seconds", 0))
                if "current_frame" in worker_status:
                    box.label(
                        text=(
                            f"Frame: {worker_status['current_frame']} / "
                            f"{worker_status['frame_end']}"
                        )
                    )
                if "progress" in worker_status:
                    box.label(text=f"Progress: {worker_status['progress'] * 100:.1f}%")
                else:
                    box.label(text="Waiting for first cached frame...")
                box.label(
                    text=f"Elapsed: {elapsed // 60:02d}:{elapsed % 60:02d}"
                )
                if state in {"BAKING_DATA", "BAKING_NOISE"} and worker_status.get("eta_seconds") is not None:
                    eta = int(worker_status["eta_seconds"])
                    box.label(text=f"Remaining: ~{eta // 60:02d}:{eta % 60:02d}")
                elif state in {"BAKING_DATA", "BAKING_NOISE"}:
                    box.label(text="Remaining: Calculating...")
                elif state == "FINALIZING":
                    box.label(text="ETA: —")
                if worker_status.get("message"):
                    box.label(text=worker_status["message"][:96])
                if worker_status.get("generation"):
                    box.label(text=f"Generation: {worker_status['generation'][:12]}")
            if domain_settings:
                box.label(text=f"Resolution: {domain_settings.resolution_max}")
                box.label(text=f"Frames: {domain_settings.cache_frame_start}-{domain_settings.cache_frame_end}")
            if running:
                box.operator("blastfx.cancel_bake", icon="CANCEL")
            else:
                box.operator("blastfx.bake", icon="REC")
                box.operator("blastfx.free", icon="LOOP_BACK")
                box.operator("blastfx.rebuild", icon="FILE_REFRESH")
                box.operator("blastfx.remove", icon="TRASH")
        else:
            box.label(text="Select a Blast FX controller")

        box = layout.box()
        box.label(text="Factory Presets")
        for preset in all_presets():
            op = box.operator("blastfx.apply_preset", text=preset.label)
            op.preset_id = preset.id


CLASSES = (BLASTFX_PT_main,)
