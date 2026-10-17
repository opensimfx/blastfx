import bpy
from .collections import create_blast_collection, remove_collection
from .controller import new_blast_id, tag_controller, is_controller
from .validation import validate_props, validate_scene
from .physics import AmbientConditions, PhysicalConfig, derive_physics, validate_physical_config, gravity_magnitude
from .physical_state import build_physical_state, state_hash
from .blender_api import runtime_self_test
from .cache import invalidate as invalidate_cache
from ..simulation import build_explosion
from ..simulation.physical_config import build_simulation_config
from ..animation import build_animation
from .domain_envelope import build_domain_envelope, envelope_state
from .explosion_profile import profile_for, profile_state


def create_explosion(context):
    props = context.scene.blastfx
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

    physical_config = PhysicalConfig(
        scale_m=float(props.scale),
        reference_energy=float(props.reference_energy),
        intensity=float(props.intensity),
        duration_s=float(props.duration),
        ambient=AmbientConditions(gravity=gravity_magnitude(context.scene.gravity)),
    )

    physics_errors = validate_physical_config(physical_config)
    if physics_errors:
        raise ValueError("; ".join(physics_errors))

    derived = derive_physics(physical_config)
    profile = profile_for(props.explosion_type)
    numerical = build_simulation_config(
        derived,
        props.quality,
        props.resolution,
        props.noise_upres,
        props.seed,
        props.turbulence,
        props.smoke_density,
        props.fire_temperature,
        profile,
    )
    fps = context.scene.render.fps / context.scene.render.fps_base
    timeline_duration = derived.characteristic_time_s / max(float(props.speed), 0.05)
    frame_start = int(props.start_frame)
    frame_end = frame_start + max(1, int(round(timeline_duration * fps)))
    domain_envelope = build_domain_envelope(
        derived,
        numerical,
        gravity_magnitude(context.scene.gravity),
        timeline_duration,
        profile,
    )

    blast_id = new_blast_id()
    collection = create_blast_collection(context.scene, blast_id)

    controller_data = bpy.data.objects.new(f"BlastController_{blast_id}", None)
    controller_data.empty_display_type = "SPHERE"
    controller_data.location = context.scene.cursor.location
    collection.objects.link(controller_data)
    tag_controller(controller_data, props, blast_id)

    physical_state = build_physical_state(
        props, context.scene, blast_id, derived, numerical, frame_start, frame_end,
        envelope_state(domain_envelope),
        profile_state(profile),
    )
    controller_data["blastfx_physics_state"] = state_hash(physical_state)
    controller_data["blastfx_characteristic_radius_m"] = derived.characteristic_radius_m
    controller_data["blastfx_characteristic_time_s"] = derived.characteristic_time_s
    controller_data["blastfx_characteristic_velocity_mps"] = derived.characteristic_velocity_mps
    controller_data["blastfx_domain_envelope"] = envelope_state(domain_envelope)
    controller_data["blastfx_explosion_profile"] = profile_state(profile)

    try:
        build_explosion(context, collection, controller_data, props)
        build_animation(context, collection, controller_data, props)
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

    # Validate current props
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

    physical_config = PhysicalConfig(
        scale_m=float(props.scale),
        reference_energy=float(props.reference_energy),
        intensity=float(props.intensity),
        duration_s=float(props.duration),
        ambient=AmbientConditions(gravity=gravity_magnitude(context.scene.gravity)),
    )

    physics_errors = validate_physical_config(physical_config)
    if physics_errors:
        raise ValueError("; ".join(physics_errors))

    derived = derive_physics(physical_config)
    profile = profile_for(props.explosion_type)
    numerical = build_simulation_config(
        derived,
        props.quality,
        props.resolution,
        props.noise_upres,
        props.seed,
        props.turbulence,
        props.smoke_density,
        props.fire_temperature,
        profile,
    )
    fps = context.scene.render.fps / context.scene.render.fps_base
    timeline_duration = derived.characteristic_time_s / max(float(props.speed), 0.05)
    frame_start = int(props.start_frame)
    frame_end = frame_start + max(1, int(round(timeline_duration * fps)))
    domain_envelope = build_domain_envelope(
        derived,
        numerical,
        gravity_magnitude(context.scene.gravity),
        timeline_duration,
        profile,
    )

    # Invalidate cache first
    invalidate_cache(props, blast_id)

    # Remove all generated objects in the collection (keep user objects)
    for obj in list(collection.objects):
        if obj != controller and obj.get("blastfx_generated", False):
            bpy.data.objects.remove(obj, do_unlink=True)

    # Update controller tags
    tag_controller(controller, props, blast_id)
    controller["blastfx_characteristic_radius_m"] = derived.characteristic_radius_m
    controller["blastfx_characteristic_time_s"] = derived.characteristic_time_s
    controller["blastfx_characteristic_velocity_mps"] = derived.characteristic_velocity_mps
    controller["blastfx_domain_envelope"] = envelope_state(domain_envelope)
    controller["blastfx_explosion_profile"] = profile_state(profile)

    physical_state = build_physical_state(
        props, context.scene, blast_id, derived, numerical, frame_start, frame_end,
        envelope_state(domain_envelope),
        profile_state(profile),
    )
    controller["blastfx_physics_state"] = state_hash(physical_state)

    # Rebuild simulation and animation
    build_explosion(context, collection, controller, props)
    build_animation(context, collection, controller, props)

    return controller
