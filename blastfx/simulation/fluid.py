"""Blender 5.2 Mantaflow helpers.

Keep Blender RNA access in one place so API drift is caught consistently.
"""
import bpy
import bmesh
from mathutils import Vector


def add_mesh_object(collection, name, builder, location=None):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    bm = bmesh.new()
    try:
        builder(bm)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if location is not None:
        obj.location = location
    return obj


def configure_fluid_modifier(obj, fluid_type):
    if obj.type != "MESH":
        raise TypeError(f"Mantaflow {fluid_type} object must be a mesh: {obj.name}")
    mod = obj.modifiers.get("BlastFX Fluid")
    if mod is None:
        mod = obj.modifiers.new(name="BlastFX Fluid", type="FLUID")
    mod.fluid_type = fluid_type
    # Settings live in different slots per fluid type.
    if fluid_type == "DOMAIN":
        settings = mod.domain_settings
    elif fluid_type == "EFFECTOR":
        settings = mod.effector_settings
    else:
        settings = mod.flow_settings
    if settings is None:
        raise RuntimeError(
            f"Blender 5.2 did not initialize Mantaflow {fluid_type} settings for {obj.name}"
        )
    return mod, settings


def configure_flow(flow, *, flow_type="SMOKE", temperature=1.0, density=1.0,
                   fuel=0.0, velocity=(0.0, 0.0, 0.0), velocity_normal=0.0,
                   velocity_random=0.0, surface_distance=1.0,
                   volume_density=1.0, subframes=2, flow_source="MESH",
                   particle_system=None):
    """Configure only FluidFlowSettings properties documented by Blender 5.2."""
    required = {
        "flow_source": flow_source,
        "flow_type": flow_type,
        "flow_behavior": "INFLOW",
        "temperature": max(-10.0, min(10.0, float(temperature))),
        "density": max(0.0, min(10.0, float(density))),
        "fuel_amount": max(0.0, min(10.0, float(fuel))),
        "surface_distance": max(0.0, min(10.0, float(surface_distance))),
        "volume_density": max(0.0, min(1.0, float(volume_density))),
        "use_initial_velocity": True,
        "velocity_coord": Vector(velocity),
        "velocity_normal": max(-100.0, min(100.0, float(velocity_normal))),
        "velocity_random": max(0.0, min(10.0, float(velocity_random))),
        "subframes": max(0, min(200, int(subframes))),
        "use_inflow": True,
    }
    if particle_system is not None:
        # Blender 5.2's pointer property name (older builds: flow_particle_system)
        required["particle_system"] = particle_system
    for key, value in required.items():
        if not hasattr(flow, key):
            raise RuntimeError(
                f"FluidFlowSettings.{key} is unavailable in this Blender version"
            )
        try:
            setattr(flow, key, value)
        except Exception as exc:
            raise RuntimeError(f"Unable to set FluidFlowSettings.{key}: {exc}") from exc
    return flow


def keyframe_inflow(flow, start_frame, end_frame):
    """Emit for a controlled physical interval rather than relying on permanent inflow."""
    start = int(start_frame)
    end = max(start + 1, int(end_frame))
    flow.use_inflow = False
    flow.keyframe_insert("use_inflow", frame=start - 1)
    flow.use_inflow = True
    flow.keyframe_insert("use_inflow", frame=start)
    flow.keyframe_insert("use_inflow", frame=end)
    flow.use_inflow = False
    flow.keyframe_insert("use_inflow", frame=end + 1)


def primitive_flow(collection, name, location, primitive, **kwargs):
    if primitive == "sphere":
        radius = kwargs.get("radius", 1.0)
        segments = kwargs.get("segments", 32)
        rings = kwargs.get("rings", 16)
        return add_mesh_object(
            collection, name,
            lambda bm: bmesh.ops.create_uvsphere(
                bm, u_segments=segments, v_segments=rings, radius=radius
            ),
            location,
        )
    if primitive == "icosphere":
        return add_mesh_object(
            collection, name,
            lambda bm: bmesh.ops.create_icosphere(
                bm, subdivisions=kwargs.get("subdivisions", 2), radius=kwargs.get("radius", 1.0)
            ),
            location,
        )
    if primitive == "cylinder":
        return add_mesh_object(
            collection, name,
            lambda bm: bmesh.ops.create_cone(
                bm, cap_ends=True, segments=kwargs.get("segments", 48),
                radius1=kwargs.get("radius", 1.0), radius2=kwargs.get("radius", 1.0),
                depth=kwargs.get("depth", 1.0)
            ),
            location,
        )
    if primitive == "cone":
        return add_mesh_object(
            collection, name,
            lambda bm: bmesh.ops.create_cone(
                bm, cap_ends=True, segments=kwargs.get("segments", 32),
                radius1=kwargs.get("radius1", 1.0), radius2=kwargs.get("radius2", 0.5),
                depth=kwargs.get("depth", 1.0)
            ),
            location,
        )
    raise ValueError(f"Unknown flow primitive: {primitive}")
