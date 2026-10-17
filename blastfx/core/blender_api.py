"""Runtime Blender 5.2 API self-test for Blast FX."""
import bpy
import bmesh


DOMAIN_REQUIRED = (
    "domain_type", "resolution_max", "time_scale", "use_adaptive_domain",
    "adapt_threshold", "adapt_margin", "cache_type", "cache_directory",
    "cache_frame_start", "cache_frame_end", "cache_data_format",
    "gravity", "alpha", "beta", "vorticity", "burning_rate", "flame_smoke",
    "flame_vorticity", "flame_ignition", "flame_max_temp", "use_noise",
    "noise_scale", "noise_strength", "noise_pos_scale", "noise_time_anim",
    "timesteps_min", "timesteps_max", "use_adaptive_timesteps",
)

FLOW_REQUIRED = (
    "flow_type", "flow_behavior", "density", "temperature", "fuel_amount",
    "surface_distance", "volume_density", "velocity_coord", "velocity_normal",
    "velocity_random", "subframes", "use_initial_velocity", "use_inflow",
)


def _temporary_mesh(name, kind):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bm = bmesh.new()
    try:
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=2.0)
        else:
            bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    bpy.context.scene.collection.objects.link(obj)
    return obj


def runtime_self_test():
    errors = []
    domain_obj = None
    flow_obj = None
    try:
        domain_obj = _temporary_mesh("__BlastFX_API_Test_Domain", "cube")
        mod = domain_obj.modifiers.new("BlastFX API Test Domain", "FLUID")
        mod.fluid_type = "DOMAIN"
        domain = mod.domain_settings
        if domain is None:
            errors.append("DOMAIN settings were not initialized.")
        else:
            if domain.domain_type != "GAS":
                domain.domain_type = "GAS"
            for attr in DOMAIN_REQUIRED + (
                "is_cache_baking_data",
                "is_cache_baking_noise",
                "has_cache_baked_data",
                "has_cache_baked_noise",
            ):
                if not hasattr(domain, attr):
                    errors.append(f"FluidDomainSettings.{attr} is unavailable.")

        flow_obj = _temporary_mesh("__BlastFX_API_Test_Flow", "sphere")
        mod = flow_obj.modifiers.new("BlastFX API Test Flow", "FLUID")
        mod.fluid_type = "FLOW"
        flow = mod.flow_settings
        if flow is None:
            errors.append("FLOW settings were not initialized.")
        else:
            for attr in FLOW_REQUIRED:
                if not hasattr(flow, attr):
                    errors.append(f"FluidFlowSettings.{attr} is unavailable.")

        if not hasattr(bpy.ops.fluid, "bake_all"):
            errors.append("bpy.ops.fluid.bake_all is unavailable.")
        if not hasattr(bpy.ops.fluid, "free_all"):
            errors.append("bpy.ops.fluid.free_all is unavailable.")

        material = bpy.data.materials.new("__BlastFX_API_Test_Volume")
        material.use_nodes = True
        volume_node = material.node_tree.nodes.new("ShaderNodeVolumePrincipled")
        for attr in ("Density Attribute", "Temperature Attribute", "Density",
                     "Temperature", "Blackbody Intensity"):
            if volume_node.inputs.get(attr) is None:
                errors.append(f"Principled Volume input {attr!r} is unavailable.")
        bpy.data.materials.remove(material, do_unlink=True)
    finally:
        for obj in (domain_obj, flow_obj):
            if obj is not None:
                bpy.data.objects.remove(obj, do_unlink=True)
    return errors
