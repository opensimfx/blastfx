# Blast FX Architecture

## 1. System boundary

Blast FX sits between the artist and Blender's simulation/rendering systems.

```text
Artist
  |
  v
UI / Properties
  |
  v
Explosion Controller
  |
  +--> Preset Resolver
  +--> Validation
  +--> Simulation Builders
  +--> Material Builders
  +--> Animation / FX
  +--> Cache Manager
  |
  v
Blender / Mantaflow / Renderer
```

## 2. Core layers

### Presentation

`ui/`

Blender panels, menus and status presentation.

### Domain model

`addon/properties.py`

Artist-facing state. This should remain renderer/simulation agnostic
where possible.

### Orchestration

`core/explosion.py`

Coordinates creation, rebuild, deletion and synchronization.

### Simulation

`simulation/`

Builds Mantaflow domains, emitters, velocity systems and cache configuration.

### Appearance

`materials/`

Creates and updates volume, fire, smoke, dust and shockwave materials.

### Animation

`animation/`

Controls flash, shockwave expansion, camera impulse, exposure and timing.

### Presets

`presets/`

Converts a preset into engine configuration.

### Infrastructure

`utils/`, `core/cache.py`, `core/validation.py`

Naming, logging, compatibility, cache paths and validation.

## 3. Explosion entity

Every blast is represented by a controller object and a dedicated collection.

```text
BlastFX
└── Blast_001
    ├── Controller
    ├── Simulation
    │   ├── Domain
    │   ├── Fireball
    │   ├── Stem
    │   └── Dust
    ├── FX
    │   ├── Shockwave
    │   ├── Debris
    │   └── HeatDistortion
    ├── Lighting
    │   └── Flash
    └── Materials
```

## 4. Stable identity

Every blast has:

- `blast_id`
- `blast_type`
- `preset_id`
- `seed`
- `version`

Objects receive:

- `blastfx_role`
- `blastfx_id`
- `blastfx_component`

The engine must never depend on display names to find components.

## 5. Rebuild model

`Rebuild` should be deterministic from:

```text
Blast Properties
+
Preset
+
Seed
+
Engine Version
```

A rebuild should:

1. validate the controller
2. preserve user-authored external scene objects
3. remove/recreate generated components
4. restore component references
5. invalidate the cache
6. report changes

## 6. Quality profiles

Draft, Preview and Final are quality profiles, not separate simulation engines.

- **Draft** — UI and structural validation: 64–96 resolution, noise off, short
  frame range.
- **Preview** — motion and shape: 96–160 resolution, optional noise, normal
  frame range.
- **Final** — rendering: 256+ resolution, noise enabled, full frame range.

Actual defaults must remain configurable. The underlying physical
configuration must never change between profiles; only numerical resolution,
noise and solver quality do.

## 7. Engine services

```text
ExplosionEngine
  create()
  rebuild()
  remove()
  duplicate()
  validate()

SimulationEngine
  build_domain()
  build_fireball()
  build_stem()
  build_dust()
  configure()
  bake()
  free()

MaterialEngine
  build_volume()
  build_fire()
  build_dust()
  build_shockwave()

FXEngine
  build_flash()
  build_shockwave()
  build_camera_fx()

CacheManager
  get_path()
  invalidate()
  status()
  free()
```

## 8. Error model

Use structured validation results rather than exceptions for expected
artist errors.

```python
ValidationResult(
    ok=False,
    errors=[...],
    warnings=[...],
)
```

Unexpected programming errors should still raise.

## 9. Security / scene safety

Blast FX should only mutate:

- its own generated collection
- explicitly selected Blast FX controllers
- scene properties belonging to Blast FX

Never delete arbitrary selected objects as part of a rebuild.

## 10. Physical model layer

The engine contains a dedicated `core.physics` layer.

Its responsibility is to translate artist intent into internally coherent
simulation quantities.

```text
PhysicalConfig
      |
      v
derive_physics()
      |
      +--> characteristic radius
      +--> characteristic time
      +--> characteristic velocity
      +--> buoyancy strength
      +--> normalized temperature
      |
      v
SimulationConfig
```

The physical model must not be confused with a validated engineering
blast-effects model.

## 11. Determinism

The generated controller stores a hash of its physical configuration.

The hash includes:

- preset version
- add-on version
- Blender version
- Mantaflow configuration
- seed
- unit settings
- frame rate

## 12. Physics-to-FX dependency rule

FX must consume the physical timeline.

```text
physical event
    |
    +--> fireball expansion
    +--> shock-front timing
    +--> buoyant rise
    +--> dust response
    +--> light pulse
```

The flash, shockwave, camera shake and smoke should not each have
independent arbitrary timing.

## 13. User-facing controls

### Explosion

- type, preset, scale, intensity, speed, start frame, duration, seed

### Components

- fireball, rising column, ground surge, dust, shockwave, debris, flash,
  heat distortion

### Simulation

- quality profile, resolution override, noise level, turbulence, cache
  directory, frame range

### Appearance

- fire temperature, fire color, smoke color, smoke density, blackbody
  strength, volume contrast

### Cinematic FX

- flash, camera shake, exposure impulse, heat distortion, ground
  illumination

## 14. UI layout

Main panel order:

1. Explosion
2. Components
3. Simulation
4. Appearance
5. Cinematic FX
6. Cache
7. Advanced

UX rules:

- Do not expose dozens of raw Mantaflow properties.
- Advanced options should be collapsed.
- Destructive operations should be visually separated.
- Bake buttons should show quality.
- Cache status should always be visible.
- Warnings should appear before expensive operations.

Artist-facing physical controls should include physical scale, reference energy
class, normalized intensity, event duration in seconds, and ambient conditions.
The UI should display units. Raw solver controls belong under Advanced.

## 15. Preset model

A preset should contain artistic defaults and engine hints.

```json
{
  "id": "large_ground",
  "label": "Large Ground Blast",
  "type": "LARGE",
  "defaults": {
    "scale": 1.0,
    "intensity": 1.0,
    "speed": 1.0
  },
  "components": {
    "fireball": true,
    "stem": true,
    "dust": true,
    "shockwave": true,
    "flash": true
  }
}
```

Raw Mantaflow settings can be attached later under an engine-specific section.

## 16. Blender 5.2 compatibility

The add-on targets Blender 5.2 and keeps Mantaflow RNA access centralized.

Verified API model:

- `FluidModifier.fluid_type` must be set to `DOMAIN` or `FLOW` before
  reading `domain_settings` or `flow_settings`.
- Gas controls such as `alpha`, `beta`, `vorticity`, `burning_rate`,
  `flame_smoke`, `flame_vorticity`, `flame_ignition`, and `flame_max_temp` are
  properties of `FluidDomainSettings`; there is no `gas_settings` object in the
  Blender 5.2 Python API.
- Flow controls such as `fuel_amount`, `temperature`, `density`,
  `surface_distance`, `velocity_coord`, `velocity_normal`, and
  `velocity_random` belong to `FluidFlowSettings`.
- Mantaflow flow and domain objects are real mesh objects.
- Baking uses `bpy.ops.fluid.bake_all()` after making the domain active.
- Freeing uses `bpy.ops.fluid.free_all()` after making the domain active.

### Runtime self-test

`blastfx/core/blender_api.py` creates temporary domain and flow meshes,
initializes their Fluid modifiers, checks the expected RNA attributes, and
removes the temporary objects. `Create Blast` runs this before modifying the
scene.

The runtime self-test also verifies every domain and flow RNA field used by the
builders, the `bpy.ops.fluid.bake_all()` / `free_all()` operators, and the
Principled Volume sockets required by the Cycles output material. Pure-Python
checks cannot replace running this audit inside the target Blender build.

### Asynchronous bake architecture

The Bake Simulation operator is non-blocking. It saves a temporary `.blend`
snapshot, launches the packaged `blastfx/core/blender_bake_worker.py` using
Blender's current `bpy.app.binary_path`, and polls a per-job atomic
`status.json` from a `bpy.app.timers` callback. The worker is the only
process that calls `bpy.ops.fluid.bake_all()`. No Python thread is used
because Blender data blocks and Mantaflow operations are not thread-safe.

The worker and main process share the already prepared cache generation, but
do not share Blender memory. Consequently, worker exit is not completion:
the main process validates the current generation's expected manifest, state
hash, frame range, and VDB/UNI output before writing `.blastfx_complete`.
Cancellation and worker failure leave the generation incomplete or partial.
The current UI supports one active job, live phase/elapsed-time reporting,
and cancellation; reliable Mantaflow frame percentages are intentionally not
fabricated. During a bake, the main process observes completed `.vdb`/`.uni`
frame files in the shared generation and reports the highest confirmed cache
frame. Until a frame file exists, progress remains unavailable. ETA is
calculated only after confirmed progress samples exist.

The worker's `.blend` is never merged back into the open scene. Only one bake
is supported at a time; Cancel Bake leaves the generation incomplete and
therefore not valid.

### Cache identity

Bake state is isolated per blast and uses an expected-state manifest plus a
completion marker. Every bake receives a new generation directory; old
VDB/UNI files are removed before preparation. A cache is reported as baked
only when the current generation has a matching state hash and Mantaflow
reports `has_cache_baked_data`/`has_cache_baked_noise`, or current-generation
VDB/UNI output exists after a successful bake.

The cache identity includes blast identity, explosion/preset settings,
physical values, speed and frame timing, seed, quality/effective resolution,
noise, turbulence, smoke/fire controls, component toggles, scene FPS, gravity,
unit scale, derived physics, and numerical Mantaflow configuration. Cosmetic
camera and appearance-only controls are excluded.

Mantaflow's public Blender 5.2 RNA does not expose a verified general-purpose
simulation seed used by this pipeline. The Blast FX seed is therefore part of
cache identity and procedural configuration, but deterministic solver noise
must remain a Blender-runtime validation item rather than being claimed from a
nonexistent RNA property.

`tools/blender_runtime_smoke_test.py` is the Blender-runtime-only integration
test. It passed in Blender 5.2.1: the minimal gas simulation baked
successfully, exposed `density_grid`, `temperature_grid`, `flame_grid`,
`heat_grid`, and `velocity_grid`, saved a Cycles PNG with
`max_rgb=0.662745` and `12288` non-background channel values, and freed the
simulation successfully.

### Domain envelope

Blender 5.2.1 runtime validation confirms the domain properties used by this
pipeline: `use_adaptive_domain`, `adapt_threshold`, `adapt_margin`,
`use_collision_border_bottom`, and the top/side collision-border properties.
Adaptive mode changes the active gas region inside a finite mesh; it does not
remove a finite top boundary. Blast FX therefore computes a deterministic
pre-bake envelope from the existing derived radius, velocity, gravity,
buoyancy, timeline, and numerical voxel size. The top and lateral borders are
open and the bottom border remains closed. Envelope bounds and boundary mode
are included in the existing cache state hash. The worker receives these
prepared domain dimensions from the scene snapshot and does not recalculate
them.

## 17. Future extension points

- Geometry Nodes debris
- custom emitter collections
- airburst presets
- multiple blasts in one controller
- renderer adapters
- asset-browser presets
- simulation version migration
- batch baking
- command-line rendering support
