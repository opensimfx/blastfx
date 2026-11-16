# Validation

What was measured while making BlastFX realistic and fast to bake: the findings, the plan they led to and its
status. (Formerly `REALISM_PLAN.md`.)

## Realism, cinematic look and bake speed: findings and plan

Status: research and diagnosis, 2026-11-14; the plan is complete except where marked.
Every claim below is marked **[measured]** (headless Blender 5.2.3 bake or API probe run for this
document), **[source]** (Blender source / manual), **[code]** (read in this repo), or
**[reference]** (external research; treat as a starting point, not truth).

The key experiment is reproduced in Appendix A.

---

## 1. Why BlastFX explosions don't look real yet

### 1.1 Mantaflow buoyancy is not scale-correct — big blasts freeze  **[measured] [source]**

`intern/mantaflow/intern/strings/smoke_script.h` divides both buoyancy coefficients by the
domain's longest side in metres:

```
buoyancy_heat = BUOYANCY_BETA / FLUID_DOMAIN_SIZE
```

Gravity *is* converted to cells correctly, so buoyant acceleration in metres falls as 1/size.
A pure-buoyancy probe (32 res, beta 1, flow temperature 1, 16 frames @ 24 fps):

| Domain size | 1 m | 2 m | 4 m | 8 m | 16 m | 40 m | 100 m |
|---|---|---|---|---|---|---|---|
| Rise (metres) | 0.29 | 0.37 | 0.38 | 0.22 | 0.10 | 0.04 | 0.01 |

Real buoyant plumes rise *faster* when bigger (velocity ~ sqrt(g·R)). Mantaflow is tuned for
~1–4 m domains and freezes beyond that. This is the root cause of the NUCLEAR profile's
`stem_velocity_factor=12` and `burst_normal_velocity=14` workarounds, and of the "slow-motion
large explosion" look.

**Fix (verified): Froude time scaling.** Set `domain.time_scale = sqrt(S / S0)` with S0 = 4 m,
and author velocities as if the blast were S0-sized. A 40 m domain at `time_scale=3.162`
rose 0.0968 domain-heights over Froude-scaled frames 25→76 against 0.0945 for the 4 m
reference over frames 8→24. Without the fix it rose 0.0106 (9× too slow). **[measured]**

Limits: `time_scale` hard max is 10 **[measured]**, so this covers domains up to ~400 m with
S0 = 4 m. Nuclear envelopes (~930 m) need S0 ≈ 10 m, or the rest made up with `beta` (max 5).
A higher time scale also raises CFL substeps, so big bakes get somewhat slower per frame.

Also checked and **not** a problem: particle and mesh initial velocities (`velocity_coord`,
particle sources) are consistent across resolution (32 vs 64) and domain size (4 vs 40 m).
**[measured]**

Found during Phase A **[measured]**:

- `velocity_normal` is **not** m/s. It is added raw to the grid velocity
  (`fluid.cc`), so its push fell ~3× from res 32 to 64 and doubled with domain size.
  `vn = v · res / (2.5 · size)` matched `velocity_coord` exactly. The dust surge and
  shock ring used it, so Draft and Final simulated different events.
- Per-solver-time rates (burning rate, vorticity, flame vorticity) must be divided by the
  solver time per T, which grows with size. Without that, a 40 m fireball burned out ~10×
  sooner (in T) than a 4 m one.

**Phase A status (committed, `38b9d61`):** with all three conversions in
`core/froude.py`, a 4 m and a 40 m `small` blast agree within ~5–15% at Froude-scaled
frames on plume height, lateral spread, smoke mass and flame lifetime. The old code
differed 2–5× on the same test.

### 1.2 Presets are 1 m blasts played over 5–16 s  **[code] [reference]**

Every non-nuclear preset uses `scale = 1.0` (0.5 m radius) with 5–16 s durations. Empirical
fireball correlations (Roberts / Lihou & Maund, BLEVE literature) give
`D ≈ 5.8·m^(1/3)` metres and `t ≈ 0.45·m^(1/3)` seconds (m = fuel kg), i.e.
**fireball lifetime ≈ 0.08 s per metre of diameter** (large-mass regime differs). A 1 m
fireball should be gone in about 0.1 s; a 10 m car fireball in about 0.8 s; a 50 m depot
fireball in about 4 s. Filmmakers shoot practical explosions at 96–120 fps and higher to make
them read big, and smaller miniatures need higher frame rates (CML thread).

**Fix:** presets carry a real-world diameter. Duration derives from diameter (fireball phase)
plus a smoke tail. A separate **Shot speed / slow-motion** control (1×, 2×, 4×) replaces
`speed`, so slow motion is an explicit cinematic choice rather than an accident of scale.

### 1.3 Volume shading  **[code]**

| Problem | Where | Effect |
|---|---|---|
| Fire is one flat colour (`flame_color`) × `flame*5` | `materials/volume.py` | No white-hot core → orange → deep-red edge gradient; the fire looks like orange paint |
| Density per metre is constant (`density_multiplier` 0.22–0.35) | `explosion_profile.SHADING` | Optical depth ∝ size: 1 m blasts are see-through haze, 170 m nuclear is an opaque black blob (see `examples/burst_probe/nuclear_user_f136.png`) |
| Emission per metre is constant | same | Large fireballs are blown out, small ones dim |
| Fresnel from Geometry Normal | `volume.py` | Volumes have no surface normal; this term is noise, not edge lightening |
| Smoke albedo ramps to ~0.01 | `SHADING` ramps | Dense smoke absorbs everything, so the fire can't light it and smoke renders flat black |
| Blackbody path wired but intensity 0 | `volume.py` | The physically right colour source sits unused |

**Fix:** (a) emission colour from a flame/temperature ColorRamp (white-yellow → orange → red →
dark) or Blackbody, with strength on a power curve; (b) normalise density and emission by
characteristic radius, so a profile sets a *target optical depth* (e.g. τ ≈ 4 for soot) and
looks the same at any scale; (c) raise smoke albedo to about 0.05–0.15 so the fire's light
scatters in the smoke; (d) fill the fireball interior with 1–3 point lights keyed to the burst
timeline. This is the cheap, standard way to get smoke lit from within; volume-to-volume
emission alone is noisy.

### 1.4 Cinematic layer bugs  **[code] [measured where noted]**

| Component | Problem | Fix |
|---|---|---|
| Exposure impulse | Keys `view_settings.exposure` to **+3 stops**, holds +2 until 15% of the shot, ends at 0 whatever the user had | Short flash (2–4 frames) then a slight *under*-exposure recovery, like a camera's auto-exposure reacting to the flash. Store and restore the user's exposure |
| Compositor glare | Glare `Type` defaults to **Streaks** **[measured]**; `Size` set to 8 on a 0–1 socket **[measured]** | Use `Bloom` or `Fog Glow`, size about 0.6–0.8 |
| Compositor | Hue 0.52 shift + Denoise node with no Albedo/Normal passes after render-time denoise | Drop the double denoise; grade with Color Balance; build it whenever cinematic FX is on, not only with heat distortion |
| Heat distortion | A Principled **Volume** sphere: grey fog, not refraction (Cycles volumes can't refract) | Refraction BSDF shell, IOR about 1.005–1.02, animated noise into Normal, camera-only ray visibility, mixed with Transparent |
| Camera shake | 4 Bezier keys over 75% of the shot: a slow drift, not a shake | Noise F-curve modifier with decaying strength, starting at **shock arrival = distance / 343 m/s** |
| Flash | Rise takes 5% of the shot (0.25 s for a 5 s blast); energy ∝ radius although light falls off ∝ 1/r² | Rise in 1–2 frames, decay with fire burn; energy ∝ r² |
| Sparks | `render_type="HALO"` (legacy Blender Internal), so nothing renders in Cycles | Instance small emissive objects (or Geometry Nodes points) with motion blur |
| Debris | `diffuse_color` only sets the viewport colour; new 5.2 materials are node-based **[measured]**, so shards render default 0.8 grey. Speed fixed at 2 m/s at every scale | Charred node material; speed from characteristic velocity; optional smoke trails per shard |
| Shockwave ring | Flat disc expanding linearly over seconds (≈1 m/s at 1 m scale); real shocks travel ≥343 m/s | Fast ring: dust kick-up (ring flow on a radius animated at shock speed), plus a short refraction ring and an optional Wilson condensation cloud |
| Render | `film_transparent=True` hides the sky; world volume scatter over the whole scene slows every render | Keep the sky visible; get depth with a Mist pass or local fog |

---

## 2. Bake speed

Current cost drivers **[code]**: `cache_type="ALL"` (any change rebakes everything); fixed res
128–256 across an envelope 6–12× the fireball radius; durations 5–16 s; FINAL ×1.5 res.

| Lever | Expected gain | Evidence / note |
|---|---|---|
| **Real durations** (§1.2) | 2–5× fewer frames on small/medium presets | Frame count is linear in cost |
| **Resolution from voxels-per-fireball** (e.g. 40–60 across the radius) instead of a fixed 256 across the envelope | Large, roughly cubic | Today 256 over a 12× envelope gives ~20 voxels per radius; adaptive domain helps but the envelope still sets voxel size |
| **MODULAR cache**: bake data once, noise separately | Noise/appearance iteration with no resim | Manual: Bake Data / Bake Noise are separate, resumable **[source]** |
| **Guided upres**: low-res domain bakes first, high-res domain guided by it | Draft motion carries into Final | Manual: a guide domain "may have a different resolution" **[source]**. Fidelity untested |
| Draft render: `volume_step_rate` 2–4, fewer volume bounces | Faster preview renders | Standard Cycles trade-off |
| VDB half precision | None: already the default ("16") | **[measured]** |
| **Zero-bake tier**: retimed VDB library (Volume object sequence) | Instant | JangaFX EmberGen packs are CC0, but 0.6–6.6 GB each, so download on demand, not bundled |
| Blender 5 GN volume grids (Advect Grid) procedural preview | Instant, lower fidelity | Experimental; R&D only |

The branch's `tools/bake_benchmark.py` + `.blastfx_metrics.json` should gate every change:
measure before and after on the same preset and tier.

---

## 3. Plan and status

Commits on `realism-and-bake-speed` (see CHANGELOG for detail and measurements).

| Phase | Status | Commit |
|---|---|---|
| A. Scale correctness: Froude time scale, `velocity_normal` and rate conversions, real-size presets, auto resolution | Done; 4 m vs 40 m agree within ~5-15% (old code 2-5x apart) | `38b9d61` |
| B. Shading: radius-normalised smoke, blackbody fire with Kirchhoff emission, soot albedo, AgX grade, fire light | Done; 4 m and 40 m render alike | `6e4dd01` |
| C. Cinematic layer: debris/sparks that render, refraction shockwave and haze, sound-delayed shake, relative exposure, safe compositor, R-based camera | Done | `b6e2c72` |
| Banding: adaptive domain off by default, buoyant column | Done; clean at Preview | `1ae6ebb` |
| D1. Tier cost: Preview without noise, CFL 4 for Draft/Preview | Done; Preview ~2.5x faster | `b58ca62` |
| D2. Split bake (MODULAR cache: motion, then noise) | Feasible but deferred; see below | - |
| D3. Instant tier from a downloadable CC0 VDB library | Not started | - |

### D2 findings (Blender 5.2.3, headless tests, 2026-11-15)

A split bake only works as a chain of worker processes, under conditions that make it
costly for a narrow benefit (re-baking only the noise pass after changing Noise):

- Noise-only baking in a fresh process writes empty noise grids (~1.4 KB vs ~36 KB files),
  even with the stage-1 worker's .blend reopened: the noise solver needs the base velocity
  state, which a normal data bake does not keep on disk.
- With `cache_resumable` on in stage 1, a second process that reopens stage 1's own .blend
  can change `noise_scale`, keep the data and bake real noise; the main scene (ALL or
  MODULAR, configured before the files arrived) then reads it. Resumable data is ~3x larger
  on disk; the manual advises against it at high resolution.
- Configuring a domain (or switching it to MODULAR) while cache files exist wipes them, so
  Rebuild would have to stash and restore files; the stage-1 .blend must survive recovery,
  which today deletes job folders on load; and cache identity needs separate data and noise
  hashes.
- A data-only MODULAR cache with noise enabled renders nothing, so "motion only" Final
  bakes would also need the noise switched off for viewing.

The Preview speed-up (no noise, CFL 4) delivered most of the iteration-time win; D2 stays
deferred unless re-baking noise becomes a frequent workflow.

Open items:

- Profiles need retuning by eye at Preview/Final; values were set during A-C at Draft.
- Nuclear exceeds the time-scale limit (10): buoyancy ~9% short (647 m domain), warned in the UI.
  The Nuclear look (spiky oversized fireball, white past 2 T, flat cap) was retuned on
  2026-11-15; see the CHANGELOG.
- Faint stripes next to the column emitter at Draft (cone only 2-3 cells wide); gone at
  Preview.
- Under AgX the fire is somewhat pastel; Filmic shows the fuller colour.

### Final bakes of every preset (Blender 5.2.3, 2026-11-16)

Every factory preset baked at Final quality at its full size, then rendered with Cycles at 25% and 85% of the
shot **[measured]**. Desktop Blender 5.2.3, `-b --factory-startup`, Apple M4 with 16 GB of memory, CPU only,
one bake at a time.

| Preset | Fireball R | Domain (m) | Resolution | Frames | Bake time |
|---|---|---|---|---|---|
| Small | 2 m | 16 x 16 x 14 | 192 | 169 | 14 min |
| Medium | 5 m | 45 x 45 x 43 | 216 | 193 | 64 min |
| Large | 10 m | 90 x 90 x 85 | 216 | 217 | 66 min |
| Large Ground | 20 m | 200 x 200 x 220 | 264 | 241 | 2 h 9 min |
| Heavy | 40 m | 440 x 440 x 480 | 288 | 289 | 3 h 24 min |
| Nuclear Airburst | 86 m | 604 x 604 x 647 | 180 | 337 | 39 min |
| Nuclear Ground Burst | 86 m | 604 x 604 x 647 | 180 | 385 | 49 min |

All seven baked and rendered with no errors, and each shows the same event as its Draft bake: same burst, column,
ground surge and cap timing. Smoke from Small has mostly dispersed by 85% of the shot at both Draft and Final.
Heavy's bake is the longest; a 288-resolution domain on a laptop CPU takes a few hours, so bake it overnight or
use Preview (no noise pass) to judge the shot first.

---

## Appendix A — Buoyancy probe (Blender 5.2.3, `-b --factory-startup`)

Domain: cube of side S, res 32, open borders, `alpha=0`, `beta=1`, no dissolve. Flow: icosphere
(radius 0.06·S) at 0.2 of the domain height, SMOKE, temperature 1, inflow frames 1–3.
Metric: density-weighted centroid height as a fraction of domain height, read from
`domain_settings.density_grid`. The Froude run sets `time_scale = sqrt(S/4)` and samples frames
scaled by the same factor.

Sources: [REFERENCES.md](REFERENCES.md).
