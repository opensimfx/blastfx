import bpy
from .collections import create_blast_collection, remove_collection
from .controller import new_blast_id, tag_controller, is_controller
from .validation import validate_props, validate_scene
from .physics import validate_physical_config
from .physical_state import build_physical_state, state_hash
from .blender_api import runtime_self_test
from .cache import invalidate as invalidate_cache
from .blast_plan import plan_blast
from ..simulation import build_explosion
from ..animation import build_animation
from .domain_envelope import envelope_state
from .explosion_profile import profile_state
from ..render.settings import configure_render_settings


def _validated_plan(context, props):
    """Validate props/scene/runtime and return (plan, validation)."""
    validation = validate_props(props)
    scene_validation = validate_scene(context.scene)
    validation.errors.extend(scene_validation.errors)
    validation.warnings.extend(scene_validation.warnings)
    validation.ok = not validation.errors
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    api_errors = runtime_self_test()
    if api_errors:
        raise RuntimeError("Blender/Mantaflow API self-test failed: " + "; ".join(api_errors))

    plan = plan_blast(props, context.scene)
    physics_errors = validate_physical_config(plan.physical_config)
    if physics_errors:
        raise ValueError("; ".join(physics_errors))
    validation.warnings.extend(plan.warnings)
    return plan, validation


def _tag_plan(controller, plan, props, scene, blast_id):
    """Store the plan's cache identity and headline values on the controller."""
    physical = plan.physical
    physical_state = build_physical_state(
        props, scene, blast_id, physical, plan.numerical, plan.frame_start, plan.frame_end,
        envelope_state(plan.envelope),
        profile_state(plan.profile),
    )
    controller["blastfx_physics_state"] = state_hash(physical_state)
    controller["blastfx_characteristic_radius_m"] = physical.characteristic_radius_m
    controller["blastfx_characteristic_time_s"] = physical.characteristic_time_s
    controller["blastfx_characteristic_velocity_mps"] = physical.characteristic_velocity_mps
    controller["blastfx_time_unit_s"] = physical.time_unit_s
    controller["blastfx_solver_time_scale"] = plan.numerical.time_scale_multiplier
    controller["blastfx_domain_envelope"] = envelope_state(plan.envelope)
    controller["blastfx_explosion_profile"] = profile_state(plan.profile)


def create_explosion(context):
    props = context.scene.blastfx
    plan, validation = _validated_plan(context, props)

    # Volume-heavy explosions need Cycles volume settings; sample count
    # follows the active quality (DRAFT 32 / PREVIEW 128 / FINAL 512).
    configure_render_settings(context.scene, quality=props.quality)

    blast_id = new_blast_id()
    collection = create_blast_collection(context.scene, blast_id)

    controller_data = bpy.data.objects.new(f"BlastController_{blast_id}", None)
    controller_data.empty_display_type = "SPHERE"
    controller_data.location = context.scene.cursor.location
    collection.objects.link(controller_data)
    tag_controller(controller_data, props, blast_id)
    _tag_plan(controller_data, plan, props, context.scene, blast_id)

    try:
        build_explosion(context, collection, controller_data, props, plan)
        build_animation(context, collection, controller_data, props, plan)
    except Exception:
        # Creation is transactional: don't leave a half-built blast behind
        # when a Mantaflow/material/animation API error occurs.
        invalidate_cache(props, blast_id)
        remove_collection(collection)
        raise

    return controller_data, validation


def remove_explosion(controller):
    if not controller:
        raise ValueError("No Blast FX controller selected.")

    collection = next(
        (c for c in controller.users_collection if c.name.startswith("Blast_")),
        None,
    )
    if collection is None:
        raise ValueError("Blast controller is not inside a Blast FX collection.")

    props = bpy.context.scene.blastfx
    invalidate_cache(props, controller["blastfx_id"])
    remove_collection(collection)


def rebuild_explosion(context, controller):
    """Rebuild blast from controller properties + preset + seed + version."""
    if not is_controller(controller):
        raise ValueError("Object is not a Blast FX controller.")

    blast_id = controller["blastfx_id"]
    collection = next(
        (c for c in controller.users_collection if c.name.startswith("Blast_")),
        None,
    )
    if collection is None:
        raise ValueError("Controller not in a Blast FX collection.")

    props = context.scene.blastfx
    plan, validation = _validated_plan(context, props)

    # Invalidate cache first
    invalidate_cache(props, blast_id)

    # Remove all generated objects in the collection (keep user objects)
    for obj in list(collection.objects):
        if obj != controller and obj.get("blastfx_generated", False):
            bpy.data.objects.remove(obj, do_unlink=True)

    tag_controller(controller, props, blast_id)
    _tag_plan(controller, plan, props, context.scene, blast_id)

    # Rebuild simulation and animation
    build_explosion(context, collection, controller, props, plan)
    build_animation(context, collection, controller, props, plan)

    return list(validation.warnings)
