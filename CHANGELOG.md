# Changelog

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
