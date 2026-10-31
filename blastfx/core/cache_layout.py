"""Bpy-free cache layout primitives: markers, inspection, recovery.

Kept importable outside Blender so pytest can exercise recovery directly;
core.cache re-exports these as its public face.
"""

from pathlib import Path
import json
import os
import re
import shutil


EXPECTED_MARKER = ".blastfx_expected.json"
COMPLETE_MARKER = ".blastfx_complete"
GENERATION_MARKER = ".blastfx_generation"
_FRAME_RE = re.compile(r"(?<!\d)(\d{1,8})(?!\d)")


def inspect_mantaflow_cache_tree(root: Path, cache_data_format: str) -> dict:
    """Recursively inspect Mantaflow output and classify configured grid files."""
    root = Path(root).resolve()
    extension = {
        "OPENVDB": ".vdb",
        "UNI": ".uni",
        "RAW": ".raw",
    }.get(str(cache_data_format).upper())
    if extension is None:
        raise ValueError(f"Unsupported Mantaflow cache format: {cache_data_format!r}")
    directories = []
    files = []
    volumetric = []
    for path in sorted(root.rglob("*")) if root.exists() else ():
        if path.is_dir():
            directories.append(str(path.relative_to(root)))
            continue
        size = path.stat().st_size
        item = {
            "path": str(path.relative_to(root)),
            "extension": path.suffix.lower(),
            "size": size,
        }
        files.append(item)
        if path.suffix.lower() == extension and size > 0:
            try:
                with path.open("rb") as handle:
                    handle.read(16)
            except OSError:
                continue
            frames = [
                int(match.group(1))
                for match in _FRAME_RE.finditer(path.stem)
            ]
            volumetric.append({**item, "frames": frames})
    frame_values = [frame for item in volumetric for frame in item["frames"]]
    return {
        "root": str(root),
        "realpath": os.path.realpath(root),
        "directories": directories,
        "files": files,
        "volumetric": volumetric,
        "volumetric_count": len(volumetric),
        "total_bytes": sum(item["size"] for item in volumetric),
        "first_frame": min(frame_values) if frame_values else None,
        "last_frame": max(frame_values) if frame_values else None,
        "cache_data_format": str(cache_data_format).upper(),
    }


def _generation_dir_from_root(cache_root: Path) -> Path:
    """Resolve the active generation directory from a blast cache root."""
    marker = Path(cache_root) / GENERATION_MARKER
    if not marker.exists():
        raise RuntimeError("Blast cache has no active generation.")
    generation = marker.read_text(encoding="utf-8").strip()
    if not generation or Path(generation).name != generation:
        raise RuntimeError("Blast cache generation marker is invalid.")
    path = Path(cache_root) / generation
    if not path.is_dir():
        raise RuntimeError("Blast cache generation directory is missing.")
    return path


def recover_generation(cache_root: Path, cache_data_format: str = "OPENVDB") -> str | None:
    """Filesystem-only recovery for one blast cache root.

    Call at file-load time, when no in-process bake can exist: drops stale
    bake-job snapshot directories and heals a baked marker whose cache files
    disappeared. A broken generation contract is invalidated so a later bake
    starts from a clean slate; valid cache data is never deleted. Returns a
    human-readable action note, or None when nothing needed recovery.
    """
    cache_root = Path(cache_root)
    if not cache_root.exists():
        return None
    try:
        generation = _generation_dir_from_root(cache_root)
    except (OSError, RuntimeError):
        shutil.rmtree(cache_root, ignore_errors=True)
        return "invalidated: broken generation contract"

    cleaned = 0
    job_root = generation / "job"
    if job_root.is_dir():
        for job_dir in list(job_root.iterdir()):
            shutil.rmtree(job_dir, ignore_errors=True)
            cleaned += 1

    expected_path = generation / EXPECTED_MARKER
    complete_path = generation / COMPLETE_MARKER
    healed = False
    if complete_path.exists():
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            complete = json.loads(complete_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            shutil.rmtree(cache_root, ignore_errors=True)
            return "invalidated: unreadable cache markers"
        if expected.get("state_hash") != complete.get("state_hash"):
            shutil.rmtree(cache_root, ignore_errors=True)
            return "invalidated: inconsistent cache markers"
        inspection = inspect_mantaflow_cache_tree(generation, cache_data_format)
        if not inspection["volumetric_count"]:
            # Mirror status() self-healing: this baked marker is a lie now.
            complete_path.unlink(missing_ok=True)
            healed = True

    actions = []
    if cleaned:
        actions.append(f"removed {cleaned} stale job dir(s)")
    if healed:
        actions.append("cleared baked marker without cache files")
    return "; ".join(actions) if actions else None
