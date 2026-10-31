from pathlib import Path
import json
import shutil
import uuid
import bpy

from .cache_layout import (
    COMPLETE_MARKER,
    EXPECTED_MARKER,
    GENERATION_MARKER,
    _generation_dir_from_root,
    inspect_mantaflow_cache_tree,
    recover_generation,
)


def project_cache_root(props) -> Path:
    subdir = Path(props.cache_subdir)
    if subdir.is_absolute() or ".." in subdir.parts:
        raise ValueError("Cache folder must be a relative path without parent traversal.")
    if bpy.data.filepath:
        project_dir = Path(bpy.data.filepath).parent
        return project_dir / subdir
    return Path(bpy.app.tempdir) / subdir


def cache_path(props, blast_id: str) -> Path:
    path = project_cache_root(props) / blast_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _blast_cache_root(props, blast_id: str) -> Path:
    return project_cache_root(props) / blast_id


def _marker_path(cache_root: Path, marker: str) -> Path:
    return cache_root / marker


def prepare_cache(
    props,
    blast_id: str,
    *,
    state_hash: str,
    frame_start: int,
    frame_end: int,
) -> Path:
    """Create an isolated cache contract before a bake starts."""
    if not blast_id or not state_hash:
        raise ValueError("Blast cache requires a controller ID and physics state hash.")
    root = _blast_cache_root(props, blast_id)
    if root.exists():
        shutil.rmtree(root)
    generation = uuid.uuid4().hex
    path = root / generation
    path.mkdir(parents=True, exist_ok=False)
    expected = {
        "blast_id": blast_id,
        "generation": generation,
        "state_hash": state_hash,
        "frame_start": int(frame_start),
        "frame_end": int(frame_end),
    }
    _marker_path(path, EXPECTED_MARKER).write_text(
        json.dumps(expected, sort_keys=True), encoding="utf-8"
    )
    (root / GENERATION_MARKER).write_text(generation, encoding="utf-8")
    return path


def _active_generation(props, blast_id: str) -> Path:
    return _generation_dir_from_root(_blast_cache_root(props, blast_id))


def active_cache_path(props, blast_id: str) -> Path:
    """Return the current isolated generation directory for a blast."""
    return _active_generation(props, blast_id)


def mark_baked(props, blast_id: str, *, state_hash: str) -> None:
    """Mark a bake complete only after Mantaflow produced cache output."""
    path = _active_generation(props, blast_id)
    expected_path = _marker_path(path, EXPECTED_MARKER)
    if not expected_path.exists():
        raise RuntimeError("Blast cache has no expected-state manifest.")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if expected.get("state_hash") != state_hash:
        raise RuntimeError("Blast cache state does not match the current physics state.")
    _marker_path(path, COMPLETE_MARKER).write_text(
        json.dumps({"state_hash": state_hash}, sort_keys=True), encoding="utf-8"
    )


def validate_cache_output(
    props,
    blast_id: str,
    *,
    state_hash: str,
    frame_start: int,
    frame_end: int,
    cache_data_format: str = "OPENVDB",
) -> bool:
    """Validate worker output without relying on the worker's Blender state."""
    try:
        path = _active_generation(props, blast_id)
        expected = json.loads(
            _marker_path(path, EXPECTED_MARKER).read_text(encoding="utf-8")
        )
    except (OSError, ValueError, RuntimeError):
        return False
    if (
        expected.get("state_hash") != state_hash
        or int(expected.get("frame_start", -1)) != int(frame_start)
        or int(expected.get("frame_end", -1)) != int(frame_end)
    ):
        return False
    inspection = inspect_mantaflow_cache_tree(path, cache_data_format)
    return bool(
        inspection["volumetric_count"]
        and (
            inspection["first_frame"] is None
            or (
                inspection["first_frame"] <= frame_start
                and inspection["last_frame"] >= frame_end
            )
        )
    )


def clear_baked_marker(props, blast_id: str) -> None:
    path = _active_generation(props, blast_id)
    _marker_path(path, COMPLETE_MARKER).unlink(missing_ok=True)


def invalidate(props, blast_id: str):
    cache_dir = project_cache_root(props) / blast_id
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    return blast_id


def status(props, blast_id: str, domain=None, state_hash: str | None = None) -> str:
    """Return cache state only for the current expected and completed cache."""
    if domain is not None:
        if (
            getattr(domain, "is_cache_baking_data", False)
            or getattr(domain, "is_cache_baking_noise", False)
        ):
            return "BAKING"

    root = _blast_cache_root(props, blast_id)
    if not root.exists():
        return "NOT_BAKED"
    try:
        cache_dir = _active_generation(props, blast_id)
    except (OSError, RuntimeError):
        return "INVALID"
    expected = cache_dir / EXPECTED_MARKER
    complete = cache_dir / COMPLETE_MARKER
    if complete.exists() and expected.exists():
        try:
            expected_data = json.loads(expected.read_text(encoding="utf-8"))
            complete_data = json.loads(complete.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "INVALID"
        if state_hash and (
            expected_data.get("state_hash") != state_hash
            or complete_data.get("state_hash") != state_hash
        ):
            return "STALE"
        cache_format = getattr(domain, "cache_data_format", "OPENVDB")
        try:
            inspection = inspect_mantaflow_cache_tree(cache_dir, cache_format)
        except ValueError:
            return "INVALID"
        has_files = bool(inspection["volumetric_count"])
        has_runtime_cache = bool(
            domain
            and (
                getattr(domain, "has_cache_baked_data", False)
                or getattr(domain, "has_cache_baked_noise", False)
            )
        )
        if has_files or has_runtime_cache:
            return "BAKED"
        complete.unlink(missing_ok=True)
    if expected.exists():
        cache_format = getattr(domain, "cache_data_format", "OPENVDB")
        try:
            has_partial_files = bool(
                inspect_mantaflow_cache_tree(cache_dir, cache_format)[
                    "volumetric_count"
                ]
            )
        except ValueError:
            return "INVALID"
        return "PARTIAL" if has_partial_files else "READY_TO_BAKE"
    return "NOT_BAKED"


def recover_caches(context) -> list:
    """Recover every blast cache in the scene (call at file-load time).

    Runs inside a load_post handler: per-blast failures are logged, never
    raised, so recovery can't abort opening the user's file.
    """
    from ..utils.logging import warning

    props = context.scene.blastfx
    notes = []
    for obj in bpy.data.objects:
        if not obj.get("blastfx_controller"):
            continue
        blast_id = obj.get("blastfx_id", "")
        if not blast_id:
            continue
        try:
            note = recover_generation(project_cache_root(props) / blast_id)
        except Exception as exc:
            warning(f"{blast_id}: cache recovery failed: {exc}")
            continue
        if note:
            warning(f"{blast_id}: {note}")
            notes.append(f"{blast_id}: {note}")
    return notes
