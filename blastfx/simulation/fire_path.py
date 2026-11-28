"""Fire along a path: a flame front that runs along a user curve, like a fuel trail igniting.

The curve is resampled into points every ``spacing`` metres (a fraction of the fireball radius, so it scales with
the blast). One particle system emits from those points *in order* (``use_emit_random`` off), so the emission
front travels the path at ``speed`` m/s; short-lived, slowly rising particles feed a Mantaflow fuel flow
(PARTICLES source), which burns where the front has passed. The path's shape enters the cache identity
(``path_signature``), so editing the curve asks for a re-bake.
"""
from __future__ import annotations

import hashlib
import math

import bpy

from .fluid import add_mesh_object, configure_fluid_modifier, configure_flow
from .particles import _add_particle_system, set_particle_seed

SPACING_R = 0.12          # emission points every 0.12 R along the path
EMITS_PER_POINT = 16      # particles per point: fuel keeps feeding the trail behind the front
LIFETIME_T = 0.8          # each particle feeds fuel for 0.8 T: the trail burns on behind the front
RISE_U = 0.15             # gentle upward start velocity (buoyancy does the rest)


def path_points(curve_obj, spacing: float) -> list[tuple[float, float, float]]:
    """World-space points every ``spacing`` metres along the evaluated curve (all splines in order)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = curve_obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    try:
        mw = curve_obj.matrix_world
        verts = [mw @ v.co for v in mesh.vertices]
        # follow edge connectivity in vertex order: curve meshes list each spline's points in order
        chains, current = [], []
        edges = {tuple(sorted(e.vertices)) for e in mesh.edges}
        for i, co in enumerate(verts):
            if current and tuple(sorted((i - 1, i))) not in edges:
                chains.append(current)
                current = []
            current.append(co)
        if current:
            chains.append(current)
    finally:
        ev.to_mesh_clear()
    out = []
    for chain in chains:
        if not chain:
            continue
        out.append(tuple(chain[0]))
        carry = 0.0
        for a, b in zip(chain, chain[1:]):
            seg = (b - a).length
            t = spacing - carry
            while t <= seg:
                p = a.lerp(b, t / seg)
                out.append(tuple(p))
                t += spacing
            carry = seg - (t - spacing)
    return out


def path_length(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def path_signature(curve_obj, radius: float) -> str:
    """Hash of the resampled path (cache identity): changes when the curve is edited or moved."""
    pts = path_points(curve_obj, max(radius * SPACING_R, 1e-3))
    h = hashlib.sha256(";".join(f"{x:.4f},{y:.4f},{z:.4f}" for x, y, z in pts).encode()).hexdigest()
    return h[:16]


def build_fire_path(context, collection, controller, config, curve_obj, speed_mps: float):
    """Emitter on the resampled path + ordered particle emission + fuel flow; returns the emitter object."""
    physical, numerical, profile = config["physical"], config["numerical"], config["profile"]
    blast_id = controller["blastfx_id"]
    r = physical.characteristic_radius_m
    U = physical.characteristic_velocity_mps
    playback = numerical.playback_speed
    pts = path_points(curve_obj, max(r * SPACING_R, 1e-3))
    if len(pts) < 2:
        raise ValueError(f"Fire path '{curve_obj.name}' is too short for this blast size.")
    length = path_length(pts)
    # slow motion stretches the run like the rest of the blast
    run_frames = max(1, int(round(config["plan"].event_frames(length / max(speed_mps, 1e-3)))))
    start = int(config["start_frame"])

    def build(bm):
        for p in pts:
            bm.verts.new(p)

    obj = add_mesh_object(collection, f"Blast_{blast_id}_FirePath", build, (0.0, 0.0, 0.0))
    life = max(1, int(round(config["plan"].event_frames(LIFETIME_T * physical.time_unit_s))))

    def configure(settings):
        settings.type = "EMITTER"
        settings.count = len(pts) * EMITS_PER_POINT
        settings.frame_start = start
        settings.frame_end = start + run_frames
        settings.lifetime = life
        settings.lifetime_random = 0.3
        settings.emit_from = "VERT"
        settings.use_emit_random = False          # in vertex order: the front runs along the path
        settings.physics_type = "NEWTON"
        settings.normal_factor = 0.0
        settings.object_align_factor = (0.0, 0.0, RISE_U * U * playback)
        settings.factor_random = 0.1 * U * playback
        settings.effector_weights.gravity = 0.0
        settings.render_type = "NONE"
        settings.child_type = "NONE"
        set_particle_seed(settings, numerical.seed + 101)

    psys = _add_particle_system(obj, "FirePathParticles", configure)
    _, flow = configure_fluid_modifier(obj, "FLOW")
    configure_flow(
        flow,
        flow_type="BOTH",
        flow_source="PARTICLES",
        particle_system=psys,
        temperature=profile.flow_heat * numerical.temperature_scale,
        density=0.6 * numerical.density_scale,
        fuel=profile.fuel_amount,
        subframes=3,
        velocity_factor=numerical.particle_velocity_factor,
    )
    flow.use_particle_size = True
    flow.particle_size = max(2.0, 2.0 * float(numerical.burst_particle_size_cells))
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "fire_path_emitter"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "fire_path"
    obj["blastfx_generated"] = True
    obj["blastfx_fire_path_frames"] = (start, start + run_frames)
    return obj
