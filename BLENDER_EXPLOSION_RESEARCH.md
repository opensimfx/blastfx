# Realistic Blender Explosion Simulations — Research Notes

> Compiled 2026-10-19 via web research (Firecrawl) of expert tutorials, official
> Blender documentation, and community threads. Focus: smoke, flames, particles
> (Mantaflow + built-in physics particles), **geometry/simulation nodes**
> workflows, and **compositor finishing**. Blender 4.x–5.x.

**Core thesis (CrossMind Studio):**
*"All that matters is a quick burst of particles — spend time getting the
initial burst right."*

An explosion is not one simulation. It is a one-frame fuel burst pushed outward
by particles, lifted by buoyancy, broken up by imperfect emitters, and finished
in shading + camera work.

---

## 1. The Particle Burst — the #1 Realism Factor

Explosion motion = **buoyancy (Density + Heat)** lifting smoke + **particle
Initial Velocity** bursting outward. Zero both and you get a standing blob; too
much buoyancy makes it drift like a campfire.

### Emitter setup (Paweł Chądzyński)

- Model a **dome/hemisphere** emission mesh, separate into an **upper and lower
  half** → two flow objects. **Two particle systems** is what produces the
  classic mushroom shape.
- **Apply scale** (Ctrl+A) on everything — emitters AND the domain.
- Edit particle systems:
  - Count **1,000–2,000** (hero shots up to **50,000** — CrossMind)
  - Frame Start **~10** / End **14–15** (smoke lingers; debris dies early)
  - Lifetime **~5–7**
  - Normal velocity **4–6**, Randomize **3–6**, ±5 Z bias for upward push
  - **Gravity OFF**
- If particles fall instead of fly: normals are flipped → Edit Mode, select all
  (A), **Shift+N** to recalculate.
- **Flow source = Particle System, Initial Velocity ON** — every source calls
  this the single biggest difference.
- Raise **Sampling Substeps (2–3)** because the flow moves fast.

### One-frame injection (CrossMind — the timing trick)

Keyframe the flow object's **Use Flow** ON on frame 2, OFF on frame 3.
A real explosion injects fuel in a fraction of a frame; continuous emission
looks like a smoker, not a blast.

Typical 24 fps timeline of a real blast:

| Phase | Frames |
|---|---|
| White flash | 1–2 |
| Fireball | 2–10 |
| Mushroom rise | 10–40 |
| Smoke linger | 100+ |

### Kill the symmetry — this is where realism lives

- Duplicate emitter systems **rotated around Z**; add ±Y velocity to a second
  system; throw rotated cubes/planes in as extra emitters so the blast is
  **oval with arms** instead of a perfect ball (Iridesium).
- Real explosions = **one big blast + several smaller inner blasts**.
- Break the simulation itself: Flow → Advanced → **Use Texture** with a Clouds
  texture, noise basis **Voronoi F1**, scale ~10, depth 2 → patchy emission.
- Different particle **seeds** = a free library of hundreds of variations.
- Animate emission to bite: Surface **0.0** / Volume **1.0**, strength keyframed
  **~1.5 → 0 by frame ~13**, density keyframed to **~0.1** to slow the rise
  (CG Geek).

---

## 2. Domain & Simulation Settings

- **Real-world scale matters**: ~2 m cube ≈ medium explosion. A 10 m
  "explosion" behaves like slow lava.
- Type: **Gas**.
- Resolution Divisions: **128** base, **192** for close-ups.
- **Vorticity 0.1 — never above 0.2** (frothy cotton-candy look).
- Buoyancy: leave Density + Heat at defaults for lift; heat difference **3–4**
  for a faster rise (CG Geek).
- **Dissolve ~40–45 frames** so smoke doesn't hang forever.
- **Adaptive Domain trick** (CrossMind): when the blast outgrows the box, do
  NOT scale the domain up — voxels grow with it and the sim looks low-res.
  Instead enable Adaptive Domain *Add Resolution* so the domain **extends with
  fine voxels** (effective 330–400 res from a 128 base). Caveat: adaptive
  clipping artifacts are a known issue (Iridesium uses it cautiously).
- Emission mesh: **subdivide / round it** (Ctrl+2–5) — a cube emitter just
  makes a cube of smoke.
- Cache: **Modular or All, never Replay** (RAM blowup while baking); turn on
  **Resumable** (Esc pauses the bake). Cache 100–200 frames; delete files after
  render (they're huge).
- Preset shortcut: Object → Quick Effects → **Quick Smoke**, then fix the
  settings above.

---

## 3. Fire, Smoke, Flow

- Flow type **Fire + Smoke** for fuel blasts; **Smoke only** for pure smoke
  mushrooms.
- **Flow Heat: default 1 → 0.05** so the fireball stays visible longer instead
  of burning out in seconds (Chądzyński's key tip).
- Lower **Reaction Speed** → larger flames.
- Ground: a **bare plane doesn't collide** — use a **thin cube** as effector.
- Trick: make the ground itself a *flow* with **Initial Temperature ≈ −3** →
  cool ground-hugging dust ring (Iridesium).
- Trail particles: spawn slow secondary particles in the first frames that feed
  the domain — afterburn pillars and ground smoke (CrossMind 42:32).

---

## 4. Debris

Separate particle system rendering a **group of small broken cube/plane shard
meshes**:

- **~55 pieces** (more for hero shots), Frame Start 1 / End ~6
- Normal **4–6** + Z offset upward bias
- Rotation **Random + Dynamic** → tumbling
- **Brownian** force for scatter
- Render as an instanced **group**, not spheres

CG Geek: *"the beauty in it is how unperfect it is."*

For production-grade debris without hand-rolling: **RBD Lab** (RaffoVFX) does
realtime rigid-body explosions.

---

## 5. Shading (material goes on the DOMAIN, not the flow)

Two schools for fire — both valid:

### A. Attribute method (most tutorials — flexible, not physical)

- **Volume Info / Attribute node — name exactly `flame`** → Math **Multiply ~5**
  → **Emission** shader (orange).
- Smoke side: **Volume Info (Density)** → **ColorRamp** (dense = black, thin =
  gray) → Math **Multiply ~75** for density; a second multiply drives the
  ramp position so **fire fades as smoke takes over**.
- Add **Fresnel** multiplied with density so thin smoke reads lighter than the
  core (CrossMind) — otherwise the early cloud looks flat and uniform.
- Combine fire + smoke via **Add Shader**.

### B. Principled Volume + Blackbody (Milanese — physically based)

- **Blackbody**, Intensity 1, Temperature driven by the flame grid.
- Higher Kelvin: red → yellow-white → blue; **red/orange = realistic fuel**.
- *Tint* field is a cheat for colored flames — keep white for realism.
- Same node handles smoke: Color, Density, **Anisotropy** (forward/backward
  scatter of light through smoke — huge for backlit shots), **Absorption
  Color** for tinted shadows.
- Two flame colors in one shot: separate domains (if they shouldn't interact)
  or emitter attributes.

> Note: the **Flame Color** slider in flow settings only tints the smoke a fire
> emits — it does nothing to flame appearance (Blender StackExchange).

---

## 6. Lighting & Render

- **Cycles**, **Light Paths → volume bounces 2**, ~**50 samples** + denoiser
  (plenty for volumes).
- Two suns: warm key ~**12** strength from the right, cool bluish rim ~**10**
  from back-left.
- Set **World background strength 0** so the fire's own light dominates.
- Compositor: **use nodes + Glare (Fog Glow / Bloom)** after render sells the
  heat.
- Bake order: bake the sim first, then **bake Noise** (upres). A 192-res bake
  + noise bake gives close-up detail resolution alone can't.

---

## 7. Camera Shake

- **Noise-driven location/rotation keyframes starting at the burst frame with
  fast decay.**
- Tiny FOV punch on the shockwave frame.
- Reference quick tutorials: "Camera Shake in Blender" (96JHvdn12WM),
  "Realistic Camera Shake" (dEyUWqBmnmI).

---

## 8. VDB / Interchange

**Export:** set the smoke cache Format = **OpenVDB** — the baked cache then
literally *is* the VDB export (Blender Artists t/1452207).

**Import:** Volume object (official 5.2 manual,
`docs.blender.org/manual/en/latest/modeling/volumes/introduction.html` and
`.../properties.html`):

- Sequences need `file-000.vdb`, `file-001.vdb` … naming.
- You can import **only the noise grid** from a smoke+noise sequence.
- Playback modes: Hold / Cycle / Ping-Pong.
- Limitations: Blender renders sparse volumes as dense (memory), level-set
  grids can't render as surfaces, VDB points unsupported.
- (Stable current manual URLs are the *volumes* pages — the fluid-physics
  manual pages currently 404.)

**EmberGen → Blender** VDB fire workflows exist, but users report detail loss
on import — if you go outside Blender, **KHAOS Detonator** keeps everything
native Mantaflow.

---

## 9. Geometry Nodes & Simulation Nodes Workflows

GN/sim-nodes explosions are **cheat-space, not volumetric physics**: no true
buoyancy, but fast, controllable, interactive previews. Ladder of realism:

### 9a. Sparks explosion via Simulation Zone (Motion Dreams, 3.5+ style, works in 4.x–5.x)

Emitter = **hemisphere**: UV sphere → delete bottom half → pivot at 3D cursor →
scale down X/Y → nudge down → Apply Scale. This one shape controls both initial
distribution AND blast direction.

Sim-zone recipe from the tutorial:

- **Distribute Points on Faces** on the emitter (drives particle count);
  store each point's **normal** as a vector attribute in the sim zone.
- Every sim tick: **Set Position offset += stored normal × force** — the
  repeated addition per frame is what launches the points. Multiply force by a
  per-particle **Random Value** (~1–3) so speed varies.
- **Gravity**: offset Z negative, masked with Compare > 0 on position Z, so
  particles above the floor fall but don't sink through it.
- **Age**: integer attribute, +1 per tick; **Delete Geometry when age ≥
  random 30–50**. Delete *outside* the sim zone — inside breaks motion blur
  and particle IDs.
- **Normalized Age** = age → Map Range (0–1, from max age) → drives size,
  opacity, and force decay over the particle's life.
- Use a Compare (frame ≥ start) into a Switch as the trigger so everything
  fires once.

### 9b. GN smoke on top of it (same source, Part II)

- Feed new points into the sim zone **every frame inside an emission window**:
  frame ≥ 10 AND ≤ 20 via Boolean Math → Switch. Feeding points continuously
  instead of once is what creates trails. **Scene Time Frame node as the
  seed** each tick → re-randomized distribution, varied trails.
- **Noise movement**: Noise Texture → Map Range (0–1 → −1–1) → offset position;
  scale node controls strength (this is GN's stand-in for sim turbulence).
- **Upward drift**: Normalized Age → Float Curve → Multiply → Combine XYZ
  (Z only) → set position. Jaw the curves to taste.
- **Points → Volume** node: set radius (drive it with Normalized Age so the
  cloud grows over life), density, and **voxel amount** for detail.
- Material: **Principled Volume**; plug the GN density through a Volume Info /
  Attribute node; multiply density by a Noise Texture → ColorRamp (object
  coordinates) so the puffs aren't perfect spheres.
- **EEVEE volume render settings** (from the tutorial): enable volumetric
  shadows, lower tile size for resolution, and set **clip start/end** to the
  actual camera viewing range (e.g. 1–25 m) — best volumetric results there.
- Alternative architecture: **sparks drive the smoke** — Instance to Points
  from the sparks system, join into the smoke sim, disable its own force so
  smoke follows the sparks. (Keeps smoke/debris motion locked together.)

### 9c. Full GN smoke solver (Seanterelle, Blender 5.0 volume-grid nodes)

A real fluid simulation implemented in geometry nodes:

- Domain = **Volume Cube** node (bounds −2..2); grids **velocity (vector),
  divergence, pressure, smoke/density (float)** created with Field to Grid on
  a shared **voxelized topology** — voxelize the grid explicitly so OpenVDB
  block-optimization doesn't hide voxels the forces need to read.
- Sim zone enforces **incompressibility** (divergence/pressure projection) and
  advects the smoke grid; a noise-driven emitter object injects density.
- **Two resolutions**: solver resolution **64** runs interactive for
  pre-vis/blocking; **smoke resolution** 128 → **256** for final detail on the
  same solver run (just longer bake).
- A final **bake node** strips non-essential grids → minimal baked memory.
- Closest thing to Mantaflow inside pure GN; .blend on the author's Gumroad.

### 9d. Other GN references

- Blender SE 321923: minimal sim-zone explosion — instances shear off along
  face normals (stored velocity, offset + rotate per tick). Answer is
  image-only, but confirms the pattern.
- "Curve explosion" GN tutorials exist (instanced debris exploding along
  curves) — good for stylized motion-graphics arms.
- Division of labor that keeps GN useful in a photoreal shot: **Mantaflow for
  the smoke (sections 1–8), GN/sim nodes for sparks, trails and debris**.

---

## 10. Compositor & Final Post Pipeline

### Enable it

Output Properties → **Post Processing**: enable **Compositing** (and
**Sequencer** if using scene strips — with both on, scene strips render
through the compositor). Leave **Dither** on: it prevents banding in smoke
gradients (official manual).

Standard chain built from "Use Nodes" → Render Layers → … → Composite
(Ryan King Art's beginner walk-through, timestamps for each node):

1. **Color**: RGB Curves, Brightness/Contrast, **Color Balance** (grading),
   Hue Correct.
2. **Effects**: **Glare** (the fire bloom — below), Blur, Sun Beams,
   **Lens Distortion** (subtle negative = photographic look), Filter (film
   grain).
3. **Mix**: Alpha Over (layering), Transform/Scale (conform layers), Denoise
   node as final polish.
4. **Animate Values**: any slider is keyframable — e.g. drive Glare intensity
   up on the flash frames.

### Glare for explosions

Two useful glare types: **Bloom** and **Fog Glow**. Fire's emission is far
above brightness threshold 1, so only hot pixels bloom — that's what makes the
GG fire; raise size for spread; **Fog Glow** reads like out-of-focus heat haze.
CrossMind's explosion scenes all finish with compositor Glare.

### Motion blur (Cycles)

- Render → **Motion Blur ON**; **Position: Center on Frame** (shutter fully
  open mid-frame — film standard; Start/End variants exist).
- **Shutter** = exposure length in frames (1.0 blurs across one frame). Start
  around 0.5; fast explosions often want up to 1.0.
- Rolling shutter options exist for a video-look.
- **Bake particles/physics before rendering** — official manual warning,
  otherwise blur can be inconsistent. Per-object motion blur overrides are in
  Object properties.

### Compositing over live footage

Render the explosion with its **alpha** and mix over the plate with Alpha
Over (community-standard integration for real-video FX shots — same pipeline
the KHAOS After Effects breakdown uses).

---

## 11. Recommended Bake Order (full workflow at a glance)

1. Dome emitter split in two + Apply Scale
2. Two particle systems (burst values above, gravity off, seeds varied)
3. Quick Smoke domain sized to the blast + Apply Scale, Gas, 128–192 res
4. Flow: Fire+Smoke, source = particles, Initial Velocity ON, Heat 0.05,
   substeps 2–3
5. Ground: thin-cube effector (+ cool-flow dust trick)
6. Cache = Modular/All + Resumable → **bake sim**
7. Camera, lighting, world off
8. **Bake Noise** (upres)
9. Shade domain: Volume Info / Blackbody + ColorRamp + Fresnel
10. Render Cycles (2 volume bounces, 50 samples) → composite Glare/bloom

---

## 12. Shortcut Add-ons

| Product | What it does |
|---|---|
| **KHAOS Detonator / Ultimate Explosion** (LightArchitect, Blender 4.x–5.0) | Pre-wired Mantaflow explosion + debris rig |
| **RBD Lab** (RaffoVFX) | Realtime rigid-body explosions & debris |
| EmberGen (.vdb) | Third-party export pipeline into Blender |

---

## Sources

- Paweł Chądzyński — "Blender Explosion" short tutorial (2025)
- Iridesium — "Create Simple Explosion VFX in Blender Mantaflow"
- CG Geek — "Create Realistic Explosions!"
- CrossMind Studio — Chapter 7: Mantaflow Explosions (1:15:53; project files at
  gumroad.com/crossmindstudio)
- Francesco Milanese — "Fire Simulations in Blender 4.5 — Principled Volume &
  Blackbody" (francescomilanese.com)
- Official Blender 5.2 manual — Modeling → Volumes
- Blender Artists threads (blurry explosions; VDB export t/1452207)
- Blender StackExchange (Flame Color behavior, q 214631)
- ConceptArtEmpire — "8 Tips for Better Explosion Simulations" (partial;
  reCAPTCHA-blocked)
- Seanterelle — "3D Smoke (Blender Geometry Nodes)" (Blender 5.0, 2025; GN
  fluid-solver smoke, .blend on author's Gumroad)
- Motion Dreams — "Procedural Explosion Effect in Blender" Part I (sparks) &
  Part II (smoke), 2024 (GN/sim nodes; project files on Patreon)
- Ryan King Art — "Compositing for Beginners" (2025)
- Blender StackExchange q 321923 (sim-zone normals explosion pattern)
- Official Blender manual — Post Processing panel; Cycles Motion Blur
