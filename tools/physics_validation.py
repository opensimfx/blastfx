"""Headless physics validation harness for Blast FX (plan sections A-D).

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python tools/physics_validation.py -- [--output report.json]

Every assertion goes through the public ``create_explosion`` path at DRAFT
quality and never bakes. Physical expectations are recomputed from the pure
bpy-free model (physics/domain_envelope/physical_config) and compared against
the RNA values the add-on actually wrote, so a wiring bug in the create path
shows up as expected-vs-observed drift.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

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

sys.path.insert(0, "/Users/arsh/Developer/Projects/blastfx")

import bpy  # noqa: E402
from blastfx.addon.registration import register, unregister  # noqa: E402
from blastfx.core.explosion import create_explosion  # noqa: E402
from blastfx.core.physics import (  # noqa: E402
    AmbientConditions,
    PhysicalConfig,
    derive_physics,
    gravity_magnitude,
)
from blastfx.core.domain_envelope import build_domain_envelope  # noqa: E402
from blastfx.core.explosion_profile import profile_for  # noqa: E402
from blastfx.simulation.physical_config import build_simulation_config  # noqa: E402

FPS_TIERS = (24, 30, 60)
SCALE_TIERS = (0.5, 1.0, 2.0)
QUALITY_TIERS = ("DRAFT", "PREVIEW", "FINAL")

# Every check a case is expected to emit, so a crash mid-case still reports
# each named check as failed instead of silently dropping it.
CASE_CHECKS = {
    "A": ("A.unit_scale_0.5_rejected", "A.unit_scale_1.0_accepted"),
    "B": (
        "B.event_seconds_constant",
        "B.event_seconds_match_physics",
        "B.frame_counts_scale_with_fps",
    ),
    "C": (
        "C.characteristic_radius_scales",
        "C.event_seconds_constant",
        "C.resolution_unchanged",
        "C.domain_dimensions_scale",
    ),
    "D": (
        "D.derived_physics_identical",
        "D.solver_settings_identical",
        "D.resolution_differs_by_quality",
    ),
}


@dataclass
class Check:
    name: str
    passed: bool
    expected: object = None
    observed: object = None
    notes: str = ""


RESULTS: list[Check] = []


def _record(name, passed, expected=None, observed=None, notes=""):
    state = "PASS" if passed else "FAIL"
    print(f"[{state}] {name}")
    if not passed:
        print(f"    expected: {expected}")
        print(f"    observed: {observed}")
    elif notes:
        print(f"    {notes}")
    RESULTS.append(Check(name, bool(passed), expected, observed, notes))


def _fresh_scene():
    """Empty data block so every case starts from identical scene state."""
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 24
    scene.render.fps_base = 1.0
    scene.cursor.location = (0.0, 0.0, 0.0)
    return scene


def _apply_props(scene, *, scale=1.0, duration=8.0, speed=1.0, quality="DRAFT",
                 seed=100, explosion_type="FUEL"):
    props = scene.blastfx
    props.explosion_type = explosion_type
    props.scale = scale
    props.intensity = 1.0
    props.duration = duration
    props.speed = speed
    props.start_frame = 1
    props.seed = seed
    props.quality = quality
    props.resolution = 0  # 0 = auto (128 base)
    props.noise_upres = 2
    props.turbulence = 1.0
    props.smoke_density = 1.0
    props.fire_temperature = 1.0
    return props


def _domain_object(controller):
    collection = controller.users_collection[0]
    return next(o for o in collection.objects if o.get("blastfx_role") == "domain")


def _domain_settings(domain_obj):
    return next(
        m.domain_settings for m in domain_obj.modifiers
        if m.type == "FLUID" and m.domain_settings is not None
    )


def _expected(scene, *, scale=1.0, duration=8.0, speed=1.0, quality="DRAFT",
              explosion_type="FUEL"):
    """Recompute the authoritative physics chain from the pure model."""
    physical = derive_physics(PhysicalConfig(
        scale_m=scale,
        reference_energy=1.0,
        intensity=1.0,
        duration_s=duration,
        ambient=AmbientConditions(gravity=gravity_magnitude(scene.gravity)),
    ))
    profile = profile_for(explosion_type)
    numerical = build_simulation_config(physical, quality, 0, 2, 100,
                                        1.0, 1.0, 1.0, profile)
    timeline_s = physical.characteristic_time_s / max(speed, 0.05)
    envelope = build_domain_envelope(
        physical, numerical, gravity_magnitude(scene.gravity), timeline_s, profile
    )
    return physical, numerical, timeline_s, envelope


def case_a():
    scene = _fresh_scene()
    _apply_props(scene)
    scene.unit_settings.scale_length = 0.5
    try:
        create_explosion(bpy.context)
        _record("A.unit_scale_0.5_rejected", False, "ValueError",
                "create_explosion succeeded")
    except ValueError as exc:
        _record("A.unit_scale_0.5_rejected", True, "ValueError",
                f"ValueError: {exc}", notes=str(exc)[:120])
    except Exception as exc:  # noqa: BLE001
        _record("A.unit_scale_0.5_rejected", False, "ValueError",
                f"{type(exc).__name__}: {exc}")

    scene.unit_settings.scale_length = 1.0
    try:
        controller, _ = create_explosion(bpy.context)
        domain = _domain_object(controller)
        ok = bool(controller.get("blastfx_controller")) and \
            domain.get("blastfx_role") == "domain"
        _record("A.unit_scale_1.0_accepted", ok, "controller + domain created",
                f"controller={bool(controller.get('blastfx_controller'))} "
                f"domain_role={domain.get('blastfx_role')}",
                notes=f"domain={domain.name}")
    except Exception as exc:  # noqa: BLE001
        _record("A.unit_scale_1.0_accepted", False, "controller + domain created",
                f"{type(exc).__name__}: {exc}")


def case_b():
    observed = {}
    for fps in FPS_TIERS:
        scene = _fresh_scene()
        scene.render.fps = fps
        scene.render.fps_base = 1.0
        _apply_props(scene)
        controller, _ = create_explosion(bpy.context)
        domain = _domain_settings(_domain_object(controller))
        frames = int(domain.cache_frame_end) - int(domain.cache_frame_start)
        observed[fps] = {
            "char_time_s": float(controller["blastfx_characteristic_time_s"]),
            "frames": frames,
            "event_s": frames / fps,
        }

    scene = _fresh_scene()
    _apply_props(scene)
    _, _, timeline_s, _ = _expected(scene)

    times = [observed[f]["char_time_s"] for f in FPS_TIERS]
    _record("B.event_seconds_constant", max(times) - min(times) < 1e-9,
            f"all equal (e.g. {times[0]!r})", times)
    _record("B.event_seconds_match_physics",
            all(abs(t - timeline_s) < 1e-9 for t in times), timeline_s, times)

    expected_frames = [max(1, round(timeline_s * f)) for f in FPS_TIERS]
    counts = [observed[f]["frames"] for f in FPS_TIERS]
    within_half_frame = all(
        abs(observed[f]["event_s"] - timeline_s) <= 0.5 / f + 1e-9 for f in FPS_TIERS
    )
    _record("B.frame_counts_scale_with_fps", counts == expected_frames and within_half_frame,
            expected_frames, counts,
            notes=f"event seconds per tier {[observed[f]['event_s'] for f in FPS_TIERS]}")


def case_c():
    observed = {}
    for scale in SCALE_TIERS:
        scene = _fresh_scene()
        _apply_props(scene, scale=scale)
        controller, _ = create_explosion(bpy.context)
        bpy.context.view_layer.update()  # refresh derived dimensions (obj.scale set post-create)
        domain_obj = _domain_object(controller)
        domain = _domain_settings(domain_obj)
        observed[scale] = {
            "radius": float(controller["blastfx_characteristic_radius_m"]),
            "char_time_s": float(controller["blastfx_characteristic_time_s"]),
            "resolution": int(domain.resolution_max),
            "dimensions": tuple(float(v) for v in domain_obj.dimensions),
        }

    scene = _fresh_scene()
    expected = {s: _expected(scene, scale=s) for s in SCALE_TIERS}

    # C.1 characteristic radius is exactly proportional to scale.
    unit_radius = observed[1.0]["radius"]
    radius_ok = all(
        abs(observed[s]["radius"] - s * unit_radius) < 1e-9 for s in SCALE_TIERS
    )
    _record("C.characteristic_radius_scales", radius_ok,
            f"radius == {unit_radius} * scale",
            {s: observed[s]["radius"] for s in SCALE_TIERS})

    # C.2 event duration in seconds is scale independent.
    times = [observed[s]["char_time_s"] for s in SCALE_TIERS]
    timeline_s = expected[1.0][2]
    _record("C.event_seconds_constant",
            max(times) - min(times) < 1e-9 and all(abs(t - timeline_s) < 1e-9 for t in times),
            timeline_s, times)

    # C.3 domain resolution does not change with scale.
    resolutions = [observed[s]["resolution"] for s in SCALE_TIERS]
    _record("C.resolution_unchanged", len(set(resolutions)) == 1,
            expected[1.0][1].domain_resolution, resolutions)

    # C.4 dimensions match the pure envelope; lateral axes scale ~4x with the
    # blast, vertical grows with it (buoyant rise follows sqrt scaling, so it
    # is not strictly linear — only lateral is asserted at 4x).
    dims = {s: observed[s]["dimensions"] for s in SCALE_TIERS}
    size_matches_pure = all(
        all(abs(dims[s][i] - float(expected[s][3]["size"][i])) < 1e-5 for i in range(3))
        for s in SCALE_TIERS
    )
    lateral_ratio = dims[2.0][0] / dims[0.5][0] if dims[0.5][0] else 0.0
    vertical_ratio = dims[2.0][2] / dims[0.5][2] if dims[0.5][2] else 0.0
    vertical_grows = dims[2.0][2] > dims[1.0][2] > dims[0.5][2]
    _record("C.domain_dimensions_scale",
            size_matches_pure and abs(lateral_ratio - 4.0) < 0.04 and vertical_grows,
            "dims == pure envelope size; lateral(2.0/0.5) ~= 4; vertical strictly grows",
            dims,
            notes=f"lateral_ratio={lateral_ratio:.4f} vertical_ratio={vertical_ratio:.4f}")


def case_d():
    observed = {}
    for quality in QUALITY_TIERS:
        scene = _fresh_scene()
        _apply_props(scene, quality=quality)
        controller, _ = create_explosion(bpy.context)
        domain = _domain_settings(_domain_object(controller))
        observed[quality] = {
            "radius": float(controller["blastfx_characteristic_radius_m"]),
            "char_time_s": float(controller["blastfx_characteristic_time_s"]),
            "velocity": float(controller["blastfx_characteristic_velocity_mps"]),
            "resolution": int(domain.resolution_max),
            "solver": {
                name: float(getattr(domain, name)) for name in (
                    "alpha", "beta", "vorticity", "burning_rate",
                    "flame_smoke", "flame_vorticity", "flame_ignition",
                    "flame_max_temp",
                )
            },
        }

    scene = _fresh_scene()
    expected = {q: _expected(scene, quality=q) for q in QUALITY_TIERS}
    derived_map = {
        "radius": "characteristic_radius_m",
        "char_time_s": "characteristic_time_s",
        "velocity": "characteristic_velocity_mps",
    }

    derived_identical = all(
        len({round(observed[q][k], 12) for q in QUALITY_TIERS}) == 1
        for k in derived_map
    )
    derived_matches_pure = all(
        abs(observed[q][k] - getattr(expected[q][0], derived_map[k])) < 1e-9
        for q in QUALITY_TIERS for k in derived_map
    )
    _record("D.derived_physics_identical", derived_identical and derived_matches_pure,
            "identical derived radius/time/velocity across tiers",
            {q: {k: observed[q][k] for k in derived_map} for q in QUALITY_TIERS})

    solver_identical = all(
        len({observed[q]["solver"][k] for q in QUALITY_TIERS}) == 1
        for k in observed["DRAFT"]["solver"]
    )
    _record("D.solver_settings_identical", solver_identical,
            "identical solver RNA across tiers",
            {q: observed[q]["solver"] for q in QUALITY_TIERS})

    expected_res = {q: expected[q][1].domain_resolution for q in QUALITY_TIERS}
    observed_res = {q: observed[q]["resolution"] for q in QUALITY_TIERS}
    ordered = observed_res["DRAFT"] < observed_res["PREVIEW"] < observed_res["FINAL"]
    _record("D.resolution_differs_by_quality", ordered and observed_res == expected_res,
            expected_res, observed_res, notes="DRAFT < PREVIEW < FINAL")


def _parse_output():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    output = os.environ.get("BLASTFX_VALIDATION_OUTPUT")
    index = 0
    while index < len(argv):
        if argv[index] == "--output" and index + 1 < len(argv):
            output = argv[index + 1]
            index += 2
        else:
            index += 1
    return Path(output).expanduser().resolve() if output else None


def run_case(key, fn):
    before = len(RESULTS)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        recorded = {result.name for result in RESULTS[before:]}
        for name in CASE_CHECKS[key]:
            if name not in recorded:
                _record(name, False, "case completed", f"aborted: {exc!r}")


def main():
    register()
    try:
        for key, fn in (("A", case_a), ("B", case_b), ("C", case_c), ("D", case_d)):
            print(f"\n=== SECTION {key} ===")
            run_case(key, fn)
    finally:
        unregister()

    failed = [result for result in RESULTS if not result.passed]
    print(f"\nPHYSICS VALIDATION: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    for result in failed:
        print(f"  FAIL {result.name}: expected {result.expected} observed {result.observed}")

    output = _parse_output()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "passed": not failed,
            "checks": [asdict(result) for result in RESULTS],
        }, indent=2, default=str), encoding="utf-8")
        print(f"report: {output}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
