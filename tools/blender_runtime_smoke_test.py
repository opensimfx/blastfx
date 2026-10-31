"""Blender 5.2-only Mantaflow smoke test.

Run with:
    blender --background --python tools/blender_runtime_smoke_test.py

This test deliberately uses Blender's runtime and is not a substitute for the
pure-Python test suite. It creates a minimal gas domain and flow, bakes one
frame range, checks cache state/output, verifies the Cycles volume material,
renders one frame, and removes all temporary data.
"""

from pathlib import Path
import shutil
import sys
import tempfile

import bpy
import bmesh


def _mesh(name, kind):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bm = bmesh.new()
    try:
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=2.0)
        else:
            bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.35)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _assert(condition, message):
    if not condition:
        raise RuntimeError(message)


def _validate_saved_render(path):
    """Validate pixels from the PNG written by background rendering."""
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        _assert(image.size[0] > 0 and image.size[1] > 0, "Saved render has no image dimensions")
        pixels = list(image.pixels)
        _assert(pixels, "Saved render contains no decoded pixels")
        rgb_values = pixels[0::4] + pixels[1::4] + pixels[2::4]
        max_rgb = max(rgb_values)
        non_background = sum(value > 0.01 for value in rgb_values)
        _assert(max_rgb > 0.01, "Saved render contains only background pixels")
        print(
            f"Saved PNG validation: {image.size[0]}x{image.size[1]}, "
            f"max_rgb={max_rgb:.6f}, non_background_channel_values={non_background}"
        )
    finally:
        bpy.data.images.remove(image)


def run():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.resolution_x = 64
    scene.render.resolution_y = 64
    scene.render.resolution_percentage = 100
    scene.frame_start = 1
    scene.frame_end = 2

    temp_dir = Path(tempfile.mkdtemp(prefix="blastfx_blender52_"))
    objects = []
    materials = []
    domain_obj = None
    try:
        domain_obj = _mesh("__BlastFX_SmokeTest_Domain", "cube")
        flow_obj = _mesh("__BlastFX_SmokeTest_Flow", "sphere")
        objects.extend((domain_obj, flow_obj))
        domain_obj.scale = (2.0, 2.0, 2.0)
        domain_obj.location.z = 2.0

        domain_mod = domain_obj.modifiers.new("BlastFX SmokeTest Domain", "FLUID")
        domain_mod.fluid_type = "DOMAIN"
        domain = domain_mod.domain_settings
        _assert(domain is not None, "DOMAIN settings were not initialized")
        domain.domain_type = "GAS"
        domain.resolution_max = 16
        domain.cache_type = "ALL"
        domain.cache_data_format = "OPENVDB"
        domain.cache_frame_start = 1
        domain.cache_frame_end = 2
        domain.cache_directory = str(temp_dir / "cache")
        domain.use_noise = False

        flow_mod = flow_obj.modifiers.new("BlastFX SmokeTest Flow", "FLUID")
        flow_mod.fluid_type = "FLOW"
        flow = flow_mod.flow_settings
        _assert(flow is not None, "FLOW settings were not initialized")
        flow.flow_type = "SMOKE"
        flow.flow_behavior = "INFLOW"
        flow.density = 1.0
        flow.temperature = 1.0
        flow.use_inflow = True
        flow.keyframe_insert("use_inflow", frame=1)
        flow.use_inflow = False
        flow.keyframe_insert("use_inflow", frame=2)

        material = bpy.data.materials.new("__BlastFX_SmokeTest_Volume")
        materials.append(material)
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        output = nodes.new("ShaderNodeOutputMaterial")
        volume = nodes.new("ShaderNodeVolumePrincipled")
        _assert(volume.inputs.get("Density Attribute") is not None, "Missing Density Attribute socket")
        _assert(volume.inputs.get("Temperature Attribute") is not None, "Missing Temperature Attribute socket")
        volume.inputs["Density Attribute"].default_value = "density"
        volume.inputs["Temperature Attribute"].default_value = "temperature"
        links.new(volume.outputs["Volume"], output.inputs["Volume"])
        domain_obj.data.materials.append(material)

        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        domain_obj.select_set(True)
        bpy.context.view_layer.objects.active = domain_obj
        result = bpy.ops.fluid.bake_all()
        _assert("FINISHED" in result, f"Mantaflow bake returned {set(result)}")

        cache_dir = Path(bpy.path.abspath(domain.cache_directory))
        _assert(
            getattr(domain, "has_cache_baked_data", False)
            or any(cache_dir.rglob("*.vdb"))
            or any(cache_dir.rglob("*.uni")),
            "Bake completed without data-baked state or cache output",
        )
        print(
            "Mantaflow grid-related runtime attributes:",
            [name for name in dir(domain) if "grid" in name.lower()],
        )

        camera_data = bpy.data.cameras.new("__BlastFX_SmokeTest_Camera")
        camera = bpy.data.objects.new("__BlastFX_SmokeTest_Camera", camera_data)
        scene.collection.objects.link(camera)
        objects.append(camera)
        camera.location = (6.0, -6.0, 5.0)
        camera.rotation_euler = (
            (domain_obj.location - camera.location).to_track_quat("-Z", "Y").to_euler()
        )
        scene.camera = camera
        scene.world.color = (0.0, 0.0, 0.0)
        scene.render.filepath = str(temp_dir / "smoke_test.png")
        bpy.ops.render.render(write_still=True)
        render_path = Path(scene.render.filepath)
        _assert(render_path.exists(), "Smoke-test render was not written")
        _validate_saved_render(render_path)
        print("BLAST FX BLENDER 5.2 SMOKE TEST: PASS")
    finally:
        if domain_obj and domain_obj.modifiers:
            try:
                bpy.context.view_layer.objects.active = domain_obj
                bpy.ops.fluid.free_all()
            except Exception as exc:
                print(f"WARNING: unable to free smoke-test cache: {exc}", file=sys.stderr)
        for obj in objects:
            if obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        for material in materials:
            if material.name in bpy.data.materials:
                bpy.data.materials.remove(material, do_unlink=True)
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run()
