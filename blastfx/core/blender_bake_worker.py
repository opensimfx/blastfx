"""Blender background process for one Blast FX Mantaflow bake."""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from pathlib import Path

import bpy

_FRAME_RE = re.compile(r"(?<!\d)(\d{1,8})(?!\d)")


def _inspect_cache_tree(root: Path, cache_data_format: str) -> dict:
    extension = {"OPENVDB": ".vdb", "UNI": ".uni", "RAW": ".raw"}.get(
        str(cache_data_format).upper()
    )
    if extension is None:
        raise ValueError(f"Unsupported Mantaflow cache format: {cache_data_format!r}")
    directories = []
    files = []
    volumetric = []
    root = root.resolve()
    for path in sorted(root.rglob("*")) if root.exists() else ():
        if path.is_dir():
            directories.append(str(path.relative_to(root)))
            continue
        item = {
            "path": str(path.relative_to(root)),
            "extension": path.suffix.lower(),
            "size": path.stat().st_size,
        }
        files.append(item)
        if item["extension"] == extension and item["size"] > 0:
            with path.open("rb") as handle:
                handle.read(16)
            frames = [int(match.group(1)) for match in _FRAME_RE.finditer(path.stem)]
            volumetric.append({**item, "frames": frames})
    frame_values = [frame for item in volumetric for frame in item["frames"]]
    return {
        "directories": directories,
        "files": files,
        "volumetric": volumetric,
        "volumetric_count": len(volumetric),
        "total_bytes": sum(item["size"] for item in volumetric),
        "first_frame": min(frame_values) if frame_values else None,
        "last_frame": max(frame_values) if frame_values else None,
    }


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _write_status(request: dict, state: str, started: float, message: str = "") -> None:
    _atomic_json(
        Path(request["status_path"]),
        {
            "job_id": request["job_id"],
            "blast_id": request["blast_id"],
            "generation": request["generation"],
            "state": state,
            "elapsed_seconds": max(0.0, time.monotonic() - started),
            "pid": os.getpid(),
            "frame_start": request["frame_start"],
            "frame_end": request["frame_end"],
            "message": message,
        },
    )


def main() -> int:
    request_path = os.environ.get("BLASTFX_BAKE_REQUEST")
    if not request_path:
        raise RuntimeError("BLASTFX_BAKE_REQUEST is not set.")
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    started = time.monotonic()
    print(
        "Blast FX bake worker: "
        f"job_id={request['job_id']} blast_id={request['blast_id']} "
        f"generation={request['generation']} "
        f"frames={request['frame_start']}-{request['frame_end']} "
        f"quality={request['quality']} noise={request['noise']}",
        flush=True,
    )
    _write_status(request, "PREPARING", started, f"Blender {bpy.app.version_string}")
    bpy.ops.wm.open_mainfile(filepath=request["scene_path"], load_ui=False)
    if Path(request["cancel_path"]).exists():
        _write_status(request, "CANCELLED", started, "Cancellation requested before bake.")
        return 2

    domain = next(
        (
            obj for obj in bpy.data.objects
            if obj.get("blastfx_role") == "domain"
            and obj.get("blastfx_id") == request["blast_id"]
        ),
        None,
    )
    if domain is None:
        raise RuntimeError("Worker could not find the requested Blast FX domain.")
    # Blender may rewrite relative cache paths when the temporary snapshot is
    # opened from the worker. The request path is the authoritative shared
    # generation and must be restored before Mantaflow starts.
    domain_settings = next(
        modifier.domain_settings
        for modifier in domain.modifiers
        if modifier.type == "FLUID" and modifier.domain_settings is not None
    )
    bpy.context.preferences.filepaths.use_relative_paths = False
    authoritative = Path(request["cache_path"]).resolve()
    configured = Path(bpy.path.abspath(domain_settings.cache_directory)).resolve()
    print(
        "Blast FX worker cache contract:",
        f"expected={authoritative}",
        f"configured_before={configured}",
        f"blend={bpy.data.filepath}",
        f"cwd={os.getcwd()}",
        flush=True,
    )
    if configured != authoritative:
        domain_settings.cache_directory = str(authoritative)
    domain_settings.cache_directory = str(authoritative)
    resolved = Path(
        os.path.realpath(bpy.path.abspath(domain_settings.cache_directory))
    )
    if resolved != Path(os.path.realpath(authoritative)):
        raise RuntimeError(f"Worker cache path mismatch: {resolved} != {authoritative}")
    if domain_settings.cache_type != "ALL":
        raise RuntimeError(f"Worker requires cache_type='ALL', got {domain_settings.cache_type!r}")
    if str(domain_settings.cache_data_format) != request["cache_data_format"]:
        raise RuntimeError(
            "Worker cache format mismatch: "
            f"{domain_settings.cache_data_format!r} != {request['cache_data_format']!r}"
        )
    authoritative.mkdir(parents=True, exist_ok=True)
    probe = authoritative / ".blastfx_worker_probe"
    probe.write_bytes(b"blastfx")
    if probe.read_bytes() != b"blastfx":
        raise OSError(f"Worker cache directory probe failed: {authoritative}")
    probe.unlink()
    print(
        "Blast FX worker cache resolved:",
        f"cache={authoritative}",
        f"realpath={resolved}",
        f"format={domain_settings.cache_data_format}",
        f"type={domain_settings.cache_type}",
        f"frames={domain_settings.cache_frame_start}-{domain_settings.cache_frame_end}",
        f"resolution={domain_settings.resolution_max}",
        flush=True,
    )
    bpy.ops.object.select_all(action="DESELECT")
    domain.select_set(True)
    bpy.context.view_layer.objects.active = domain
    _write_status(request, "BAKING_DATA", started, "Baking simulation data.")
    result = bpy.ops.fluid.bake_all()
    if "CANCELLED" in result:
        _write_status(request, "CANCELLED", started, "Mantaflow cancelled the bake.")
        return 2
    if "FINISHED" not in result:
        raise RuntimeError(f"Mantaflow bake returned {set(result)}")
    _write_status(request, "BAKE_OPERATOR_RETURNED", started, "Bake operator returned.")
    _write_status(request, "VERIFYING_CACHE", started, "Verifying cache output.")
    inspection = _inspect_cache_tree(authoritative, domain_settings.cache_data_format)
    print(
        "Blast FX worker cache inspection:",
        f"directories={len(inspection['directories'])}",
        f"files={len(inspection['files'])}",
        f"volumetric={inspection['volumetric_count']}",
        f"bytes={inspection['total_bytes']}",
        f"frames={inspection['first_frame']}-{inspection['last_frame']}",
        flush=True,
    )
    if not inspection["volumetric_count"]:
        raise RuntimeError(
            "Mantaflow returned FINISHED but wrote no usable volumetric cache files."
        )
    if Path(request["cancel_path"]).exists():
        _write_status(request, "CANCELLED", started, "Cancellation requested after bake.")
        return 2
    completed_scene = Path(request["scene_path"]).with_name("completed_scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(completed_scene), copy=True)
    request["scene_path"] = str(completed_scene)
    request_path = Path(os.environ["BLASTFX_BAKE_REQUEST"])
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    _write_status(request, "VERIFIED", started, "Worker cache files verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        request_path = os.environ.get("BLASTFX_BAKE_REQUEST")
        if request_path:
            try:
                request = json.loads(Path(request_path).read_text(encoding="utf-8"))
                _write_status(
                    request,
                    "FAILED",
                    time.monotonic(),
                    f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
                )
            except Exception:
                traceback.print_exc()
        traceback.print_exc()
        raise
