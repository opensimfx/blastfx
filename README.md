# Blast FX

A modular Blender add-on for authoring physically based procedural cinematic explosions with Mantaflow.

Blast FX builds ground-blast scenes from a coherent physical configuration — SI units, FPS-independent timing, scale-aware domains — rather than hand-keyframed fire and smoke. One click creates a full blast stack: gas domain with a deterministic pre-bake envelope, fireball, rising column, ground dust, shockwave, debris, flash, camera shake, exposure impulse and heat haze. Bakes run in a background Blender worker so the UI stays responsive, and caches are content-addressed: nothing is re-baked unless the physical state actually changed.

> Blast FX is a **visual simulation system**. It produces cinematic explosions; it is not an engineering model of real blasts, yields or damage.

## Features

- **Profiles, not magic numbers** — deterministic `ExplosionProfile` data (source topology, combustion, buoyancy, turbulence, timing, camera framing) drives the sim; `large_ground` preset rides the LARGE profile.
- **Physically timed secondary FX** — flash, shockwave geometry, camera impulse and dust derive their timing from the physical event timeline, not from independent keyframes.
- **Background bake worker** — one non-blocking job at a time, atomic status, cancel-safe; incomplete generations are never reported as baked.
- **Cache you can trust** — state-hash identity covers envelope, profile, seed, FPS, gravity and units; stale or lying caches are detected and invalidated on file load.
- **Quality tiers** — Draft / Preview / Final change only numerical resolution, noise and solver quality, never the underlying event.
- **Scene safety** — generated objects are tagged (`blastfx_role` / `blastfx_id` / `blastfx_component`) and every blast lives in its own removable collection.

## Requirements

- Blender 5.2+ (Mantaflow gas with adaptive domain)
- Cycles for rendering (recommended; renderer choice is a scene setting)

The add-on enforces one Blender unit = one metre. Scenes with other `scale_length` values are rejected at creation rather than mis-simulated.

## Installation

1. Download or build the add-on zip (`tools/package.py` → `blastfx_v1.zip`).
2. In Blender: `Edit > Preferences > Add-ons > Install...` and select the zip.
3. Enable **Blast FX**.

The repository also ships ready-made example scenes under `examples/` (`test_small`, `test_medium`, `test_large`, `test_large_event`) — open one, press **Bake Simulation**, and render.

## Quick start

1. Open `3D View > N > Blast FX`.
2. Pick an explosion type and preset (or a scale/duration directly).
3. Create the blast at the 3D cursor.
4. Tune artistic parameters (components, appearance, cinematic FX).
5. Run a preview bake — inspect motion and silhouette.
6. Run the final bake — full resolution.
7. Render with Cycles.

## Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System layers, blast entity, identity model, rebuild semantics, UI layout, engine services, Blender 5.2 API audit, bake-worker architecture, cache identity |
| [`docs/PHYSICS.md`](docs/PHYSICS.md) | Physics pipeline, SI units, FPS conversion, scale handling, realism tiers and policy, preset profiles, large-blast scope |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Install, dev loop, coding rules, test matrix, bake worker details, Mantaflow calibration workflow, physics validation plan |
| [`docs/HISTORY.md`](docs/HISTORY.md) | Original prototype mapping, implementation order as built, milestone status/open roadmap |

## Contributing

Contributions are welcome — bug fixes, Blender-version compat fixes, and open roadmap items (see `docs/HISTORY.md`).

1. **Read the coding rules** in `docs/DEVELOPMENT.md`. Highlights: no simulation construction in UI panels, no `bpy.context` deep inside pure config code, tagged generated objects, explicit cache invalidation, a useful report from every operator.
2. Set up a developer loop (symlink or zip install; see `docs/DEVELOPMENT.md`).
3. Keep pure logic importable without `bpy` — `bpy`/`mathutils` are only imported inside Blender; the pytest suite runs under plain Python.
4. Add or update tests: `.venv/bin/python -m pytest -q` (profile/config/cache-identity tests live in `tests/`).
5. Validate in Blender with the runtime tools: `tools/blender_runtime_smoke_test.py` (API audit), `tools/physics_validation.py` (units/FPS/scale).
6. Visual/calibration changes go through the controlled workflow in `docs/DEVELOPMENT.md` (Mantaflow visual calibration) — one-factor sweeps, results recorded, no fake precision.

### Specific asks

- Blender version compat reports (5.2 first, then newer builds)
- Headless/CLI workflow hardening
- Geometry Nodes debris, Asset Browser integration (Milestone 7 in `docs/HISTORY.md`)

## License

Blast FX is free software, licensed under the **GNU GPL-3.0 or later** — see [`LICENSE.txt`](LICENSE.txt).

This keeps the add-on compatible with Blender's own GPL codebase and with the Blender Extensions platform. Contributions you submit fall under the same license.

## Development notes

- **`speed` is a simulation-time multiplier**, not a playback control — it changes the physical event timeline for emitters, FX, cache ranges and cache identity.
- **Deterministic envelope**: the Mantaflow domain is sized before baking from radius, velocity, gravity/buoyancy, timeline and voxel margin; bounds are part of cache identity. Adaptive-domain mode only shapes gas inside it.
- **One bake at a time**: per-blast job state, expected-state manifest + completion marker, confirmed-cache-file progress, no fabricated ETAs.
- **Mantaflow is not an explosion solver**: parameters are normalized/proxy controls; a parameter is called "physical" only when its unit, transformation and solver mapping are documented (acceptance rule in `docs/DEVELOPMENT.md`).
