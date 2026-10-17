# Development Guide

## Requirements

- Blender 5.2+
- Python bundled with Blender
- Git
- A Blender project file for local testing

Do not use the system Python to import `bpy`.

## Install during development

### Option A: Blender UI

`Edit > Preferences > Add-ons > Install...`

Select the zip produced by `tools/package.py` (`blastfx_v1.zip` in the repo root).

### Option B: Development symlink

Use Blender's add-on search path or create a symlink into the Blender scripts/addons directory.

Keep the source repository outside Blender's installation directory.

## Recommended development loop

1. Edit source.
2. Open Blender.
3. Install/reload the add-on.
4. Open `N > Blast FX`.
5. Test creation at the 3D cursor.
6. Inspect the generated collection.
7. Test preview bake.
8. Test free cache.
9. Test rebuild.
10. Save/reopen the `.blend`.
11. Test final bake only after preview is correct.

## Reloading during development

The add-on exposes:

`Blast FX > Advanced > Reload`

During early development, restarting Blender is still preferred when changing
registration, property definitions or module imports.

## Coding rules

- Keep functions small.
- Do not put simulation construction in UI panels.
- Do not access `bpy.context` deep inside pure configuration code unless necessary.
- Prefer explicit controller references over active-object discovery.
- Do not silently swallow errors.
- Compatibility helpers may catch expected Blender RNA drift and must log it.
- Generated objects must be tagged.
- Generated collections must be removable without touching user objects.
- Cache invalidation must be explicit.
- Every user-facing operator should provide a useful report.

## Test matrix

At minimum test:

- new scene
- saved scene
- unsaved scene
- one blast
- multiple blasts
- duplicate blast
- rebuild
- delete
- preview cache
- free cache
- final cache
- invalid cache directory
- missing component
- changed preset
- changed seed
- reopened blend file

## Performance

Do not optimize before measuring.

The expected expensive operations are:
1. Mantaflow bake
2. noise/up-resolution bake
3. high-density volume rendering

The add-on should keep procedural setup fast and predictable even when simulation is expensive.

## Mantaflow bake workers

Blast FX starts Mantaflow baking in a separate Blender `--background`
process. The main Blender process saves a temporary snapshot, launches the
worker, and polls an atomic job status file with `bpy.app.timers`; it never
uses Python threads around `bpy` or waits synchronously for `bake_all()`.
Worker output is written into the active cache generation. The main process
validates the generation, state hash, frame range, and VDB/UNI output before
writing the completion marker, because the worker's in-memory scene is not
shared with the user's scene.

Only one bake job is supported per Blender instance. Cancel creates a
`cancel.flag` and terminates a still-running worker if Mantaflow has not
returned. The generation remains incomplete and cannot be reported as baked.
Simulation settings are disabled in the panel while a job is active.
Frame progress is confirmed from completed cache files rather than inferred
from elapsed time; ETA is withheld until enough confirmed samples exist.

### Mantaflow domain envelope

The domain is sized before the worker snapshot is created. Its deterministic
envelope includes lateral expansion, buoyant vertical rise, and a solver
voxel-based safety margin. Mantaflow adaptive-domain mode remains enabled and
the top and lateral collision borders are open, while the bottom remains
closed for the ground interaction. The envelope is not resized during baking;
its normalized bounds and boundary mode are included in the existing physics
state hash.

## Mantaflow visual calibration

This workflow tunes the built-in presets against reproducible renders. It
does not turn the gas solver into a validated blast or combustion simulator.

### What the values mean

Blender flow density and fuel set emitted amounts; flow temperature is an
offset from ambient. Domain `alpha` and `beta` control density- and heat-driven
buoyancy. Global and flame vorticity add turbulence. These are solver controls,
not SI measurements of pressure, heat release, fuel mass, or blast yield.

The add-on maps profile data into those controls in
`blastfx/simulation/physical_config.py` and `blastfx/simulation/domain.py`.
The validation output records the evaluated domain settings so a profile
multiplier is not confused with the final solver value.

### Calibration points

Start with one-factor sweeps from the current accepted profile and keep seed,
scale, timeline, camera, render settings, and all other profile fields fixed:

| Mantaflow setting | Calibration points | Current useful reference |
|---|---|---|
| Density buoyancy (`alpha`) | `0.5`, `1.0`, `1.5` | Blender default is `1.0` |
| Heat buoyancy (`beta`) | `0.5`, `1.0`, `1.5` | Blender default is `1.0` |
| Global vorticity | `0.1`, `0.2`, `0.35` | Blender manual illustrates `0.2` |
| Flame vorticity | `0.25`, `0.5`, `0.75` | Blender default is `0.5` |

These are dimensionless empirical calibration points. They are deliberately
inside Blender's supported ranges; choose a winner from rendered behavior,
not from the largest numeric value. After each one-factor pass, test only the
best neighboring combinations to avoid an unreviewable parameter grid.

Fuel starts from the previously measured `burning_rate = 0.32` and
`source_duration = 1.25`. Keep those fixed during other sweeps. For the Large
profile, test source density, smoke production, buoyancy, and turbulence
before adjusting layer timing. For Large Ground, keep the isolated shockwave
measurable and adjust its emission timing and composite visibility
independently from the fireball.

### Running a controlled candidate

Run one bake per candidate in a fresh Blender process. A JSON profile override
sets the corresponding `ExplosionProfile` fields before scene creation, so
the override participates in the existing physical-state/cache identity.
`results.json` records the complete profile, overrides, rendered samples,
evaluated grids, and final Mantaflow settings.

```sh
BLASTFX_PRESET=large \
BLASTFX_CASE=low_smoke \
BLASTFX_QUALITY=PREVIEW BLASTFX_RESOLUTION=64 \
BLASTFX_OUTPUT="$PWD/blastfx_visual_validation/large_low_smoke" \
BLASTFX_PROFILE_OVERRIDES='{"buoyancy_density":1.0,"buoyancy_heat":1.5,"turbulence":0.35,"flame_vorticity":0.5,"density":0.85,"flame_smoke":1.5}' \
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/visual_validation.py
```

Compare candidates at matching event-relative frames. Use the Preview/Final
tiers for final image judgment; Draft is only for eliminating poor candidates.
Keep isolated-layer images for diagnosis, but accept Large Ground from the
full composite. Maintain the Small preset as a regression reference.

### Current review notes

The 2026-10-06 visual pass produced a new Preview candidate for the large
profile. (The earlier nuclear/mushroom calibration rounds were withdrawn
along with that feature; regenerate any candidate with the recipe above.)

#### Large Ground

The shockwave is now a broad, slightly irregular, translucent annular dust
front. It begins after the fireball, expands to six characteristic radii, and
is framed around the event instead of the oversized simulation domain. A
longer, lower-density ground smoke emission and a soft area backlight keep
dirty smoke visible around the front in the later composite frames.

(Calibration outputs are gitignored; regenerate with the recipe above.)

These are 64-resolution Preview candidates. They demonstrate the intended
silhouettes and timing, but final-resolution visual review is still required.

### Visual acceptance

- **Small:** retain its compact, energetic silhouette and existing regression
  behavior.
- **Fuel:** preserve an irregular multi-lobed flame through the measured burn
  interval, followed by smoke.
- **Large (`large_ground`):** the composite visibly separates fireball, ground
  surge, expanding dust/air front, and lingering dirty smoke, and reads as one
  large event framed by the large-event camera.

Record values as physical only when their units and dimensional mapping are
validated. Otherwise describe them as normalized Mantaflow controls or
empirical VFX calibration values. Never infer yield, pressure, damage, or
hazard radius from these renders.

## Physics validation plan

The add-on should be validated against physical behavior and high-quality
reference footage without pretending that a Blender gas solver is an exact
explosion simulator.

### A. Unit validation

Verify: scene unit scale, metres per Blender unit, FPS, FPS base, gravity, ambient temperature, ambient density.

### B. Temporal validation

For a fixed physical duration, 24 FPS, 30 FPS and 60 FPS must produce the
same event duration in seconds. Only the number of rendered frames should
differ.

### C. Scale validation

Run the same normalized preset at 0.5×, 1×, 2×. Verify that:
- shape proportions remain coherent
- domain dimensions scale
- emitter dimensions scale
- timing remains tied to physical configuration
- turbulence length scale changes appropriately

### D. Numerical validation

Compare Draft, Preview, Final. The underlying physical configuration must
remain constant. Only numerical resolution, noise and solver quality should
change.

### E. Visual reference validation

For each preset, compare: silhouette, expansion timing, vertical rise, smoke
persistence, turbulence scale, brightness falloff, dust motion.

Do not use visual similarity as proof of physical correctness.

### F. Regression scenes

Maintain `.blend` test scenes:

```text
examples/
├── test_small.blend
├── test_medium.blend
├── test_large.blend
└── test_large_event.blend
```

Each scene should contain a camera, neutral lighting and a deterministic seed.

### G. Acceptance rule

A parameter may be called "physical" only if:
1. its unit is known,
2. its transformation is documented,
3. its solver mapping is understood,
4. changing it has predictable dimensional consequences.

Otherwise call it: normalized, proxy, artistic, empirical.
