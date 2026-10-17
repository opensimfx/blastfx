# Project History

## Original prototype

The original `blastfx.py` prototype is the reference implementation for the
first Mantaflow port. It is intentionally not embedded into the architecture;
port behavior, not structure.

| Prototype area | New destination |
|---|---|
| `PRESETS` | `blastfx/presets/registry.py` |
| `_set()` | `blastfx/utils/compatibility.py` |
| `_key()` | `blastfx/animation/` |
| `_volume_material()` | `blastfx/materials/volume.py` |
| `_glass_material()` | `blastfx/materials/shockwave.py` |
| `_add_flow()` | `blastfx/simulation/` |
| `build_blast()` | `blastfx/core/explosion.py` + simulation builders |
| `BLASTFX_Props` | `blastfx/addon/properties.py` |
| create operator | `blastfx/addon/operators.py` |
| bake/free operators | `blastfx/addon/operators.py` + `simulation/cache.py` |
| remove operator | `blastfx/core/explosion.py` |
| panel | `blastfx/ui/panel.py` |

The original script is a working prototype. The new system preserves its
proven simulation assumptions where appropriate while separating
responsibilities.

## Implementation order (as built)

The tasks were implemented in this order:

1. Scaffold install and registration.
2. Create Blast generating root collection, blast collection, controller.
3. Port of the original prototype's domain builder.
4. Port of fireball.
5. Port of stem.
6. Port of dust.
7. Port of flash.
8. Port of shockwave.
9. Preview/final quality profiles.
10. Cache status and invalidation.
11. Rebuild.
12. Large-blast scale layers (LARGE profile).
13. Cinematic FX.
14. Preset persistence.

The controller and rebuild architecture always came before the large-blast
profile work.

## Roadmap

Status synced with the codebase on 2026-10-17. Checked items were verified
against the source tree and the runtime validation noted in README.md; open
items and caveats are annotated inline.

### Milestone 0 — Scaffold
- [x] package structure
- [x] registration
- [x] property model
- [x] UI skeleton
- [x] controller metadata
- [x] preset registry
- [x] cache abstraction
- [x] validation abstraction

### Milestone 1 — Physics foundation
- [x] SI-oriented physical configuration
- [x] physical derivation layer
- [x] scale-aware configuration boundary
- [x] FPS-independent timing model
- [x] physical-state hashing
- [x] pure Python physics tests
- [x] validated solver mapping
  - Automated physics validation passes 12/12 in Blender 5.2.1
    (`tools/physics_validation.py`: units, FPS-independence, scale behavior,
    quality-tier isolation).
  - Visual calibration complete: `m1_calibration_20261017` (large-profile, PREVIEW,
    res 64, 290 frames, 580 VDBs, 6 review renders) — user visual sign-off
    received. See `DEVELOPMENT.md` (Mantaflow visual calibration).

### Milestone 2 — Existing prototype port
- [x] port domain creation (`simulation/domain.py`)
- [x] port fireball emitter (`simulation/fireball.py`)
- [x] port stem (`simulation/stem.py`)
- [x] port dust ring (`simulation/dust.py`)
- [x] port flash (`animation/flash.py`)
- [x] port shockwave (`simulation/shockwave.py`, `animation/shockwave.py`)
- [x] port volume material (`materials/volume.py`)
- [x] port bake/free (`core/bake_job.py`, `core/blender_bake_worker.py`, `simulation/cache.py`)
- [x] Blender compatibility testing (Blender 5.2 RNA self-test in `core/blender_api.py`)

### Milestone 3 — Engine quality
- [x] deterministic seeds
- [x] rebuild (`core/explosion.py::rebuild_explosion`, `BLASTFX_OT_rebuild`)
- [x] duplicate (`BLASTFX_OT_duplicate` in `addon/operators.py`; verified in
      headless smoke test: new blast id, copied seed/config, offset placement)
- [x] preview/final profiles (proven by `tests/test_simulation_config.py`)
- [x] cache invalidation (content-addressed via `core/physical_state.py::state_hash`)
- [x] status UI (Cache section in `ui/panel.py`, bake job polling)
- [x] validation warnings (`core/validation.py`, `BLASTFX_OT_validate`)

### Milestone 4 — Large-blast scale
Originally built as a dedicated nuclear/mushroom system (multi-stage fireball,
animated cap, base surge, rolling turbulence). Those specialist components were
later removed in a design simplification; the LARGE profile now drives the
`nuclear_ground` preset directly through the conventional pipeline.
- [x] LARGE profile and domain envelope (`core/explosion_profile.py`,
      `core/domain_envelope.py`)
- [x] rising column (`use_stem`, `simulation/stem.py`)
- [x] ground dust (`simulation/dust.py`)
- [x] shock front; visually calibrated via `DEVELOPMENT.md`

### Milestone 5 — Cinematic layer
- [x] flash animation (`animation/flash.py`)
- [x] exposure impulse (`animation/exposure.py`)
- [x] camera shake (`animation/camera.py`)
- [x] heat distortion (`animation/heat_distortion.py`, volume-based,
      physically timed via `phase_frames`)
- [x] atmospheric distortion (event-scale distortion volume
      `build_atmospheric_distortion` in `animation/heat_distortion.py`, gated
      by profile (LARGE 0.3); the compositor hook stays a stub by
      design — the volume approach replaces it)
- [x] volumetric lighting (`animation/dust_light.py`)

### Milestone 6 — Production
- [x] preset save/load (`BLASTFX_OT_save_preset`, `presets/apply.py`, JSON presets)
- [x] batch generation (`BLASTFX_OT_create_batch`: count/spacing/seed-step
      dialog, seeds restored afterwards)
- [x] batch baking (`core/bake_queue.py` + `start_batch_bake`; the one-bake-at-
      a-time worker invariant is preserved, the queue sequences starts —
      verified end-to-end headless: two blasts queued, both caches BAKED)
- [x] robust cache recovery (`core/cache_layout.py::recover_generation` +
      `recover_caches` on `load_post`; invalidates broken generations, lying
      complete markers, stale job dirs; unit-tested + headless scenario test)
- [x] documentation (`docs/`)
- [x] example .blend scenes (`tools/make_examples.py` →
      `examples/test_{small,medium,large,large_event}.blend`: deterministic seeds,
      framed camera, neutral light, no bake; `examples/README.md`)
- [x] release packaging (`tools/package.py`)

### Milestone 7 — Optional
- [ ] Geometry Nodes debris (current debris in `simulation/debris.py` is particle-based)
- [ ] Asset Browser integration
- [ ] custom emitter collections
- [ ] Eevee adapter
- [ ] command-line workflow (headless dev scripts exist in `tools/`; no
      user-facing CLI)
