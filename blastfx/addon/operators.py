import bpy
from bpy.types import Operator

from ..core.explosion import create_explosion, remove_explosion, rebuild_explosion
from ..presets.apply import apply_preset, save_current_as_preset
from ..core.validation import validate_props, validate_scene
from ..core.blender_api import runtime_self_test
from ..simulation.cache import free, validate_bake_setup
from ..core.bake_job import (
    active_job,
    request_cancel,
    start as start_bake_job,
    start_batch_bake,
)


class BLASTFX_OT_create(Operator):
    bl_idname = "blastfx.create"
    bl_label = "Create Blast"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if active_job():
            self.report({"ERROR"}, "Cancel the active bake before creating a blast.")
            return {"CANCELLED"}
        try:
            controller, validation = create_explosion(context)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        for warning in validation.warnings:
            self.report({"WARNING"}, warning)

        context.view_layer.objects.active = controller
        controller.select_set(True)
        self.report({"INFO"}, f"Created {controller.name}")
        return {"FINISHED"}


class BLASTFX_OT_apply_preset(Operator):
    bl_idname = "blastfx.apply_preset"
    bl_label = "Apply Preset"

    preset_id: bpy.props.StringProperty()

    def execute(self, context):
        if active_job():
            self.report({"ERROR"}, "Cancel the active bake before applying a preset.")
            return {"CANCELLED"}
        try:
            apply_preset(context.scene.blastfx, self.preset_id)
        except KeyError:
            self.report({"ERROR"}, f"Unknown preset: {self.preset_id}")
            return {"CANCELLED"}
        return {"FINISHED"}


class BLASTFX_OT_validate(Operator):
    bl_idname = "blastfx.validate"
    bl_label = "Validate"

    def execute(self, context):
        result = validate_props(context.scene.blastfx)
        scene_result = validate_scene(context.scene)
        result.errors.extend(scene_result.errors)
        result.warnings.extend(scene_result.warnings)
        result.ok = not result.errors
        for warning in result.warnings:
            self.report({"WARNING"}, warning)
        for error in result.errors:
            self.report({"ERROR"}, error)

        if not result.ok:
            return {"CANCELLED"}

        try:
            api_errors = runtime_self_test()
        except Exception as exc:
            self.report({"ERROR"}, f"Blender/Mantaflow API self-test failed: {exc}")
            return {"CANCELLED"}
        if api_errors:
            for error in api_errors:
                self.report({"ERROR"}, error)
            return {"CANCELLED"}

        self.report({"INFO"}, "Blast configuration and Blender 5.2 Mantaflow API are valid.")
        return {"FINISHED"}


class BLASTFX_OT_remove(Operator):
    bl_idname = "blastfx.remove"
    bl_label = "Remove Blast"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            if active_job():
                raise RuntimeError("A Blast FX bake is already running.")
            remove_explosion(context.active_object)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        self.report({"INFO"}, "Blast removed.")
        return {"FINISHED"}


class BLASTFX_OT_bake(Operator):
    bl_idname = "blastfx.bake"
    bl_label = "Bake Simulation"
    bl_options = {"REGISTER"}

    def execute(self, context):
        controller = context.active_object
        if not controller or not controller.get("blastfx_controller"):
            self.report({"ERROR"}, "Select a Blast FX controller.")
            return {"CANCELLED"}

        collection = next(
            (c for c in controller.users_collection if c.name.startswith("Blast_")),
            None,
        )
        if not collection:
            self.report({"ERROR"}, "Controller not in a Blast FX collection.")
            return {"CANCELLED"}

        domain_obj = None
        for obj in collection.objects:
            if obj.get("blastfx_role") == "domain":
                domain_obj = obj
                break

        if not domain_obj:
            self.report({"ERROR"}, "No domain found in blast collection.")
            return {"CANCELLED"}

        try:
            if active_job():
                self.report({"ERROR"}, "A Blast FX bake is already running.")
                return {"CANCELLED"}
            mod = domain_obj.modifiers.get("BlastFX Fluid") or domain_obj.modifiers.get("Fluid")
            if not mod:
                self.report({"ERROR"}, "No fluid modifier on domain.")
                return {"CANCELLED"}
            validate_bake_setup(context, domain_obj)
            start_bake_job(context, controller, domain_obj)
        except Exception as exc:
            self.report({"ERROR"}, f"Bake failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, "Mantaflow bake started in a background Blender worker.")
        return {"FINISHED"}


class BLASTFX_OT_cancel_bake(Operator):
    bl_idname = "blastfx.cancel_bake"
    bl_label = "Cancel Bake"

    def execute(self, context):
        try:
            request_cancel(context.active_object)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Bake cancellation requested.")
        return {"FINISHED"}


class BLASTFX_OT_free(Operator):
    bl_idname = "blastfx.free"
    bl_label = "Free Cache"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        controller = context.active_object
        if not controller or not controller.get("blastfx_controller"):
            self.report({"ERROR"}, "Select a Blast FX controller.")
            return {"CANCELLED"}

        collection = next(
            (c for c in controller.users_collection if c.name.startswith("Blast_")),
            None,
        )
        if not collection:
            self.report({"ERROR"}, "Controller not in a Blast FX collection.")
            return {"CANCELLED"}

        domain_obj = None
        for obj in collection.objects:
            if obj.get("blastfx_role") == "domain":
                domain_obj = obj
                break

        if not domain_obj:
            self.report({"ERROR"}, "No domain found in blast collection.")
            return {"CANCELLED"}

        try:
            if active_job():
                raise RuntimeError("Cancel the active bake before freeing the cache.")
            mod = domain_obj.modifiers.get("BlastFX Fluid") or domain_obj.modifiers.get("Fluid")
            if not mod:
                self.report({"ERROR"}, "No fluid modifier on domain.")
                return {"CANCELLED"}
            free(context, domain_obj)
        except Exception as exc:
            self.report({"ERROR"}, f"Free failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, "Cache freed.")
        return {"FINISHED"}


class BLASTFX_OT_rebuild(Operator):
    bl_idname = "blastfx.rebuild"
    bl_label = "Rebuild Blast"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        controller = context.active_object
        if not controller or not controller.get("blastfx_controller"):
            self.report({"ERROR"}, "Select a Blast FX controller.")
            return {"CANCELLED"}

        try:
            if active_job():
                raise RuntimeError("Cancel the active bake before rebuilding the blast.")
            rebuild_explosion(context, controller)
        except Exception as exc:
            self.report({"ERROR"}, f"Rebuild failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, "Blast rebuilt.")
        return {"FINISHED"}


class BLASTFX_OT_save_preset(Operator):
    bl_idname = "blastfx.save_preset"
    bl_label = "Save as Preset"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: bpy.props.StringProperty(name="Preset ID", default="custom_preset")
    label: bpy.props.StringProperty(name="Label", default="Custom Preset")
    description: bpy.props.StringProperty(name="Description", default="")

    def execute(self, context):
        try:
            save_current_as_preset(context.scene.blastfx, self.preset_id, self.label, self.description)
            # Reload presets to pick up the new file
            load_presets_from_directory()
        except Exception as exc:
            self.report({"ERROR"}, f"Save preset failed: {exc}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Preset '{self.label}' saved.")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class BLASTFX_OT_duplicate(Operator):
    bl_idname = "blastfx.duplicate"
    bl_label = "Duplicate Blast"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        source = context.active_object
        if not source or not source.get("blastfx_controller"):
            self.report({"ERROR"}, "Select a Blast FX controller.")
            return {"CANCELLED"}
        if active_job():
            self.report({"ERROR"}, "Cancel the active bake before duplicating a blast.")
            return {"CANCELLED"}

        props = context.scene.blastfx
        # The scene panel is the single source of configuration; sync it with
        # the source blast's captured identity so the duplicate matches it.
        try:
            props.explosion_type = source["blastfx_type"]
            props.preset_id = source["blastfx_preset"]
            props.seed = source["blastfx_seed"]
            controller, _validation = create_explosion(context)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        controller.location = source.location.copy()
        controller.location.x += 2.0 * float(props.scale)
        context.view_layer.objects.active = controller
        controller.select_set(True)
        self.report({"INFO"}, f"Created {controller.name} from {source.name}")
        return {"FINISHED"}


class BLASTFX_OT_create_batch(Operator):
    bl_idname = "blastfx.create_batch"
    bl_label = "Create Blast Batch"
    bl_options = {"REGISTER", "UNDO"}

    count: bpy.props.IntProperty(name="Count", default=3, min=1, max=8)
    spacing: bpy.props.FloatProperty(
        name="Spacing",
        default=10.0,
        min=0.0,
        soft_max=100.0,
        description="Metres between blast origins along +X",
    )
    seed_step: bpy.props.IntProperty(name="Seed Step", default=1, min=1, max=1000)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if active_job():
            self.report({"ERROR"}, "Cancel the active bake before creating blasts.")
            return {"CANCELLED"}

        props = context.scene.blastfx
        base_seed = int(props.seed)
        created = []
        try:
            for index in range(self.count):
                props.seed = base_seed + index * self.seed_step
                controller, _validation = create_explosion(context)
                controller.location.x += index * self.spacing
                created.append(controller)
        except Exception as exc:
            props.seed = base_seed
            self.report(
                {"ERROR"},
                f"Batch stopped after {len(created)} blast(s): {exc}",
            )
            return {"CANCELLED"}
        props.seed = base_seed
        if created:
            context.view_layer.objects.active = created[-1]
            created[-1].select_set(True)
        self.report(
            {"INFO"},
            f"Created {len(created)} blasts, seeds "
            f"{base_seed}..{base_seed + (self.count - 1) * self.seed_step}",
        )
        return {"FINISHED"}


class BLASTFX_OT_bake_all(Operator):
    bl_idname = "blastfx.bake_all"
    bl_label = "Bake All Blasts"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if active_job():
            self.report({"ERROR"}, "A Blast FX bake is already running.")
            return {"CANCELLED"}
        controllers = sorted(
            (o for o in bpy.data.objects if o.get("blastfx_controller")),
            key=lambda o: o.name,
        )
        if not controllers:
            self.report({"ERROR"}, "No blasts in the scene.")
            return {"CANCELLED"}
        try:
            result = start_batch_bake(context, controllers)
        except Exception as exc:
            self.report({"ERROR"}, f"Bake all failed: {exc}")
            return {"CANCELLED"}
        if not result["queued"]:
            self.report({"INFO"}, "All blasts already have valid caches.")
            return {"FINISHED"}
        self.report(
            {"INFO"},
            f"Bake queue: {result['queued']} blast(s) pending, first bake started.",
        )
        return {"FINISHED"}


CLASSES = (
    BLASTFX_OT_create,
    BLASTFX_OT_apply_preset,
    BLASTFX_OT_validate,
    BLASTFX_OT_remove,
    BLASTFX_OT_bake,
    BLASTFX_OT_cancel_bake,
    BLASTFX_OT_free,
    BLASTFX_OT_rebuild,
    BLASTFX_OT_save_preset,
    BLASTFX_OT_duplicate,
    BLASTFX_OT_create_batch,
    BLASTFX_OT_bake_all,
)
