# Blast FX example scenes

Regression scenes for the physics validation plan (section F) in
`docs/DEVELOPMENT.md`. Each file is a
self-contained Blender 5.2 scene with a deterministic seed, the blast at the
world origin, PREVIEW quality, a camera framed on the domain envelope, and
neutral sun + world lighting. **No cache is baked**, so the files stay small.

Regenerate with:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python tools/make_examples.py
```

Bake any scene by opening it and pressing **Bake Simulation** in the Blast FX
panel (or `bpy.ops.blastfx.bake()`), then scrub the timeline to review.

## Scenes

- **test_small.blend** — `small` preset (GROUND): compact ground blast with a
  fireball and shockwave, seed 1001. Best first bake; lowest domain resolution, so
  it completes fastest.
- **test_medium.blend** — `medium` preset (FUEL): fuel/vehicle-scale blast with a
  ground surge, seed 2002. Demonstrates buoyant smoke rise and dust motion.
- **test_large.blend** — `large` preset (FUEL, "Medium Ground Blast"): medium
  ground blast with a fireball, ground surge and smoke, seed 3003.
- **test_large_event.blend** — `large_ground` preset (LARGE): large ground
  blast with a rising column, ground surge and a wide shockwave, seed 4004.
  Highest resolution; the longest bake.

## Headless open + bake

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
    examples/test_medium.blend --python-expr \
    "import bpy; bpy.ops.blastfx.bake()"
```

Bakes run in a background worker process; poll progress from the Blast FX panel.
