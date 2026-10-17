"""Diagnose and render one already-baked Mantaflow gas snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _domain():
    obj = next(obj for obj in bpy.data.objects if obj.get("blastfx_role") == "domain")
    settings = next(
        modifier.domain_settings
        for modifier in obj.modifiers
        if modifier.type == "FLUID" and modifier.domain_settings is not None
    )
    return obj, settings


def _socket_names(node):
    return [socket.name for socket in node.inputs]


def _material_info(material):
    if material is None or not material.use_nodes:
        return {"name": None, "nodes": [], "links": []}
    return {
        "name": material.name,
        "nodes": [
            {
                "name": node.name,
                "type": node.bl_idname,
                "inputs": _socket_names(node),
                "values": {
                    socket.name: getattr(socket, "default_value", None)
                    for socket in node.inputs
                    if not socket.is_linked
                    and hasattr(socket, "default_value")
                },
            }
            for node in material.node_tree.nodes
        ],
        "links": [
            {
                "from": f"{link.from_node.name}:{link.from_socket.name}",
                "to": f"{link.to_node.name}:{link.to_socket.name}",
            }
            for link in material.node_tree.links
        ],
    }


def _grid_info(settings):
    result = {}
    for name in (
        "density_grid",
        "temperature_grid",
        "flame_grid",
        "heat_grid",
        "velocity_grid",
    ):
        grid = getattr(settings, name, None)
        try:
            result[name] = {
                "length": len(grid),
                "min": min(grid) if len(grid) else None,
                "max": max(grid) if len(grid) else None,
                "average": (sum(grid) / len(grid)) if len(grid) else None,
            }
        except (TypeError, ValueError, RuntimeError):
            result[name] = {"available": bool(grid), "repr": repr(grid)}
    return result


def _evaluated_grid_info(domain, depsgraph):
    evaluated = domain.evaluated_get(depsgraph)
    modifier = next(
        modifier
        for modifier in evaluated.modifiers
        if modifier.type == "FLUID" and modifier.domain_settings is not None
    )
    return _grid_info(modifier.domain_settings)


def _look_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def main():
    args = sys.argv[sys.argv.index("--") + 1 :]
    blend_path = Path(args[0]).resolve()
    output_path = Path(args[1]).resolve()
    frame = int(args[2])
    bpy.ops.wm.open_mainfile(filepath=str(blend_path), load_ui=False)
    scene = bpy.context.scene
    bpy.context.preferences.filepaths.use_relative_paths = False
    domain, settings = _domain()
    records = []
    start = int(settings.cache_frame_start)
    target = max(start, frame)
    for current in (start, target):
        scene.frame_set(current)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        depsgraph.update()
        records.append(
            {
                "frame": current,
                "has_cache_baked_data": bool(settings.has_cache_baked_data),
                "dimensions": tuple(domain.dimensions),
                "hide_render": domain.hide_render,
                "hide_viewport": domain.hide_viewport,
                "visible_camera": domain.visible_camera,
                "material": _material_info(domain.active_material),
                "display": {
                    "display_thickness": getattr(settings, "display_thickness", None),
                    "slice_method": getattr(settings, "slice_method", None),
                    "clip": getattr(settings, "clip", None),
                },
                "grids": _grid_info(settings),
                "evaluated_grids": _evaluated_grid_info(domain, depsgraph),
            }
        )

    center = domain.matrix_world.translation.copy()
    camera_data = bpy.data.cameras.new("__BlastFX_DiagnosticCamera")
    camera = bpy.data.objects.new("__BlastFX_DiagnosticCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((domain.dimensions.length * 1.5,) * 3)
    _look_at(camera, center)
    camera.data.lens = 50
    camera.data.clip_start = 0.01
    camera.data.clip_end = max(1000.0, domain.dimensions.length * 10)
    scene.camera = camera
    production_material = domain.active_material
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    production_path = output_path.with_name(output_path.stem + "_production.png")
    scene.render.filepath = str(production_path)
    scene.frame_set(target)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)

    material = bpy.data.materials.new("__BlastFX_DiagnosticVolume")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    volume = nodes.new("ShaderNodeVolumePrincipled")
    volume_info = nodes.new("ShaderNodeVolumeInfo")
    links.new(volume_info.outputs["Density"], volume.inputs["Density"])
    temperature_scale = nodes.new("ShaderNodeMath")
    temperature_scale.operation = "MULTIPLY"
    temperature_scale.inputs[1].default_value = 1000.0
    links.new(volume_info.outputs["Temperature"], temperature_scale.inputs[0])
    links.new(temperature_scale.outputs[0], volume.inputs["Temperature"])
    volume.inputs["Density Attribute"].default_value = ""
    volume.inputs["Temperature Attribute"].default_value = ""
    volume.inputs["Blackbody Intensity"].default_value = 1.0
    volume.inputs["Emission Strength"].default_value = 0.0
    links.new(volume.outputs["Volume"], output.inputs["Volume"])
    domain.data.materials.clear()
    domain.data.materials.append(material)

    scene.render.filepath = str(output_path)
    scene.frame_set(target)
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)

    print(
        json.dumps(
            {
                "blend": str(blend_path),
                "cache_directory": bpy.path.abspath(settings.cache_directory),
                "cache_type": settings.cache_type,
                "cache_data_format": settings.cache_data_format,
                "domain": domain.name,
                "domain_material": _material_info(domain.active_material),
                "camera": {
                    "location": tuple(camera.location),
                    "forward": tuple(
                        camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
                    ),
                    "center": tuple(center),
                    "distance": (camera.location - center).length,
                },
                "frames": records,
                "render": str(output_path),
                "production_render": str(production_path),
                "production_material": _material_info(production_material),
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
