"""Asynchronous Mantaflow bake job orchestration.

The worker owns Blender/Mantaflow execution. The main process owns job
coordination and remains the authority for cache completion.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import traceback
import uuid
from pathlib import Path

import bpy

from .cache import (
    active_cache_path,
    clear_baked_marker,
    inspect_mantaflow_cache_tree,
    mark_baked,
    status as cache_status,
    validate_cache_output,
)
from .bake_queue import BakeQueue
from ..simulation.cache import validate_bake_setup


POLL_INTERVAL = 0.4
JOB_STATES = frozenset(
    {
        "IDLE",
        "PREPARING",
        "LAUNCHING",
        "BAKING_DATA",
        "BAKING_NOISE",
        "BAKE_OPERATOR_RETURNED",
        "VERIFYING_CACHE",
        "VERIFIED",
        "FINALIZING",
        "COMPLETED",
        "FAILED",
        "CANCEL_REQUESTED",
        "CANCELLED",
        "PARTIAL",
    }
)
_ACTIVE_JOB = None
_QUEUE = BakeQueue()


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _job_dir(props, blast_id: str, job_id: str) -> Path:
    generation = active_cache_path(props, blast_id)
    path = generation / "job" / job_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_status(job: dict, state: str, message: str = "", **extra) -> None:
    if state not in JOB_STATES:
        raise ValueError(f"Unknown bake job state: {state}")
    payload = {
        "job_id": job["job_id"],
        "blast_id": job["blast_id"],
        "state": state,
        "elapsed_seconds": max(0.0, time.monotonic() - job["started_monotonic"]),
        "pid": job.get("pid"),
        "frame_start": job["frame_start"],
        "frame_end": job["frame_end"],
        "generation": job["generation"],
        "message": message,
        **extra,
    }
    _atomic_json(job["status_path"], payload)


def _cache_progress(job: dict) -> dict:
    """Read confirmed frame output without inspecting the worker's Blender state."""
    try:
        cache_path = active_cache_path(bpy.context.scene.blastfx, job["blast_id"])
    except RuntimeError:
        return {}
    frames = []
    for path in cache_path.rglob("*"):
        if path.suffix.lower() not in {".vdb", ".uni"}:
            continue
        matches = re.findall(r"(?<!\d)(\d{1,8})(?!\d)", path.stem)
        frames.extend(int(value) for value in matches)
    if not frames:
        return {}
    current = min(max(frames), job["frame_end"])
    span = max(job["frame_end"] - job["frame_start"], 1)
    progress = min(1.0, max(0.0, (current - job["frame_start"]) / span))
    return {
        "current_frame": current,
        "progress": progress,
        "message": f"Baking frame {current} / {job['frame_end']}",
    }


def active_job() -> dict | None:
    return _ACTIVE_JOB


def active_job_for(blast_id: str) -> bool:
    return bool(_ACTIVE_JOB and _ACTIVE_JOB["blast_id"] == blast_id)


def pending_bakes() -> tuple:
    """Blast ids waiting in the batch queue (excludes the running bake)."""
    return _QUEUE.pending()


def _domain_for(controller):
    collection = next(
        (c for c in controller.users_collection if c.name.startswith("Blast_")),
        None,
    )
    if collection is None:
        return None
    return _find_domain(collection, controller["blastfx_id"])


def start_batch_bake(context, controllers) -> dict:
    """Queue controllers for sequential baking and start the first bake.

    The single-bake invariant holds: the queue only feeds the one-job-at-a-time
    machinery. Blasts whose cache already validates as BAKED are skipped.
    """
    if _ACTIVE_JOB is not None:
        raise RuntimeError("A Blast FX bake is already running.")
    props = context.scene.blastfx
    queued = 0
    skipped = []
    for controller in controllers:
        blast_id = controller.get("blastfx_id", "")
        try:
            state = cache_status(
                props,
                blast_id,
                _domain_for(controller),
                controller.get("blastfx_physics_state"),
            )
        except Exception:
            state = "UNKNOWN"
        if state == "BAKED":
            skipped.append(blast_id)
            continue
        queued += int(_QUEUE.enqueue(blast_id))
    started = _start_next_queued_job()
    return {"queued": queued, "skipped": tuple(skipped), "started": started}


def _start_next_queued_job() -> bool:
    """Pop queue entries until one bake starts; False when the queue drains."""
    while True:
        blast_id = _QUEUE.dequeue()
        if blast_id is None:
            return False
        controller = bpy.data.objects.get(f"BlastController_{blast_id}")
        if controller is None:
            print(f"Blast FX bake queue: {blast_id} no longer exists, skipping.")
            continue
        domain = _domain_for(controller)
        if domain is None:
            print(f"Blast FX bake queue: {blast_id} has no domain, skipping.")
            continue
        try:
            if cache_status(
                bpy.context.scene.blastfx,
                blast_id,
                domain,
                controller.get("blastfx_physics_state"),
            ) == "BAKED":
                print(f"Blast FX bake queue: {blast_id} is already baked, skipping.")
                continue
        except Exception:
            pass  # unreadable cache state still deserves a bake attempt
        try:
            start(bpy.context, controller, domain)
            return True
        except Exception as exc:
            # One broken blast must not stall the batch; keep draining.
            print(f"Blast FX bake queue: starting bake for {blast_id} failed: {exc}")


def job_status(controller) -> dict | None:
    path = controller.get("blastfx_bake_status_path")
    if not path:
        return None
    try:
        return _read_json(Path(path))
    except (OSError, ValueError):
        return None


def request_cancel(controller) -> None:
    job = _ACTIVE_JOB
    if not job or job["blast_id"] != controller.get("blastfx_id"):
        raise RuntimeError("No active bake exists for this blast.")
    drained = _QUEUE.clear()
    if drained:
        print(f"Blast FX bake queue: cancelled {drained} queued bake(s).")
    job["cancel_path"].write_text("cancel requested\n", encoding="utf-8")
    _write_status(job, "CANCEL_REQUESTED", "Cancellation requested by user.")


def _find_domain(collection, blast_id: str):
    return next(
        (
            obj for obj in collection.objects
            if obj.get("blastfx_role") == "domain"
            and obj.get("blastfx_id") == blast_id
        ),
        None,
    )


def start(context, controller, domain_obj) -> dict:
    global _ACTIVE_JOB
    if _ACTIVE_JOB is not None:
        raise RuntimeError("A Blast FX bake is already running.")

    props = context.scene.blastfx
    blast_id = controller["blastfx_id"]
    validate_bake_setup(context, domain_obj)
    generation_path = active_cache_path(props, blast_id)
    modifier = domain_obj.modifiers.get("BlastFX Fluid") or domain_obj.modifiers.get("Fluid")
    domain_settings = modifier.domain_settings
    absolute_cache = Path(bpy.path.abspath(domain_settings.cache_directory)).resolve()
    if absolute_cache != generation_path.resolve():
        raise RuntimeError(
            "Domain cache path does not match authoritative generation: "
            f"{absolute_cache} != {generation_path.resolve()}"
        )
    absolute_cache.mkdir(parents=True, exist_ok=True)
    probe = absolute_cache / ".blastfx_worker_probe"
    probe.write_bytes(b"blastfx")
    if probe.read_bytes() != b"blastfx":
        raise OSError(f"Cache directory probe failed: {absolute_cache}")
    probe.unlink()
    domain_settings.cache_directory = str(absolute_cache)
    bpy.context.preferences.filepaths.use_relative_paths = False
    print(
        "Blast FX cache contract:",
        f"generation={generation_path.name}",
        f"cache={absolute_cache}",
        f"realpath={os.path.realpath(absolute_cache)}",
        f"format={domain_settings.cache_data_format}",
        f"type={domain_settings.cache_type}",
        f"frames={domain_settings.cache_frame_start}-{domain_settings.cache_frame_end}",
        f"resolution={domain_settings.resolution_max}",
        f"blend={bpy.data.filepath}",
        f"cwd={os.getcwd()}",
    )
    expected = json.loads(
        (generation_path / ".blastfx_expected.json").read_text(encoding="utf-8")
    )
    job_id = uuid.uuid4().hex
    job_dir = _job_dir(props, blast_id, job_id)
    scene_path = job_dir / "scene.blend"
    status_path = job_dir / "status.json"
    cancel_path = job_dir / "cancel.flag"
    log_path = job_dir / "worker.log"

    # save_as_mainfile(copy=True) writes the prepared state without changing
    # the user's current .blend path or replacing their working file.
    result = bpy.ops.wm.save_as_mainfile(filepath=str(scene_path), copy=True)
    if "FINISHED" not in result:
        raise RuntimeError("Could not save the temporary bake snapshot.")

    job = {
        "job_id": job_id,
        "blast_id": blast_id,
        "generation": expected["generation"],
        "frame_start": expected["frame_start"],
        "frame_end": expected["frame_end"],
        "status_path": status_path,
        "cancel_path": cancel_path,
        "started_monotonic": time.monotonic(),
        "process": None,
    }
    request = {
        "job_id": job_id,
        "blast_id": blast_id,
        "generation": expected["generation"],
        "scene_path": str(scene_path),
        "cache_path": str(generation_path),
        "cache_data_format": str(domain_settings.cache_data_format),
        "cache_type": str(domain_settings.cache_type),
        "frame_start": expected["frame_start"],
        "frame_end": expected["frame_end"],
        "quality": props.quality,
        "noise": int(props.noise_upres),
        "log_path": str(log_path),
        "status_path": str(status_path),
        "cancel_path": str(cancel_path),
    }
    _atomic_json(job_dir / "request.json", request)
    _write_status(job, "PREPARING", "Bake snapshot prepared.")

    blender_binary = bpy.app.binary_path
    if not blender_binary:
        raise RuntimeError("Blender executable path is unavailable.")
    worker_script = Path(__file__).resolve().parent / "blender_bake_worker.py"
    environment = os.environ.copy()
    environment["BLASTFX_BAKE_REQUEST"] = str(job_dir / "request.json")
    log_handle = log_path.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [blender_binary, "--background", "--python", str(worker_script)],
            cwd=str(worker_script.parents[1]),
            env=environment,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
    except Exception:
        log_handle.close()
        raise
    log_handle.close()
    job["process"] = process
    job["pid"] = process.pid
    _ACTIVE_JOB = job
    controller["blastfx_bake_job_id"] = job_id
    controller["blastfx_bake_status_path"] = str(status_path)
    controller["blastfx_bake_log_path"] = str(log_path)
    _write_status(job, "LAUNCHING", "Blender bake worker launched.")
    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, first_interval=POLL_INTERVAL)
    return job


def _finish(job, controller, state: str, message: str, **extra) -> None:
    global _ACTIVE_JOB
    _write_status(job, state, message, **extra)
    controller["blastfx_bake_state"] = state
    _ACTIVE_JOB = None


def _redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {"VIEW_3D", "PROPERTIES"}:
                area.tag_redraw()


def _poll():
    global _ACTIVE_JOB
    job = _ACTIVE_JOB
    if job is None:
        return None
    controller = bpy.data.objects.get(f"BlastController_{job['blast_id']}")
    if controller is None:
        if job["process"].poll() is None:
            job["process"].terminate()
        _ACTIVE_JOB = None
        _start_next_queued_job()
        return POLL_INTERVAL if _ACTIVE_JOB is not None else None
    try:
        status = _read_json(job["status_path"])
    except (OSError, ValueError):
        status = {}

    confirmed_progress = _cache_progress(job)
    if confirmed_progress:
        status.update(confirmed_progress)
        progress = status.get("progress")
        if progress is not None and progress > 0:
            samples = job.setdefault("progress_samples", [])
            samples.append((time.monotonic(), progress))
            if len(samples) >= 2:
                elapsed = time.monotonic() - job["started_monotonic"]
                remaining = elapsed * (1.0 - progress) / progress
                status["eta_seconds"] = max(0.0, remaining)

    if status.get("state") == "CANCEL_REQUESTED":
        process = job["process"]
        if process.poll() is None:
            process.terminate()
            _redraw()
            return POLL_INTERVAL

    process = job["process"]
    if process.poll() is None:
        _write_status(
            job,
            status.get("state", "BAKING_DATA"),
            status.get("message", "Baking simulation."),
            **{
                key: status[key]
                for key in ("current_frame", "progress", "eta_seconds")
                if key in status
            },
        )
        _redraw()
        return POLL_INTERVAL

    if status.get("state") == "CANCEL_REQUESTED":
        _finish(job, controller, "CANCELLED", "Bake cancelled.")
        clear_baked_marker(bpy.context.scene.blastfx, job["blast_id"])
        _redraw()
        # request_cancel already drained the queue; this is a safety no-op.
        _start_next_queued_job()
        return POLL_INTERVAL if _ACTIVE_JOB is not None else None

    if process.returncode == 0 and not job.get("validation_started"):
        confirmed = _cache_progress(job)
        job["validation_started"] = True
        _write_status(
            job,
            "FINALIZING",
            "Validating cache...",
            current_frame=confirmed.get("current_frame", job["frame_end"]),
            progress=confirmed.get("progress", 1.0),
        )
        _redraw()
        return POLL_INTERVAL

    props = bpy.context.scene.blastfx
    domain = _find_domain(controller.users_collection[0], job["blast_id"])
    try:
        if process.returncode != 0:
            raise RuntimeError(
                status.get("message") or f"Bake worker exited with code {process.returncode}."
            )
        if domain is None:
            raise RuntimeError("Blast domain no longer exists in the main scene.")
        cache_path = active_cache_path(props, job["blast_id"])
        cache_format = domain.modifiers.get("BlastFX Fluid").domain_settings.cache_data_format
        inspection = inspect_mantaflow_cache_tree(cache_path, cache_format)
        print(
            "Blast FX main cache inspection:",
            f"cache={cache_path.resolve()}",
            f"format={cache_format}",
            f"volumetric={inspection['volumetric_count']}",
            f"bytes={inspection['total_bytes']}",
            f"frames={inspection['first_frame']}-{inspection['last_frame']}",
        )
        if not validate_cache_output(
            props,
            job["blast_id"],
            state_hash=controller.get("blastfx_physics_state"),
            frame_start=job["frame_start"],
            frame_end=job["frame_end"],
            cache_data_format=cache_format,
        ):
            raise RuntimeError(
                "Worker exited without valid cache output: "
                f"format={cache_format} files={inspection['volumetric_count']} "
                f"bytes={inspection['total_bytes']} "
                f"frames={inspection['first_frame']}-{inspection['last_frame']}"
            )
        mark_baked(
            props,
            job["blast_id"],
            state_hash=controller.get("blastfx_physics_state", ""),
        )
    except Exception as exc:
        clear_baked_marker(props, job["blast_id"])
        try:
            cache_path = active_cache_path(props, job["blast_id"])
            has_partial_output = any(cache_path.rglob("*.vdb")) or any(
                cache_path.rglob("*.uni")
            )
        except RuntimeError:
            has_partial_output = False
        _finish(job, controller, "PARTIAL" if has_partial_output else "FAILED", str(exc))
        print(f"Blast FX bake worker validation failed:\n{traceback.format_exc()}")
        _redraw()
        _start_next_queued_job()
        return POLL_INTERVAL if _ACTIVE_JOB is not None else None
    _finish(
        job,
        controller,
        "COMPLETED",
        "Bake completed — cache validated.",
        current_frame=job["frame_end"],
        progress=1.0,
    )
    _redraw()
    _start_next_queued_job()
    return POLL_INTERVAL if _ACTIVE_JOB is not None else None
