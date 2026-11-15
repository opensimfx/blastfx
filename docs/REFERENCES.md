# References and Licensing

## Licensing

BlastFX is GPL-3.0-or-later and original work. It bundles no third-party code, shaders, node groups, textures,
VDBs or other assets. The material below informed the design; nothing from it is copied into the add-on.

## Research sources

- Blender source: `intern/mantaflow/intern/strings/smoke_script.h`, `fluid_script.h`,
  `source/blender/blenkernel/intern/fluid.cc` (main branch, fetched 2026-11-14)
- Blender manual: fluid domain Settings, Cache, Guides, Noise
- Fireball correlations: https://www.aidic.it/cet/20/82/036.pdf ,
  https://www.icheme.org/media/25181/the-assessment-of-major-hazards-icheme-symposium-series-71-1982-15-lihou.pdf
- Miniature/high-speed practice: https://cinematography.net/edited-pages/Earth_Explosion_-_fps.htm
- Heat distortion via refraction shells: https://www.blendernation.com/2018/09/23/create-realistic-heat-distortions-in-blender/ ,
  https://blenderartists.org/t/fake-simulated-heat-distortion-in-blender/1282239
- Free CC0 VDBs: https://jangafx.com/software/embergen/download/free-vdb-animations
- Blender 5.0 volume grid nodes: https://developer.blender.org/docs/release_notes/5.0/geometry_nodes/
- Fire shading practice: https://sites.google.com/view/vdblabuserguide/user-interface/main-modules/shading ,
  https://www.blendernation.com/2024/03/29/two-tips-for-better-explosions-in-blender-initial-velocity-and-turbulence-quicktip-ft-khaos-add-on/

## Physics background

The scaling laws (Froude similarity, the time unit T = sqrt(R/g)), the blackbody fire model and the nuclear
fireball sizing (cube-root law after Glasstone and Dolan, compressed 8x for cinematic framing) are described with
their reasoning in [PHYSICS.md](PHYSICS.md); the measurements behind them are in [VALIDATION.md](VALIDATION.md).
