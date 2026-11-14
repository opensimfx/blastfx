# Realism, Cinematic Look and Bake Speed — Findings and Plan

Status: research + diagnosis, 2026-11-14, branch `realism-and-bake-speed`.
Every claim below is marked **[measured]** (headless Blender 5.2.3 bake or API probe run for this
document), **[source]** (Blender source / manual), **[code]** (read in this repo), or
**[reference]** (external research; treat as a starting point, not truth).

Experiment scripts live outside the repo; the key one is reproduced in Appendix A.

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

**Phase A status (implemented, uncommitted):** with all three conversions in
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

## 3. Plan (in order)

**Phase A — Scale correctness (biggest realism win)**
1. Froude time scaling in `build_domain` (`time_scale = sqrt(S/S0)`, clamp 10, beta top-up
   beyond); author all velocities at S0. Remove the nuclear 12×/14× hacks.
2. Real-world sizes in presets; duration from diameter; explicit Shot Speed (slow-mo).
3. Resolution from voxels-per-radius, not a fixed number.
Acceptance: a 4 m and a 40 m blast match in domain-relative silhouette at Froude-scaled frames
(extend `tools/physics_validation.py`); bake_benchmark shows a frame-count drop on presets.

**Phase B — Shading**
4. Fire ramp/blackbody, radius-normalised density and emission, albedo floor, internal fire
   lights. Delete the Fresnel term.
Acceptance: side-by-side small/medium/nuclear renders at matching frames; no opaque blob and
no see-through haze.

**Phase C — Cinematic layer**
5. Fix exposure, glare type, compositor, heat haze (refraction), camera shake (noise, sound
   delay), flash timing/energy, sparks, debris material/speed, fast shockwave.

**Phase D — Speed workflow**
6. MODULAR cache (data then noise); Draft render settings; then guided upres as an experiment.
7. Optional "Instant" tier from a downloadable VDB library.

Retune profiles after A and B. Their current values were tuned around the scale bug and the
missing burst velocity (see CHANGELOG).

---

## Appendix A — Buoyancy probe (Blender 5.2.3, `-b --factory-startup`)

Domain: cube of side S, res 32, open borders, `alpha=0`, `beta=1`, no dissolve. Flow: icosphere
(radius 0.06·S) at 0.2 of the domain height, SMOKE, temperature 1, inflow frames 1–3.
Metric: density-weighted centroid height as a fraction of domain height, read from
`domain_settings.density_grid`. The Froude run sets `time_scale = sqrt(S/4)` and samples frames
scaled by the same factor.

## Sources

- Blender source: `intern/mantaflow/intern/strings/smoke_script.h`, `fluid_script.h`,
  `source/blender/blenkernel/intern/fluid.cc` (main branch, fetched 2026-11-14)
- Blender manual (bundled with the Blender MCP): fluid domain Settings, Cache, Guides, Noise
- Fireball correlations: https://www.aidic.it/cet/20/82/036.pdf ,
  https://www.icheme.org/media/25181/the-assessment-of-major-hazards-icheme-symposium-series-71-1982-15-lihou.pdf
- Miniature/high-speed practice: https://cinematography.net/edited-pages/Earth_Explosion_-_fps.htm
- Heat distortion via refraction shells: https://www.blendernation.com/2018/09/23/create-realistic-heat-distortions-in-blender/ ,
  https://blenderartists.org/t/fake-simulated-heat-distortion-in-blender/1282239
- Free CC0 VDBs: https://jangafx.com/software/embergen/download/free-vdb-animations
- Blender 5.0 volume grid nodes: https://developer.blender.org/docs/release_notes/5.0/geometry_nodes/
- Fire shading practice: https://sites.google.com/view/vdblabuserguide/user-interface/main-modules/shading ,
  https://www.blendernation.com/2024/03/29/two-tips-for-better-explosions-in-blender-initial-velocity-and-turbulence-quicktip-ft-khaos-add-on/
