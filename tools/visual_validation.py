"""Run the four-preset Blender 5.2 visual validation pass.

This script uses the registered add-on operators for creation and bake start.
Mantaflow remains owned by the background worker; the foreground script only
polls the existing job coordinator and renders completed cache frames.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import bpy
from mathutils import Vector

# Blender auto-enables a stale installed copy of blastfx at startup (Oct 1
# snapshot under Application Support). Disable it and purge its modules so the
# repo checkout below is the code under test.
import addon_utils  # noqa: E402

try:
    addon_utils.disable("blastfx", default_set=False)
except Exception as exc:  # noqa: BLE001
    print(f"note: addon_utils.disable raised {exc!r}; continuing after purge")
for key in [
    k for k in list(sys.modules) if k == "blastfx" or k.startswith("blastfx.")
]:
    del sys.modules[key]

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(__import__("os").environ.get(
    "BLASTFX_OUTPUT", "/tmp/blastfx_visual_validation"
)).expanduser().resolve()
PRESETS = ("small", "medium", "large", "large_ground")


def _clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.name != "Collection" and collection.users == 0:
            bpy.data.collections.remove(collection)


def _render_stats(path: Path) -> dict:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        rgb = list(image.pixels)
        pixels = [
            tuple(rgb[index : index + 3])
            for index in range(0, len(rgb), 4)
        ]
        width = image.size[0]
        height = image.size[1]
        border = (
            pixels[:width] + pixels[-width:]
            + [pixels[index * width] for index in range(height)]
            + [pixels[index * width + width - 1] for index in range(height)]
        ) if pixels else []
        background = tuple(statistics.median(pixel[channel] for pixel in border)
                           for channel in range(3)) if border else (0.0, 0.0, 0.0)
        channels = [value for pixel in pixels for value in pixel]
        foreground = [
            (index % width, index // width)
            for index, pixel in enumerate(pixels)
            if sum((value - base) ** 2 for value, base in zip(pixel, background))
            > 0.0025
        ]
        bounds = None
        if foreground:
            xs, ys = zip(*foreground)
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            bounds = {
                "width": max_x - min_x + 1,
                "height": max_y - min_y + 1,
                "center_x": (min_x + max_x) / 2 / width,
                "center_y": (min_y + max_y) / 2 / height,
                "width_height_ratio": (max_x - min_x + 1) / max(1, max_y - min_y + 1),
            }
        return {
            "max_rgb": max(channels) if channels else 0.0,
            "mean_rgb": sum(channels) / len(channels) if channels else 0.0,
            "background_rgb": background,
            "non_background": sum(
                sum((value - base) ** 2 for value, base in zip(pixel, background))
                > 0.0025
                for pixel in pixels
            ),
            "bounds": bounds,
        }
    finally:
        bpy.data.images.remove(image)


def _source_info(controller) -> list[dict]:
    from blastfx.utils.animation import action_fcurves
    collection = next(c for c in controller.users_collection if c.name.startswith("Blast_"))
    result = []
    for obj in collection.objects:
        if obj.get("blastfx_role") != "emitter":
            continue
        flow = next((m.flow_settings for m in obj.modifiers if m.type == "FLUID"), None)
        keyframes = []
        if obj.animation_data and obj.animation_data.action:
            for curve in action_fcurves(obj):
                if "use_inflow" in curve.data_path:
                    keyframes.extend(float(point.co.x) for point in curve.keyframe_points)
        result.append({
            "name": obj.name,
            "component": obj.get("blastfx_component"),
            "location": tuple(round(value, 5) for value in obj.location),
            "dimensions": tuple(round(value, 5) for value in obj.dimensions),
            "scale": tuple(round(value, 5) for value in obj.scale),
            "flow_type": getattr(flow, "flow_type", None),
            "flow_behavior": getattr(flow, "flow_behavior", None),
            "fuel": getattr(flow, "fuel_amount", None),
            "temperature": getattr(flow, "temperature", None),
            "velocity_normal": getattr(flow, "velocity_normal", None),
            "velocity_random": getattr(flow, "velocity_random", None),
            "emission_start": min(keyframes) if keyframes else None,
            "emission_end": max(keyframes) if keyframes else None,
        })
    return result


def _max_animated_scale(context, obj) -> tuple[float, float, float]:
    """Return the maximum absolute animated scale per axis for containment checks."""
    values = []
    original_frame = context.scene.frame_current
    for frame in range(context.scene.frame_start, context.scene.frame_end + 1):
        context.scene.frame_set(frame)
        evaluated = obj.evaluated_get(context.evaluated_depsgraph_get())
        values.append(tuple(float(value) for value in evaluated.scale))
    context.scene.frame_set(original_frame)
    return tuple(max(abs(value[index]) for value in values) for index in range(3))


def _containment_audit(controller) -> dict:
    """Check every generated source against the planned domain before baking."""
    collection = next(c for c in controller.users_collection if c.name.startswith("Blast_"))
    domain_obj = next(obj for obj in collection.objects if obj.get("blastfx_role") == "domain")
    domain_min = domain_obj.location - domain_obj.dimensions * 0.5
    domain_max = domain_obj.location + domain_obj.dimensions * 0.5
    margin = max(min(domain_obj.dimensions) * 0.01, 0.01)
    sources = []
    violations = []
    for obj in collection.objects:
        if obj.get("blastfx_role") != "emitter":
            continue
        max_scale = _max_animated_scale(bpy.context, obj)
        half_extent = obj.dimensions * 0.5
        current_scale = obj.scale
        half_extent = Vector((
            half_extent[index] * max_scale[index] / max(abs(current_scale[index]), 1e-6)
            for index in range(3)
        ))
        source_min = obj.location - half_extent
        source_max = obj.location + half_extent
        contained = all(
            source_min[index] >= domain_min[index] + margin
            and source_max[index] <= domain_max[index] - margin
            for index in range(3)
        )
        entry = {
            "component": obj.get("blastfx_component"),
            "location": tuple(round(value, 5) for value in obj.location),
            "max_animated_scale": tuple(round(value, 5) for value in max_scale),
            "bounds_min": tuple(round(value, 5) for value in source_min),
            "bounds_max": tuple(round(value, 5) for value in source_max),
            "contained": contained,
        }
        sources.append(entry)
        if not contained:
            violations.append(entry)
    if violations:
        raise RuntimeError(
            f"Generated source outside domain envelope: "
            f"domain_min={tuple(domain_min)}, domain_max={tuple(domain_max)}, "
            f"violations={violations}"
        )
    return {
        "domain_min": tuple(round(value, 5) for value in domain_min),
        "domain_max": tuple(round(value, 5) for value in domain_max),
        "margin": round(margin, 5),
        "sources": sources,
    }


def _wait_for_bake(controller, timeout=1800):
    from blastfx.core import bake_job

    started = time.monotonic()
    while bake_job.active_job() is not None:
        bake_job._poll()
        if time.monotonic() - started > timeout:
            raise RuntimeError("Timed out waiting for asynchronous bake worker.")
        time.sleep(0.5)
    status = bake_job.job_status(controller) or {}
    return status


def _frame_range(controller, props):
    from blastfx.core.cache import active_cache_path

    expected = json.loads(
        (active_cache_path(props, controller["blastfx_id"]) / ".blastfx_expected.json")
        .read_text(encoding="utf-8")
    )
    return int(expected["frame_start"]), int(expected["frame_end"])


def _render_scene_child(
    blend_path: Path, output_dir: Path, frames: list[int], cache_path: Path
) -> None:
    command = [
        bpy.app.binary_path,
        "--background",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--render-scene",
        str(blend_path),
        str(output_dir),
        json.dumps(frames),
        str(cache_path),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode:
        raise RuntimeError(f"Render validation process failed with code {result.returncode}")


def _render_scene_child_main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :]
    blend_path = Path(args[1])
    output_dir = Path(args[2])
    frames = json.loads(args[3])
    cache_path = Path(args[4])
    sys.path.insert(0, str(ROOT))
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    scene = bpy.context.scene
    bpy.context.preferences.filepaths.use_relative_paths = False
    if scene.camera and __import__("os").environ.get("BLASTFX_RENDER_LENS"):
        scene.camera.data.lens = float(__import__("os").environ["BLASTFX_RENDER_LENS"])
    if __import__("os").environ.get("BLASTFX_RENDER_EXPOSURE"):
        scene.view_settings.exposure = float(
            __import__("os").environ["BLASTFX_RENDER_EXPOSURE"]
        )
    domain_obj = next(
        obj for obj in bpy.data.objects if obj.get("blastfx_role") == "domain"
    )
    if __import__("os").environ.get("BLASTFX_RENDER_HIDE_DOMAIN") == "1":
        domain_obj.hide_render = True
    if __import__("os").environ.get("BLASTFX_RENDER_HIDE_SHOCKWAVE") == "1":
        for obj in bpy.data.objects:
            if obj.get("blastfx_id") == domain_obj.get("blastfx_id") and obj.get(
                "blastfx_role"
            ) in {"shockwave_geometry"}:
                obj.hide_render = True
    if __import__("os").environ.get("BLASTFX_RENDER_HIDE_NON_SUPPORT") == "1":
        for obj in bpy.data.objects:
            if obj.get("blastfx_id") != domain_obj.get("blastfx_id"):
                continue
            if obj.get("blastfx_role") not in {
                "controller", "camera_fx", "volumetric_light"
            }:
                obj.hide_render = True
    domain_settings = next(
        modifier.domain_settings
        for modifier in domain_obj.modifiers
        if modifier.type == "FLUID" and modifier.domain_settings is not None
    )
    resolved_cache = Path(bpy.path.abspath(domain_settings.cache_directory)).resolve()
    if resolved_cache != cache_path.resolve():
        raise RuntimeError(
            f"Fresh process cache path mismatch: {resolved_cache} != {cache_path.resolve()}"
        )
    if scene.camera and __import__("os").environ.get(
        "BLASTFX_RENDER_CAMERA_OUTSIDE_DOMAIN"
    ) == "1":
        controller_obj = next(
            obj for obj in bpy.data.objects
            if obj.get("blastfx_id") == domain_obj.get("blastfx_id")
            and obj.get("blastfx_controller", False)
        )
        if scene.camera.animation_data:
            scene.camera.animation_data_clear()
        half_x = float(domain_obj.dimensions.x) * 0.5 * 1.03
        half_y = float(domain_obj.dimensions.y) * 0.5 * 1.03
        characteristic_radius = float(
            controller_obj.get("blastfx_characteristic_radius_m", 0.5)
        )
        scene.camera.location = controller_obj.location + Vector((
            half_x, half_y, characteristic_radius * 8.0,
        ))
        target = controller_obj.location + Vector((
            0.0, 0.0, characteristic_radius * 2.0,
        ))
        scene.camera.rotation_euler = (
            target - scene.camera.location
        ).to_track_quat("-Z", "Y").to_euler()
    if scene.camera and __import__("os").environ.get(
        "BLASTFX_RENDER_LARGE_EVENT_CAMERA"
    ) == "1":
        controller_obj = next(
            obj for obj in bpy.data.objects
            if obj.get("blastfx_id") == domain_obj.get("blastfx_id")
            and obj.get("blastfx_controller", False)
        )
        if scene.camera.animation_data:
            scene.camera.animation_data_clear()
        radius = float(controller_obj.get("blastfx_characteristic_radius_m", 0.5))
        scene.camera.location = controller_obj.location + Vector(
            (radius * 6.0, -radius * 12.0, radius * 8.0)
        )
        target = controller_obj.location + Vector((0.0, 0.0, radius * 1.2))
        scene.camera.rotation_euler = (
            target - scene.camera.location
        ).to_track_quat("-Z", "Y").to_euler()
        scene.camera.data.lens = float(
            __import__("os").environ.get("BLASTFX_RENDER_LARGE_LENS", "36")
        )
    if __import__("os").environ.get("BLASTFX_RENDER_SMOKE_COLOR"):
        smoke_color = tuple(
            float(value) for value in __import__("os").environ[
                "BLASTFX_RENDER_SMOKE_COLOR"
            ].split(",")
        )
        if len(smoke_color) != 3:
            raise ValueError("BLASTFX_RENDER_SMOKE_COLOR expects three comma-separated values")
        for material in domain_obj.data.materials:
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type == "VOLUME_PRINCIPLED" and node.inputs.get("Color"):
                    node.inputs["Color"].default_value = (*smoke_color, 1.0)
    if __import__("os").environ.get("BLASTFX_RENDER_LARGE_FRONT_GAIN") == "1":
        for obj in bpy.data.objects:
            if obj.get("blastfx_role") != "shockwave_geometry":
                continue
            for material in obj.data.materials:
                if not material or not material.use_nodes:
                    continue
                for node in material.node_tree.nodes:
                    if node.type == "BSDF_PRINCIPLED":
                        strength = node.inputs.get("Emission Strength")
                        if strength is not None:
                            strength.default_value = 0.8
                    if node.type == "MAP_RANGE":
                        node.inputs["To Min"].default_value = 0.10
                        node.inputs["To Max"].default_value = 0.42
    if (
        not domain_settings.has_cache_baked_data
        and not __import__("os").environ.get("BLASTFX_LAYER")
        and __import__("os").environ.get("BLASTFX_RENDER_ALLOW_PARTIAL_CACHE") != "1"
    ):
        # Blender 5.2 can report the persisted bake flag as false after loading
        # a worker-produced Preview cache even when the VDB grids are readable.
        # Validate the evaluated grid itself before rejecting the reload.
        scene.frame_set(int(domain_settings.cache_frame_start))
        bpy.context.view_layer.update()
        evaluated_domain_obj = domain_obj.evaluated_get(
            bpy.context.evaluated_depsgraph_get()
        )
        evaluated_domain = next(
            modifier.domain_settings for modifier in evaluated_domain_obj.modifiers
            if modifier.type == "FLUID" and modifier.domain_settings is not None
        )
        try:
            density_grid = list(evaluated_domain.density_grid)
        except (TypeError, ValueError, RuntimeError) as error:
            raise RuntimeError(
                "Fresh process could not read the completed Mantaflow density grid."
            ) from error
        if not density_grid or max(density_grid, default=0.0) <= 0.0:
            raise RuntimeError(
                "Fresh process did not load a non-empty completed Mantaflow density grid."
            )
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    if __import__("os").environ.get("BLASTFX_LAYER") in {"cap", "stem_cap"}:
        material = bpy.data.materials.new("__BlastFX_CapDiagnostic")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        volume = nodes.new("ShaderNodeVolumePrincipled")
        info = nodes.new("ShaderNodeVolumeInfo")
        density = nodes.new("ShaderNodeMath")
        density.operation = "MULTIPLY"
        density.inputs[1].default_value = float(
            __import__("os").environ.get("BLASTFX_LAYER_DENSITY_SCALE", "0.03")
        )
        links.new(info.outputs["Density"], density.inputs[0])
        links.new(density.outputs[0], volume.inputs["Density"])
        volume.inputs["Blackbody Intensity"].default_value = 0.0
        volume.inputs["Emission Color"].default_value = (0.9, 0.9, 0.9, 1.0)
        links.new(density.outputs[0], volume.inputs["Emission Strength"])
        links.new(volume.outputs["Volume"], output.inputs["Volume"])
        domain_obj.data.materials.clear()
        domain_obj.data.materials.append(material)
    render_density_scale = __import__("os").environ.get(
        "BLASTFX_RENDER_DENSITY_SCALE"
    )
    if render_density_scale is not None and domain_obj.data.materials:
        material = domain_obj.data.materials[0]
        if material and material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type != "MATH" or node.operation != "MULTIPLY":
                    continue
                from_density_grid = any(
                    link.from_node.type == "VOLUME_INFO"
                    and link.from_socket.name == "Density"
                    for link in material.node_tree.links
                    if link.to_node == node and link.to_socket == node.inputs[0]
                )
                if from_density_grid:
                    node.inputs[1].default_value = float(render_density_scale)
                    break
    output_dir.mkdir(parents=True, exist_ok=True)
    grid_metrics = []
    for index, frame in enumerate(frames):
        scene.frame_set(int(domain_settings.cache_frame_start))
        bpy.context.view_layer.update()
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        if __import__("os").environ.get("BLASTFX_RENDER_LARGE_FRONT_GAIN") == "1":
            for obj in bpy.data.objects:
                if obj.get("blastfx_role") == "shockwave_geometry":
                    obj.scale.x *= 6.0 / 4.5
                    obj.scale.y *= 6.0 / 4.5
        scene.render.filepath = str(output_dir / f"{index:02d}_{frame:05d}.png")
        bpy.ops.render.render(write_still=True)
        evaluated = domain_obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        evaluated_domain = next(
            modifier.domain_settings for modifier in evaluated.modifiers
            if modifier.type == "FLUID" and modifier.domain_settings is not None
        )
        metrics = {}
        for name in ("density_grid", "temperature_grid", "flame_grid", "heat_grid"):
            grid = getattr(evaluated_domain, name, [])
            try:
                values = list(grid)
                metrics[name] = {
                    "length": len(values),
                    "max": max(values) if values else 0.0,
                    "mean": sum(values) / len(values) if values else 0.0,
                }
            except (TypeError, ValueError, RuntimeError):
                metrics[name] = {"length": 0, "max": 0.0, "mean": 0.0}
        grid_metrics.append({"frame": frame, "grids": metrics})
    (output_dir / "grid_metrics.json").write_text(
        json.dumps(grid_metrics, indent=2, default=str), encoding="utf-8"
    )


def run_one(preset_id: str) -> dict:
    from blastfx.presets.apply import apply_preset
    from blastfx.core.explosion_profile import PROFILES

    _clean_scene()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 4
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.002, 0.002, 0.002)
    scene.frame_start = 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    layer_mode = __import__("os").environ.get("BLASTFX_LAYER", "").lower()
    case_name = __import__("os").environ.get("BLASTFX_CASE", "").lower()
    profile_key = {
        "small": "GROUND", "medium": "FUEL", "large": "LARGE",
        "large_ground": "LARGE",
    }[preset_id]
    profile = PROFILES[profile_key]
    overrides_text = __import__("os").environ.get("BLASTFX_PROFILE_OVERRIDES", "")
    overrides = json.loads(overrides_text) if overrides_text else {}
    if not isinstance(overrides, dict):
        raise ValueError("BLASTFX_PROFILE_OVERRIDES must be a JSON object")
    unknown = set(overrides) - set(profile.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Unknown profile override(s): {sorted(unknown)}")
    if overrides:
        PROFILES[profile_key] = replace(profile, **overrides)
    output_name = (
        f"{preset_id}_{case_name}_{layer_mode}" if case_name and layer_mode
        else f"{preset_id}_{case_name}" if case_name
        else f"{preset_id}_{layer_mode}" if layer_mode else preset_id
    )
    (OUTPUT / output_name).mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(
        filepath=str(OUTPUT / output_name / f"{output_name}.base.blend")
    )
    props = scene.blastfx
    if preset_id == "medium" and case_name and not overrides:
        rate = float(__import__("os").environ["BLASTFX_BURNING_RATE"])
        duration = float(__import__("os").environ["BLASTFX_SOURCE_DURATION"])
        PROFILES["FUEL"] = replace(PROFILES["FUEL"], burning_rate=rate,
                                    source_duration=duration)
    apply_preset(props, preset_id)
    if layer_mode in {"fireball", "ground_surge", "shockwave", "smoke"}:
        props.use_fireball = layer_mode == "fireball"
        props.use_dust = layer_mode == "ground_surge"
        props.use_shockwave = layer_mode == "shockwave"
        props.use_stem = layer_mode == "smoke"
        props.use_debris = False
    props.quality = __import__("os").environ.get("BLASTFX_QUALITY", "DRAFT").upper()
    props.resolution = int(__import__("os").environ.get("BLASTFX_RESOLUTION", "64"))
    props.use_camera_fx = True
    props.use_exposure = False
    props.use_heat_distortion = False

    if "FINISHED" not in bpy.ops.blastfx.create():
        raise RuntimeError(f"Create failed for {preset_id}")
    controller = bpy.context.active_object
    frame_limit = int(__import__("os").environ.get("BLASTFX_FRAME_LIMIT", "0"))
    if frame_limit > 0:
        collection = next(
            c for c in controller.users_collection if c.name.startswith("Blast_")
        )
        domain_obj = next(
            obj for obj in collection.objects if obj.get("blastfx_role") == "domain"
        )
        domain_settings = next(
            modifier.domain_settings for modifier in domain_obj.modifiers
            if modifier.type == "FLUID" and modifier.domain_settings is not None
        )
        if frame_limit < int(domain_settings.cache_frame_start):
            raise ValueError("BLASTFX_FRAME_LIMIT is before the cache start frame")
        domain_settings.cache_frame_end = min(
            frame_limit, int(domain_settings.cache_frame_end)
        )
        scene.frame_end = domain_settings.cache_frame_end
        from blastfx.core.cache import active_cache_path
        expected_path = active_cache_path(props, controller["blastfx_id"])
        expected_file = expected_path / ".blastfx_expected.json"
        expected = json.loads(expected_file.read_text(encoding="utf-8"))
        expected["frame_end"] = int(domain_settings.cache_frame_end)
        expected_file.write_text(json.dumps(expected, sort_keys=True), encoding="utf-8")
    containment = _containment_audit(controller)
    if "FINISHED" not in bpy.ops.blastfx.bake():
        raise RuntimeError(f"Bake start failed for {preset_id}")
    status = _wait_for_bake(controller)
    from blastfx.core.cache import active_cache_path
    render_cache_path = active_cache_path(props, controller["blastfx_id"])
    if status.get("state") != "COMPLETED" and not (
        layer_mode and status.get("state") == "PARTIAL"
        and any(render_cache_path.rglob("*.vdb"))
    ):
        log_path = Path(controller.get("blastfx_bake_log_path", ""))
        if log_path.exists():
            (OUTPUT / preset_id).mkdir(parents=True, exist_ok=True)
            (OUTPUT / preset_id / "worker.log").write_text(
                log_path.read_text(encoding="utf-8", errors="replace"),
                encoding="utf-8",
            )
        raise RuntimeError(f"Bake did not complete: {status}")
    frame_start, frame_end = _frame_range(controller, props)
    log_path = Path(controller.get("blastfx_bake_log_path", ""))
    if log_path.exists():
        (OUTPUT / preset_id).mkdir(parents=True, exist_ok=True)
        (OUTPUT / preset_id / "worker.log").write_text(
            log_path.read_text(encoding="utf-8", errors="replace"),
            encoding="utf-8",
        )
    collection = next(c for c in controller.users_collection if c.name.startswith("Blast_"))
    domain_obj = next(obj for obj in collection.objects if obj.get("blastfx_role") == "domain")
    domain = next(mod.domain_settings for mod in domain_obj.modifiers if mod.type == "FLUID")
    # The worker has written shared cache files, but the foreground Blender
    # instance must reassert the cache path before loading them for rendering.
    requested_frames = __import__("os").environ.get("BLASTFX_REVIEW_FRAMES")
    if requested_frames:
        frames = [int(frame) for frame in json.loads(requested_frames)]
        if any(frame < frame_start or frame > frame_end for frame in frames):
            raise ValueError("BLASTFX_REVIEW_FRAMES falls outside the cached frame range")
        fractions = tuple(
            (frame - frame_start) / max(1, frame_end - frame_start) for frame in frames
        )
    else:
        fractions = (0.15, 0.30, 0.45, 0.60, 0.75, 0.90)
        frames = [
            round(frame_start + (frame_end - frame_start) * fraction)
            for fraction in fractions
        ]
    output_dir = OUTPUT / output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    request_path = Path(controller["blastfx_bake_status_path"]).parent / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    scene_path = Path(request["scene_path"])
    print(
        "CACHE OUTPUT",
        render_cache_path,
        render_cache_path.exists(),
        sum(1 for path in render_cache_path.rglob("*.vdb")),
        sum(1 for path in render_cache_path.rglob("*.uni")),
        [str(path.relative_to(render_cache_path)) for path in render_cache_path.rglob("*") if path.is_file()][-5:],
        flush=True,
    )
    if not any(render_cache_path.rglob("*.vdb")) and not any(
        render_cache_path.rglob("*.uni")
    ):
        raise RuntimeError(
            f"Worker completed without usable Mantaflow grids in {render_cache_path}"
        )
    _render_scene_child(
        scene_path,
        output_dir,
        frames,
        render_cache_path,
    )
    renders = [
        {
            "frame": frame,
            "path": str(output_dir / f"{index:02d}_{frame:05d}.png"),
            "stats": _render_stats(output_dir / f"{index:02d}_{frame:05d}.png"),
        }
        for index, frame in enumerate(frames)
    ]

    from blastfx.core.explosion_profile import profile_for, profile_state

    profile = profile_state(profile_for(props.explosion_type))
    solver_settings = {
        "alpha_density_buoyancy": float(domain.alpha),
        "beta_heat_buoyancy": float(domain.beta),
        "global_vorticity": float(domain.vorticity),
        "burning_rate": float(domain.burning_rate),
        "flame_vorticity": float(domain.flame_vorticity),
        "flame_smoke": float(domain.flame_smoke),
        "resolution_max": int(domain.resolution_max),
        "interpretation": "Mantaflow controls / empirical VFX calibration values; not SI explosion measurements",
    }
    raw_envelope = dict(controller.get("blastfx_domain_envelope", {}))
    envelope = {
        key: list(value) if hasattr(value, "__iter__") and not isinstance(value, str)
        else value
        for key, value in raw_envelope.items()
    }
    return {
        "preset": preset_id,
        "layer_mode": layer_mode or "all",
        "status": status,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "sampled_frames": renders,
        "profile": profile,
        "solver_settings": solver_settings,
        "profile_overrides": overrides,
        "domain_envelope": envelope,
        "camera": scene.camera.name if scene.camera else None,
        "camera_location": tuple(scene.camera.location) if scene.camera else None,
        "sources": _source_info(controller),
        "containment": containment,
    }


def main():
    sys.path.insert(0, str(ROOT))
    import blastfx

    blastfx.register()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        preset_filter = __import__("os").environ.get("BLASTFX_PRESET")
        layers = __import__("os").environ.get("BLASTFX_LAYERS")
        if layers:
            preset_filter = preset_filter or "large"
            layer_values = [value.strip() for value in layers.split(",") if value.strip()]
        else:
            layer_values = [__import__("os").environ.get("BLASTFX_LAYER", "")]
        for preset_id in ((preset_filter,) if preset_filter else PRESETS):
            for layer in layer_values:
                if layer:
                    __import__("os").environ["BLASTFX_LAYER"] = layer
                else:
                    __import__("os").environ.pop("BLASTFX_LAYER", None)
                print(f"VISUAL VALIDATION: {preset_id} layer={layer or 'all'}", flush=True)
                results.append(run_one(preset_id))
    finally:
        blastfx.unregister()
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"VISUAL VALIDATION RESULTS: {OUTPUT / 'results.json'}", flush=True)


if "--render-scene" in sys.argv:
    _render_scene_child_main()
elif __name__ == "__main__":
    main()
