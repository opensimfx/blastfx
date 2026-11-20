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
# Folder names BlastFX creates: controller.new_blast_id() and uuid4().hex. A .blend is untrusted input, so an ID
# read from it is only used for a path when it matches these exactly (no "..", separators or absolute paths).
_BLAST_ID_RE = re.compile(r"[0-9a-f]{8}")
_HEX32_RE = re.compile(r"[0-9a-f]{32}")


def is_valid_blast_id(blast_id) -> bool:
    """True for an ID in the format BlastFX generates (8 lowercase hex characters)."""
    return isinstance(blast_id, str) and _BLAST_ID_RE.fullmatch(blast_id) is not None


def is_hex32(name) -> bool:
    """True for a generation or job ID (uuid4().hex)."""
    return _is_hex32(name)


def _is_hex32(name) -> bool:
    return isinstance(name, str) and _HEX32_RE.fullmatch(name) is not None


def is_inside(path: Path, root: Path) -> bool:
    """True when ``path`` resolves (symlinks followed) strictly inside ``root``."""
    real_root = Path(os.path.realpath(root))
    real = Path(os.path.realpath(path))
    return real != real_root and real_root in real.parents


def blast_dir(cache_root: Path, blast_id) -> Path:
    """The cache folder of one blast. Refuses IDs not in the generated format and folders outside the root."""
    if not is_valid_blast_id(blast_id):
        raise ValueError(f"Invalid BlastFX ID {blast_id!r}: expected 8 hexadecimal characters.")
    path = Path(cache_root) / blast_id
    if path.is_symlink() or not is_inside(path, cache_root):
        raise ValueError(f"BlastFX cache folder {path} is not inside the cache root {cache_root}.")
    return path


def has_blastfx_marker(path: Path) -> bool:
    """True when ``path`` holds a BlastFX cache: its generation marker, or a generation folder with its manifest
    (a bake interrupted before the marker was written)."""
    path = Path(path)
    if (path / GENERATION_MARKER).is_file():
        return True
    try:
        children = list(path.iterdir())
    except OSError:
        return False
    return any(
        child.is_dir() and not child.is_symlink() and _is_hex32(child.name)
        and (child / EXPECTED_MARKER).is_file()
        for child in children
    )


def remove_blast_dir(path: Path) -> bool:
    """Delete one blast's cache folder, only when it is safe: a real folder (not a symlink) named like a BlastFX
    ID, inside its parent, and carrying a BlastFX marker. Returns True when it was deleted."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        return False
    if not is_valid_blast_id(path.name) or not is_inside(path, path.parent):
        return False
    if not has_blastfx_marker(path):
        return False
    shutil.rmtree(path)
    return True


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
    if not _is_hex32(generation):
        raise RuntimeError("Blast cache generation marker is invalid.")
    path = Path(cache_root) / generation
    if path.is_symlink() or not path.is_dir() or not is_inside(path, cache_root):
        raise RuntimeError("Blast cache generation directory is missing.")
    return path


def recover_generation(cache_root: Path, cache_data_format: str = "OPENVDB") -> str | None:
    """Filesystem-only recovery for one blast cache root.

    Call at file-load time, when no in-process bake can exist: drops stale
    bake-job snapshot directories and heals a baked marker whose cache files
    disappeared. A broken generation contract is invalidated so a later bake
    starts from a clean slate; valid cache data is never deleted. Returns a
    human-readable action note, or None when nothing needed recovery.

    Nothing is deleted unless the folder is a BlastFX cache: named like a
    BlastFX ID, not a symlink, and carrying a BlastFX marker (see
    ``remove_blast_dir``). Anything else is left untouched.
    """
    cache_root = Path(cache_root)
    if not cache_root.exists():
        return None
    if (
        cache_root.is_symlink()
        or not cache_root.is_dir()
        or not is_valid_blast_id(cache_root.name)
        or not has_blastfx_marker(cache_root)
    ):
        return None
    try:
        generation = _generation_dir_from_root(cache_root)
    except (OSError, RuntimeError):
        remove_blast_dir(cache_root)
        return "invalidated: broken generation contract"

    cleaned = 0
    job_root = generation / "job"
    if job_root.is_dir() and not job_root.is_symlink():
        for job_dir in list(job_root.iterdir()):
            # bake snapshots are uuid4().hex folders; anything else is not ours
            if job_dir.is_symlink() or not job_dir.is_dir() or not _is_hex32(job_dir.name):
                continue
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
            remove_blast_dir(cache_root)
            return "invalidated: unreadable cache markers"
        if expected.get("state_hash") != complete.get("state_hash"):
            remove_blast_dir(cache_root)
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
