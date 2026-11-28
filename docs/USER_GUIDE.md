# User Guide

BlastFX builds a complete explosion from a few physical settings: the fireball size, how fast the shot
plays back and how long it lasts. Everything else (domain size, resolution, solver timing, fire and smoke
shading, the cinematic layer) follows from those, so a blast looks the same at any size and only its
real-world timing changes. See [PHYSICS.md](PHYSICS.md) for why.

## Install

1. Get the zip from [Gumroad](https://arshth.gumroad.com/l/blastfx), or build it from the source: `python tools/build_extension.py`
   (writes `dist/blastfx-<version>.zip`).
2. In Blender 5.2 LTS: *Edit > Preferences > Get Extensions > (v) > Install from Disk...*, pick the zip.
3. Open the 3D Viewport sidebar (**N**) and the **BlastFX** tab.

## Your first blast

1. Place the 3D cursor where the blast should start (on the ground for ground blasts; at the burst
   height for **Nuclear Air Burst**).
2. Pick a preset from the menu at the top of the panel. The description under it says what it is.
3. Press **Create Blast**. A new collection holds the controller (an empty), the gas domain, the
   emitters and, if enabled, the camera, lights and ground collider.
4. Open **Cache and Bake**, keep **Draft** and press **Bake Simulation**. The bake runs in a background
   Blender process, so the interface stays responsive; progress, elapsed and remaining time show in the panel.
5. Scrub the timeline, then switch to **Preview** or **Final** and bake again for the shot.
6. Render with Cycles.

To change a blast, select its controller, edit the settings and press **Rebuild Blast**. **Duplicate Blast**
places a copy with the same settings beside it; **Remove Blast** deletes its collection.

## The panel

### Explosion

| Setting | What it does |
|---|---|
| Type | Ground (charge), Fuel (vehicle, fuel-rich), Large, Heavy, Nuclear. Each has its own profile: burst shape, burn rate, smoke, column and surge. |
| Fireball Size | Fireball diameter in metres. Nuclear uses **Yield (kt)** instead. |
| Playback Speed | 1 = real time, 0.5 = 2x slow motion. Practical explosions are usually filmed in slow motion. |
| Duration | Real event seconds the shot covers. **0** = automatic: the type's natural length at this size (the panel shows it). |
| Start Frame, Seed | When the blast starts; the seed varies the details without changing the look. |
| Directed Blast, Blast Direction | A one-sided blast: fireball, debris and sparks drive into the half-space the direction faces (a charge against a wall, a vehicle hit from the side, a mortar burst). At most 75 degrees from straight up; the ground surge stays put and the domain shifts that way. |

### Components

Simulation parts: **Fireball**, **Rising Column**, **Ground Surge** (dust), **Shockwave** (dust ring),
**Debris** (with **Smoking Debris**: each shard drags a thin smoke trail once it is clear of the fireball),
and **Rapatronic Skin** for Nuclear. **Fire Path**: pick a curve and a flame front runs along it at **Path
Speed** (metres per second of event time), like a fuel trail igniting, burning on behind the front; keep the
curve inside the blast's domain, and re-bake after editing it. Cinematic parts: **Fire Light**, **Camera FX** (a camera framed
on the blast, with a shake that arrives with the sound), **Exposure & Bloom** and **Heat Distortion**. Your own
scene camera stays active: the BlastFX camera is added beside it. Turn on **Use BlastFX Camera** to render
through it; removing the blast gives your camera back. A scene with no camera uses the BlastFX one.

### Look

**Fire Temperature**, **Smoke Density**, **Turbulence** and **Intensity** scale the type's defaults. They
change the look, not the physics: a blast with higher Smoke Density is the same event with darker smoke.

**Fire Grading** changes only the material, so it updates the baked blast live (even during a bake) and never
needs a re-bake. All four are neutral at their defaults.

| Setting | What it does |
|---|---|
| Fire Exposure | Fire brightness in stops: +1 doubles it. |
| Fire Contrast | Above 1: a hotter core with thinner, darker flame edges; below 1: softer, fuller flames. Pivots on a typical flame, so the fire keeps roughly its brightness. |
| Flame Break-up | Splits the fire into flickering tongues and gaps (an evolving noise mask about the fireball's depth). |
| Fire Lights Scene | How strongly the fire lights the ground, smoke and scene, separately from how bright it looks to the camera. Cycles only; mostly visible at night. |

### Cache and Bake

| Quality | Use it for | Cost |
|---|---|---|
| Draft | Timing and silhouette | Fast: low resolution, no noise pass |
| Preview | Judging the look | About 2.5x faster than Final, no noise pass |
| Final | The render | Full resolution plus the noise pass |

**Resolution** 0 picks the domain resolution from the fireball size and quality (voxels per fireball radius);
set a number to override it. **Noise** only applies to Final. The cache lives under **Cache Folder**, one
folder per blast; **Free Cache** deletes it. A cache is only reused when everything that affects the
simulation is unchanged, so changing a setting marks it out of date instead of showing a wrong bake.

**Bake All Blasts** queues every blast in the scene. After a bake, **Render Flipbook** renders the baked range
at half size with few samples (EEVEE by default) into the blast's cache folder, to check timing and shape before
the full render; **Play Flipbook** plays it in Blender's animation player. **Re-bake Noise** (Final quality):
change **Noise** after a bake and bake only the noise pass again; the simulation itself is kept. It refuses when
a setting that changes the simulation was changed too. **Export Sprite Sheet** renders the baked blast into one
transparent atlas of frames (4 x 4 to 8 x 8) plus a JSON describing it, for camera-facing cards and game engines;
it is lit by your scene's lights and world and saved in `blastfx_sprites/` next to the .blend. Your render settings are put back
afterwards, also if you cancel with Esc.

### Readout and Diagnostics

**Readout** shows what Create will build: fireball diameter, the time unit T, the event length, frames,
the solver time scale, resolution, voxels per radius and voxel size. **Diagnostics** lists errors and
warnings, for example when a very large blast exceeds Blender's solver limits and rises a little slower
than real.

### Preset Files

**Save as Preset** stores the current settings as a JSON preset in the add-on's user data folder (kept across
updates) and adds it to the menu at once.
See [PRESETS.md](PRESETS.md) for the factory presets.

## Tips

- Bake in **Draft** first. A Final bake of a large blast can take hours (Heavy: about 3.5 h on an Apple M4 CPU,
  Small: 14 min); Draft and Preview are for deciding whether it is worth it.
- Bigger blasts are slower in real time: a 170 m nuclear fireball takes about 3 s per time unit T, a 4 m
  charge 0.45 s. Use Playback Speed for slow motion rather than stretching Duration.
- Under Blender's default AgX view the fire is graded to keep its colour; Filmic shows the raw blackbody colour.
- Keep the blast's collection: the cache, the controller and the generated objects belong together.
