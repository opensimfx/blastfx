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

### Phase A: scale-correct physics (Froude scaling)

Measured in Blender 5.2.3 (`docs/REALISM_PLAN.md`): Mantaflow divides buoyancy by the
domain size, so big blasts barely rose; `velocity_normal` is in grid units, so dust and
shock pushes changed with resolution; per-solver-time rates (burning, vorticity) ran faster
on bigger domains.

- New `core/froude.py`: every blast runs as a reference-sized model with
  `time_scale = playback x sqrt(S / 4 m)`; flow velocities, particle velocity factor,
  `velocity_normal` (grid units), burning rate, vorticity and dissolve are converted from
  real values. A 4 m and a 40 m blast now match within ~15% in plume height, spread, smoke
  mass and flame lifetime at Froude-scaled frames (the old code diverged 2-5x).
- Profiles are scale-free: velocities in `U = sqrt(gR)`, times in `T = sqrt(R/g)`, domain
  shape in R. Shot length no longer changes how fast the blast moves; smoke fade is a
  profile property, not half the shot.
- Domain is a fixed shape in fireball radii; resolution is automatic from voxels per
  radius (Draft 8 / Preview 14 / Final 24). Old presets had 4-10 voxels per radius in
  domains up to 62x the fireball.
- Presets are real-world sizes (4 m charge ... 80 m heavy burst) with explicit playback
  speed (slow motion). `Scale` is now "Fireball Size" (diameter, m), `Speed` is "Playback
  Speed". Presets no longer pin resolution (0 = auto).
- Very large blasts that exceed the time-scale limit get a warning with the buoyancy
  shortfall (nuclear presets).
- One planning function (`core/blast_plan.py`) replaces three copies of the
  derive/config/envelope sequence in create, rebuild, simulation and animation.
- Fix: repo-root JSON presets silently replaced factory presets with stale values
  (`large_ground.json` forced 24 s). Factory ids now win.
- Fix: Rebuild left an emitter active, so Bake / Rebuild right after failed with "Select a
  Blast FX controller". Rebuild also reports plan warnings now.
- Fix: `tools/physics_validation.py` imported from a stale hard-coded path.
- Profiles need visual retuning on top of this (expected; values were tuned around the
  scale bug).

### Phase B: shading and fire light

- Smoke extinction is normalised by fireball radius (`optical_depth` per profile), so a
  4 m and a 40 m blast render alike; before, small blasts were see-through haze and big
  ones opaque blobs.
- Fire colour comes from a Blackbody node fed by the flame grid mapped to a per-profile
  temperature range (white-hot core, orange body, red edges) instead of one flat colour.
- Fire emission follows Kirchhoff's law (extinction x brightness x flame^gamma): an
  optically thick core glows at the same radiance at any size and density. Per-metre
  emission had left dense fireballs as dim as the sky.
- Smoke albedo ramp spans the measured density range (0-3) and is darkened where flame
  burns (soot is black); dense smoke keeps ~0.04 albedo so the fire lights it. The volume
  Fresnel term (no surface normal in a volume) is gone.
- AgX compensation: under Blender's default AgX view the fire gets a hue/saturation grade
  and lower brightness, because AgX turned raw blackbody orange salmon-pink (measured
  against Filmic on the same bake). Other views get the raw colour.
- Fire light replaces the flash: a 1-2 frame detonation flash then the fire's glow over
  the measured fire lifetime (`fire_light_T`), energy proportional to R^2, colour by
  temperature. The old light ramped over 5% of the shot at 50 kW per metre and lasted
  35% of it, washing out every frame.
- The rising column starts once the fireball has lifted (`stem_delay_T`) at normal
  density; fed from frame 1 it rendered as a black chimney.

### Phase C: cinematic layer

- Fix: debris and sparks never rendered. Emitters were `hide_render`, which hides their
  particle instances too (measured); sparks used the HALO type, which Cycles does not
  draw; debris shards were sized twice (~1 cm on a 4 m blast) with a viewport-only colour.
  Emitters now hide via `show_instancer_for_render`, prototypes live in a view-layer-
  excluded collection, sparks are emissive blackbody instances, debris is charred and
  thrown at multiples of U with playback-scaled gravity.
- Fix: removing or rebuilding a blast now deletes its prototype collections instead of
  orphaning them (they piled up on every Rebuild).
- Shockwave: the flat dusty disc that crawled outward over most of the shot is replaced
  by a refraction ripple sweeping out at 343 m/s (at least 3 frames on screen), and the
  shock dust comes from an annulus with lift instead of a filled cylinder that stamped a
  dark pancake under the fireball.
- Heat haze is a refraction shell (Cycles volumes cannot refract) with animated noise,
  faded toward its silhouette, camera-only, hidden outside the fire's lifetime. The old
  "haze" was a grey Principled Volume fog ball.
- Camera shake: noise on rotation starting when the blast wave reaches the camera
  (distance / 343 m/s), amplitude by distance relative to fireball size, decaying over
  ~1 s of event time. The old shake was four Bezier keys drifting over 75% of the shot.
- Camera framing in fireball radii for every profile; the old radius rule parked the
  Large Ground camera ~2.4 R out, inside the smoke.
- Exposure reacts relative to the scene's own exposure (one frame +1 stop, a slight iris
  dip, recovery over ~1.5 T) instead of forcing +3 stops and ending at 0.
- Compositor: Bloom instead of the default Streaks, no hue shift, no second denoise
  without passes, and a scene with its own compositor tree is no longer wiped
  (`nodes.clear()` ran on whatever tree the scene had). Built with "Exposure & Bloom".
- Create no longer forces `film_transparent`, which hid the artist's world.
- Labels: "Fire Light", "Exposure & Bloom".

### Smoke banding

- Fix: horizontal bands in rising smoke (Medium, Large Ground). Bisected with renders and
  grid slices: the simulation's own density had no layers, and denoising, samples and
  volume step size did not change them; the adaptive domain did. Its moving box clips
  rising smoke every step (margins 4 and 12 banded, 20 mostly not), and inside the tight
  Froude envelope it saved little time (Draft medium: margin 4 38 s, off 48 s, margin 20
  53 s). Adaptive domain is now off by default (`SimulationConfig.use_adaptive_domain`).
- The rising column is mostly buoyant now (`stem_speed_U` 0.25-0.5, was 1.0-2.2): an
  imposed jet shed regular sheets (strong at 1.2 U, faint at 0.5 U, none without a jet).

### Phase D: bake speed (tiers)

- Measured on medium at Preview (first 46 frames): 257-322 s before; the noise pass was
  ~50% of the cost, CFL 4 saved ~20-30%, max substeps 3 ~20%. Preview now skips the
  noise pass and Draft and Preview use CFL 4 (`TIER_SOLVER`); Final keeps noise and
  CFL 2. Same 46 frames: 104 s, same shape and timing, smoother billows without fine
  soot detail. Full medium Preview (193 frames): 242 s, where 91 frames took 470 s.
- Fix: Final simulated a weaker explosion than Draft. Mantaflow sizes particle fuel
  injection in cells, so each burst particle injected ~1/27 the volume at Final and the
  tier's 4x particle count did not make it up (small, frame 11: smoke -23%, flame -33%;
  fire gone by 1 T at Final). Each particle now has a fixed radius in metres, shrunk as the
  tier adds particles, so injected volume matches Draft: tiers now agree within ~4-7%.
- Shock dust: lighter (0.6x) with more lift (0.8 U), and the emitter ring now sweeps out
  from inside the fireball over `shock_sweep_T` instead of stamping the whole annulus in
  one frame; the flat glowing disc under the fireball became billowing dust.

### Tuning (Preview review of every preset)

- Large Ground: the whole cloud glowed peach through 2 T (burning 0.22, fuel 4.5); now
  burning 0.45, fuel 3.5, fire light 3 T, so it goes dark with pockets of fire.
- Heavy: the "long-burning" burst burned out by 2 T with pale smoke (burning 1.2); now
  burning 0.4, more soot, darker smoke ramp.
- Nuclear: the domain shrinks to 3.5 R per side (was 5.4 R, 932 m), cutting the buoyancy
  shortfall from ~37% to ~9% so the cloud rises; fuel 3.5 (the core stayed white past
  2 T) and less random burst spread (fewer spikes). The domain top is closed for Nuclear
  (`ceiling`), so the plume spreads under it like a cap at its stabilisation altitude
  instead of being sliced off by the open border; fire range 1500-5000 K at brightness 35
  (was 1800-6500 K at 60). Still open: the fireball stays bright for over 2 T and the cap
  is flattish.

### UI

- Sidebar rebuilt to the shared OpenSimFX UI conventions (`docs/UI_STYLE.md`, identical in
  all four add-ons): preset dropdown with wrapped description, large Create button, the
  selected blast's Rebuild / Duplicate with Remove separated, then Explosion, Components,
  Look, Cache and Bake, Readout, Diagnostics and Preset Files sub-panels.
- Nuclear yield and Rapatronic Skin were missing from the UI; both show for Nuclear.
- New Readout: fireball diameter, T, event length, frames, solver time scale, resolution,
  voxels per radius, voxel size and noise, from the same plan Create uses; plan warnings
  (buoyancy shortfall) show in Readout and Diagnostics.
- Cache and Bake shows state, frames, a progress bar, elapsed/remaining time and failure
  messages; Draft/Preview explain that they skip the noise pass.
- Duration displays in seconds; "Resolution Override" is "Resolution" (0 = automatic).
- Removed the stale "Noise is enabled for Draft quality" warning (tiers ignore it).
- The free-text preset field and the list of preset buttons are replaced by the dropdown;
  the unused Reference Energy field is no longer shown.

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
