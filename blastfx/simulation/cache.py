from pathlib import Path

import bpy

from ..core.cache import (
    prepare_cache,
    active_cache_path,
)


def _domain_modifier(domain_obj):
    if domain_obj.type != "MESH":
        raise RuntimeError(f"Mantaflow domain must be a mesh object: {domain_obj.name}")
    mod = domain_obj.modifiers.get("BlastFX Fluid") or domain_obj.modifiers.get("Fluid")
    if mod is None or mod.type != "FLUID" or mod.fluid_type != "DOMAIN":
        raise RuntimeError(f"{domain_obj.name} does not have a valid Mantaflow DOMAIN modifier")
    if mod.domain_settings is None:
        raise RuntimeError(f"{domain_obj.name} has no initialized Mantaflow domain settings")
    return mod


def _flow_objects(domain_obj, collection):
    flows = []
    for obj in collection.objects:
        if (
            obj == domain_obj
            or obj.type != "MESH"
            or not obj.get("blastfx_generated", False)
            or obj.get("blastfx_id") != domain_obj.get("blastfx_id")
        ):
            continue
        mod = obj.modifiers.get("BlastFX Fluid") or obj.modifiers.get("Fluid")
        if mod and mod.type == "FLUID" and mod.fluid_type == "FLOW" and mod.flow_settings is not None:
            flows.append(obj)
    return flows


def configure_cache(domain_obj, context, collection, controller, config, quality):
    mod = _domain_modifier(domain_obj)
    domain = mod.domain_settings
    props = context.scene.blastfx
    fps = context.scene.render.fps / context.scene.render.fps_base
    start = int(config.get("start_frame", 1))
    duration_s = config.get("timeline_duration_s", config["physical"].characteristic_time_s)
    end = start + max(1, int(round(duration_s * fps)))

    cache_dir = prepare_cache(
        props,
        controller["blastfx_id"],
        state_hash=controller.get("blastfx_physics_state", ""),
        frame_start=start,
        frame_end=end,
    )
    domain.cache_type = "ALL"
    domain.cache_directory = str(cache_dir)
    domain.cache_frame_start = start
    domain.cache_frame_end = end
    domain.cache_data_format = "OPENVDB"
    if getattr(domain, "use_noise", False):
        domain.cache_noise_format = "OPENVDB"
    return domain


def validate_bake_setup(context, domain_obj):
    """Validate the complete domain/flow wiring before starting a costly bake."""
    mod = _domain_modifier(domain_obj)
    domain = mod.domain_settings

    if domain.domain_type != "GAS":
        raise RuntimeError(f"Blast domain is {domain.domain_type!r}; expected GAS")
    if domain.cache_type != "ALL":
        raise RuntimeError(f"Blast cache type is {domain.cache_type!r}; expected ALL for Bake Simulation")
    if domain.cache_frame_end < domain.cache_frame_start:
        raise RuntimeError("Blast cache frame range is invalid")
    if int(domain.resolution_max) < 16:
        raise RuntimeError("Blast domain resolution is below the supported minimum (16)")
    if not domain.cache_directory:
        raise RuntimeError("Blast cache directory is empty")

    collection = next((c for c in domain_obj.users_collection if c.name.startswith("Blast_")), None)
    if collection is None:
        raise RuntimeError("Blast domain is not inside a Blast FX collection")
    flows = _flow_objects(domain_obj, collection)
    if not flows:
        raise RuntimeError("Blast domain has no valid Mantaflow FLOW objects")

    cache_dir = Path(bpy.path.abspath(domain.cache_directory))
    expected_cache_dir = active_cache_path(
        context.scene.blastfx, domain_obj.get("blastfx_id")
    ).resolve()
    if cache_dir.resolve() != expected_cache_dir:
        raise RuntimeError("Blast cache directory is not isolated to this blast.")
    cache_dir.mkdir(parents=True, exist_ok=True)
    probe = cache_dir / ".blastfx_write_test"
    try:
        probe.write_text("ok")
    finally:
        try:
            probe.unlink()
        except OSError:
            pass

    return domain, flows


def free(context, domain_obj):
    _domain_modifier(domain_obj)
    for obj in context.selected_objects:
        obj.select_set(False)
    domain_obj.select_set(True)
    context.view_layer.objects.active = domain_obj
    result = bpy.ops.fluid.free_all()
    if "CANCELLED" in result:
        raise RuntimeError("Mantaflow free operation was cancelled")
    from ..core.cache import clear_baked_marker
    clear_baked_marker(context.scene.blastfx, domain_obj.get("blastfx_id"))
    return result
