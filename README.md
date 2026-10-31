# BlastFX

**Procedural cinematic explosions for Blender** — part of [OpenSimFX](https://github.com/opensimfx),
alongside RainFX, FlowFX and AtmosFX.

> BlastFX is a **visual simulation system**. It produces cinematic explosions; it is not an engineering model of real blasts, yields or damage.

![Small blast](docs/previews/small.png)
![Medium blast](docs/previews/medium.png)
![Large blast](docs/previews/large.png)

_Renders: headless Cycles, DRAFT quality (`tools/render_preview.py`). They are validation checks, not showpieces._

BlastFX builds ground-blast scenes from a coherent physical configuration — SI units, FPS-independent timing, scale-aware domains — rather than hand-keyframed fire and smoke. One click creates a full blast stack: gas domain with a deterministic pre-bake envelope, fireball, rising column, ground dust, shockwave, debris, flash, camera shake, exposure impulse and heat haze. Bakes run in a background Blender worker so the UI stays responsive, and caches are content-addressed: nothing is re-baked unless the physical state actually changed.

## Features

- **Profiles, not magic numbers** — deterministic `ExplosionProfile` data (source topology, combustion, buoyancy, turbulence, timing, camera framing) drives the sim; `large_ground` preset rides the LARGE profile.
- **Physically timed secondary FX** — flash, shockwave geometry, camera impulse and dust derive their timing from the physical event timeline, not from independent keyframes.
- **Background bake worker** — one non-blocking job at a time, atomic status, cancel-safe; incomplete generations are never reported as baked.
- **Cache you can trust** — state-hash identity covers envelope, profile, seed, FPS, gravity and units; stale or lying caches are detected and invalidated on file load.
- **Quality tiers** — Draft / Preview / Final change only numerical resolution, noise and solver quality, never the underlying event.
- **Scene safety** — generated objects are tagged (`blastfx_role` / `blastfx_id` / `blastfx_component`) and every blast lives in its own removable collection.

## Install

Requires Blender **5.2 LTS or newer** (Mantaflow gas with adaptive domain).

```bash
python tools/package.py        # -> blastfx_v1.zip
```

In Blender: *Edit > Preferences > Add-ons > Install…*, pick the zip. The panel appears in the 3D Viewport sidebar (**N**) under **Blast FX**.

The repository ships ready-made example scenes under `examples/` (`test_small`, `test_medium`, `test_large`, `test_large_event`) — open one, press **Bake Simulation**, and render.

## Quick start

1. Open the **Blast FX** tab, pick an explosion type and preset (or a scale/duration directly).
2. Create the blast at the 3D cursor.
3. Tune artistic parameters (components, appearance, cinematic FX).
4. Run a preview bake — inspect motion and silhouette.
5. Run the final bake — full resolution.
6. Render with Cycles.

## Verification status (read this)

Verified on **Blender 5.2 LTS**:

- Core logic (profile/config/cache-identity) tested under plain Python via pytest — no `bpy` required.
- Blender runtime smoke tests (`tools/blender_runtime_smoke_test.py`) exercise the full operator surface and API contracts.
- Physics validation (`tools/physics_validation.py`) checks SI units, FPS conversion, scale handling.
- Mantaflow calibration workflow documented in `docs/DEVELOPMENT.md` — one-factor sweeps, results recorded, no fake precision.

**Not verified** — treat as unknown:

- Blender versions newer than 5.2 LTS (compatibility reports welcome).
- Headless/CLI workflow (see `docs/HISTORY.md` Milestone 7).
- Geometry Nodes debris, Asset Browser integration (planned).

## Repository layout

```
blastfx/                 the add-on (what gets zipped)
  core/                  pure Python: profiles, config, cache identity, physics
  ops/                   operators (create, bake, cancel, utilities)
  ui/                    panels, properties, presets
  services/              bake worker, cache, estimates, impulses
  examples/              test_small, test_medium, test_large, test_large_event
tools/                   package, validation, calibration, runtime smoke tests
docs/                    ARCHITECTURE, PHYSICS, DEVELOPMENT, HISTORY
tests/                   pytest suites (pure Python, no bpy)
```

## Generate Previews

```bash
# Requires desktop Blender 5.2+ (not headless bpy wheel — Mantaflow needs the full build)
# Usage: /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
#        --python tools/render_preview.py -- <preset> <output.png> [samples]

/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python tools/render_preview.py -- small docs/previews/small.png 48

/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python tools/render_preview.py -- medium docs/previews/medium.png 48

/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python tools/render_preview.py -- large docs/previews/large.png 48
```

Presets: `small`, `medium`, `large`, `large_ground`, `nuclear_airburst`, `nuclear_groundburst`

## Develop

```bash
# Pure tests (no Blender)
python -m pytest -q

# Blender runtime checks (needs bpy 5.2)
python tools/blender_runtime_smoke_test.py
python tools/physics_validation.py

# Build the extension zip
python tools/package.py
```

See `docs/DEVELOPMENT.md` for the full dev loop, coding rules, test matrix, and Mantaflow calibration workflow.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Physics](docs/PHYSICS.md) · [Development](docs/DEVELOPMENT.md) · [History & Roadmap](docs/HISTORY.md)

## License

GPL-3.0-or-later — see [`LICENSE.txt`](LICENSE.txt).

This keeps the add-on compatible with Blender's own GPL codebase and with the Blender Extensions platform. Contributions you submit fall under the same license.