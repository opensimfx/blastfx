# Blast FX Physics

## Objective

Blast FX produces visually credible explosions by deriving secondary effects from a coherent physical parameter model rather than independently animating every visual element.

The add-on is a **visual simulation system for Blender**. It is not an engineering tool for predicting real explosive effects, weapon performance, or real-world blast damage.

The physics layer is designed around:

- SI units
- dimensional consistency
- conservation-aware procedural controls
- scale-aware simulation
- physically plausible timing relationships
- empirical/artistic calibration where Blender/Mantaflow does not directly model the phenomenon

## Physics pipeline

```text
User Intent
    |
    v
Physical Configuration
    |
    +-- Scale
    +-- Reference Energy Class
    +-- Ambient Conditions
    +-- Gravity
    +-- Medium
    +-- Initial Conditions
    |
    v
Derived Physical Quantities
    |
    +-- Characteristic length
    +-- Characteristic time
    +-- Expansion velocity
    +-- Pressure / density ratios
    +-- Temperature proxy
    +-- Buoyancy strength
    +-- Turbulence scale
    |
    v
Simulation Configuration
    |
    +-- Gas domain
    +-- Temperature
    +-- Fuel / reaction proxy
    +-- Buoyancy
    +-- Vorticity
    +-- Dissipation
    +-- Inflow velocity
    |
    v
Secondary FX
    |
    +-- Shockwave representation
    +-- Dust
    +-- Debris
    +-- Flash
    +-- Heat haze
    +-- Lighting
```

## Unit system

Internally use SI units wherever Blender's unit configuration permits:

- distance: metres
- time: seconds
- mass: kilograms
- velocity: metres/second
- acceleration: metres/second²
- temperature: kelvin
- pressure: pascals
- density: kilograms/m³

The UI can expose artist-friendly controls, but the engine converts them into SI quantities.

## Blender frame conversion

The engine must explicitly convert:

```text
simulation_seconds
        |
        v
scene FPS
        |
        v
Blender frame number
```

Never assume 24 FPS.

```python
frame = start_frame + seconds * scene.render.fps / scene.render.fps_base
```

## Scale handling

Explosion size must not simply scale mesh dimensions.

When scale changes, the engine derives corresponding:

- domain size
- voxel size
- emitter dimensions
- characteristic velocity
- simulation duration
- buoyancy length scale
- turbulence scale
- shockwave radius
- light falloff
- camera impulse distance

The goal is to preserve dimensionless behavior across scale changes.

## Dimensionless controls

Where practical, use dimensionless ratios:

- Reynolds-like turbulence control
- buoyancy-to-inertia ratio
- expansion ratio
- normalized temperature
- normalized density
- normalized time

These are implementation controls, not claims that Mantaflow is solving a complete real-world combustion model.

## Physical timing

The explosion has internally coherent phases:

```text
t0
|
+-- initiation / flash
+-- rapid expansion
+-- shock-front representation
+-- fireball growth
+-- buoyant rise
+-- turbulent mixing
+-- cooling / smoke formation
+-- secondary plume evolution
```

Do not independently keyframe each phase with arbitrary unrelated timing.

## Conservation-aware design

Procedural emitters should avoid:

- unexplained energy appearing after the initial event
- velocity discontinuities without a source
- arbitrary temperature spikes
- density changes that have no source/sink
- infinite smoke production
- shockwaves that continue accelerating forever

Every major quantity should have an identified source, sink, or transfer.

## Realism policy

Blast FX uses a hierarchy of truth.

1. **Physical truth** — use actual physical units and relationships wherever Blender's simulation stack supports them.
2. **Solver truth** — respect what Mantaflow actually solves. Do not describe a visual proxy as a full physical solution.
3. **Empirical approximation** — for effects outside the solver, use documented approximation functions with named parameters.
4. **Artistic override** — artistic controls may override derived values, but overrides must be explicit and marked as artistic.

### No fake precision

Do not expose values such as "real pressure = X" unless the engine actually computes that quantity under a validated model.

Use names such as:

- `reference_energy_class`
- `normalized_intensity`
- `expansion_velocity`
- `temperature_proxy`

rather than misleading engineering claims.

### Realism tiers

**Tier A — Physically coherent:** SI units, gravity, density, temperature, velocity, pressure proxies, scale-aware timing, physically coherent phase relationships.

**Tier B — Physically informed approximation:** empirical approximations for phenomena not directly represented by the chosen Blender solver — visible shock front, radiation flash, heat haze, secondary dust surge, camera response.

**Tier C — Cinematic augmentation:** optional effects that deliberately depart from physical simulation — exaggerated flash, stylized debris, additional smoke, camera shake, exposure impulse.

The UI should clearly identify Tier C controls.

### Reproducibility

Every generated blast stores:

- add-on version
- preset version
- random seed
- physical configuration hash
- simulation quality profile
- Blender version
- scene FPS
- unit scale

This makes a result reproducible and debuggable.

## Preset profiles

Blast FX uses a deterministic physically informed profile for each explosion type. A profile is simulation data, not a claim of engineering-scale physical truth. Its values control source topology, combustion, buoyancy, smoke persistence, timing offsets, and camera framing.

- **Small Blast** uses a compact source, short emission, strong outward velocity, limited turbulence, and short-lived secondary effects.
- **Fuel / Vehicle** uses a larger fuel-rich source, longer emission, lower burning rate, rolling turbulence, and persistent soot.
- **Large Ground Blast** (`large_ground`) uses the LARGE profile: a large hot source, stronger buoyant rise, a broad ground-fed surge and delayed dust behavior, and long-persistent smoke. It is intentionally not a yield, damage, or fallout model.

All profile fields are serialized into cache identity and contribute to the deterministic domain envelope. Consequently, changing a source, combustion, timing, or morphology control cannot reuse an incompatible bake.

## Mantaflow mapping (0.2.0 calibration)

How the profile fields land in solver controls, benchmarked against researched expert workflows (`BLENDER_EXPLOSION_RESEARCH.md`) and calibrated with headless bake probes (`examples/burst_probe/`):

- **Fuel injection**: one 2-5 frame burst of fast, short-lived particles
  (`simulation/burst.py`) feeding a PARTICLES flow — no continuous mesh
  inflow for the fireball. Injection length is `min(5, fps*source_duration*0.35)`
  with per-profile overrides; per-variant particle seeds come from the artist
  seed so each blast is a reproducible, non-identical sibling.
- **Vorticity**: expert ceiling 0.2 (froth above). Artist turbulence maps as
  `clamp(turbulence * profile_scale * 0.12, 0, 0.2)` — 1.0 lands mid-band.
- **Flow heat**: burst flow temperature is profile flow heat
  (GROUND 1.0 / FUEL 0.85-1.0) scaled by the artist's temperature factor.
  Calibrated against bake matrix evidence; the researched 0.05 figure applies
  to tall continuous inflows, not one-frame bursts.
- **Buoyancy**: heat buoyancy (beta) 2.2-3.1 per profile, density buoyancy
  1.0-1.3; calibrated so fireballs rise through their own smoke instead of
  stalling.
- **Dissolve**: smoke dissolves across the second half of the timeline
  (`timeline * fps * 0.5`, minimum 12 frames), so the plume lingers through
  the last hero frame instead of vanishing.
- **Ground interaction**: thin-cube collision effector at ground level; dust
  emits with negative initial temperature (-2.0 to -2.5) so the base surge
  hugs the floor instead of launching; debris particles fall onto the ground
  via a plain COLLISION modifier.
- **Fire rendering**: the Mantaflow `flame` grid drives emission strength
  (multiplier ~5) through the domain's volume material; smoke color/density
  runs through a per-profile ColorRamp with Fresnel edge lightening. The
  temperature blackbody path stays wired but off by default.
- **Burst count**: profile counts describe the interactive DRAFT bake;
  PREVIEW doubles and FINAL quadruples them so hero-quality large blasts
  reach the researched 8-10k particle band.

## Large-blast scope

The LARGE profile (the `large_ground` preset) is a **visual representation** of a large-scale atmospheric blast.

It models visual phenomena such as:

- intense initial flash
- rapidly expanding hot volume
- buoyant rising column
- ground-level dust/surge
- turbulent mixing
- secondary smoke evolution

The system must not expose or implement engineering calculations intended to determine real weapon yield, damage radius, casualty radius, structural overpressure, radiation dose, or weapon optimization.

Those quantities are outside the add-on's scope.

## Validation

The physics validator flags:

- non-SI scene units
- extreme scale ratios
- sub-frame event durations
- unstable voxel size
- unreasonable domain aspect ratios
- negative physical values
- incompatible frame ranges
- insufficient resolution for selected scale
- final-quality simulations with preview settings

Warnings should be actionable.

## Reference behavior tests

Every physics model should eventually have automated regression tests for:

1. doubling scale changes domain dimensions consistently
2. changing FPS does not change physical duration
3. changing seed changes turbulence but not physical base parameters
4. increasing intensity changes derived quantities through the defined model
5. disabled visual FX do not change simulation state
6. preview/final profiles preserve physical parameters while changing numerical quality
