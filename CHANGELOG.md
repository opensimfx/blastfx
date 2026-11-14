# Changelog

## Unreleased (branch `realism-and-bake-speed`)

Realism and bake-time work. Plan: Phase 0 measure, Phase 1 bugs and speed, then shading, then nuclear.

- Fix: burst particles never received the profile's burst speed. `burst_normal_velocity` and
  `burst_random_velocity` were computed but not applied, so every blast left at Blender's default
  particle speed. They now set `normal_factor` and `factor_random`. All profiles were look-tuned
  without this, so expect to retune them.
- Fix: the lower-cap flip was applied to both burst caps; it now applies to the lower cap only.
- Fix: the ground collider added the blast's height twice (`ground_top_z` is already a world Z),
  misplacing it for any blast above Z=0.
- Bake cost is now set per quality tier in one table (`TIER_SOLVER` in
  `simulation/physical_config.py`): Draft skips the noise pass and uses Blender's default-like
  adaptive-domain and timestep settings; Final keeps full fidelity. Values are starting points
  until timed.
- New: bake metrics. Each worker bake writes `.blastfx_metrics.json` into the cache (wall time,
  peak memory, cache bytes, per-phase span, solver settings), outside `job/` so recovery keeps it.
- New: `tools/bake_benchmark.py` times a bake for a preset and tier in desktop Blender.

## 0.2.0-beta2 (2026-10-19)

Nuclear support on top of the beta1 rework.

- New Nuclear Burst type: the `Yield (kt)` property (kilotons) drives the
  fireball diameter via the cube-root law compressed 8x (15 kt ≈ 173 m),
  overriding the manual scale at Create and Rebuild.
- Two presets: Nuclear Air Burst (14 s; place the 3D cursor at burst
  height — the ground collider drops to the envelope bottom) and Nuclear
  Ground Burst (16 s; full fallout column, dust surge and debris). Both
  render at resolution 256 / noise 2 and share the Trinity-style profile
  (buried 5-second fireball, shock factor ~4, inside the 5-psi relation).
- Nuclear double flash: the flash light dips (shock front overtakes the
  fireball) and re-brightens before the burn decay — the bhangmeter
  signature.
- Rapatronic skin: shader-only speck shell (two Voronoi masks over a
  transparent icosphere) keyed visible for the first 6 frames of any
  nuclear fireball, re-creating the classic early-fireball mottled look;
  new `Rapatronic Skin` toggle, on by default in the nuclear presets.
- Fallout-grey smoke shading (near-white incandescent core) for nuclear
  types; tests 44 green.
- Fix: nuclear builds ignored the yield scale in the animation rig, leaving
  the add-on camera 2.6 m from a 172 m fireball (and the flash, shockwave
  ring and heat sphere metre-scale). Animation config now uses the effective
  nuclear scale.
- Fix: long timelines starved their smoke column — the stem fed for 2 s only
  and a cold dust sheet ran for the full shot, flattening the blast into a
  pancake. Stems are now wider/hotter, fed for up to 4 s (a quarter of the
  timeline), and the nuclear dust surge is shorter and lighter.

## 0.2.0-beta1 (2026-10-19)

First beta of the cinematic simulation rework, aligned with the Mantaflow
research catalogue (`examples/before/` vs `examples/after/` turntables).

- Particle-driven fireball burst: equator-split hemisphere emitters feed the
  Mantaflow domain directly (particle-sourced flows replace the old mesh-inflow
  fireball), with deterministic per-variant seeds and per-profile burst
  windows; fireball visibility now scales with blast size (~2 s small,
  ~3 s fuel-scale, ~5 s large presets).
- Shading rebuilt per profile: density ColorRamp (near-black cores, light
  wisps), Fresnel edge lightening, and the Mantaflow flame grid driving
  volume emission instead of the temperature-x400 blackbody hack; unused
  fire/dust materials removed.
- Physics in the expert-researched bands: domain vorticity cap 0.2,
  profile-derived flame ignition temperature, timeline-derived smoke dissolve.
- Ground interaction: Mantaflow ground effector with particle COLLISION
  deflection, cool negative-temperature dust hugging the floor, and a
  keyframed expanding dust donut ring.
- Presets rebased: small/medium/large/large-derived timings inside the
  100-200 frame research band, draft-quality resolution pre-scaling, and the
  long-burning Heavy Ground Burst preset (renamed from MOAB) with its own
  profile (burst windows 36/40, debris on).
- Hero burst counts scale with render quality (up to 9,600 particles FINAL).
- Background bake queue with live per-frame verify + recoverable cache
  generations; core/render settings applied at Create; glass/compositing
  chain ends in NodeGroupOutput (Blender 5.2 API).
- dist zip is versioned from the controller's stored version.

Earlier milestones are documented in `docs/HISTORY.md`.
