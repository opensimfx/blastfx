"""Particle-driven fireball burst (plan T1.1-T1.6).

Blast realism comes from a quick fuel burst injected along fast, short-lived
particles: the emission dome is split at the equator into an upper and a
lower cap, each carrying a particle system that bursts outward from its
interior; the particle systems feed the Mantaflow flow as PARTICLE_SYSTEM
sources (the mushroom shape falls out of the cap split).
"""

import bmesh

from ..utils.naming import component_name
from .fluid import (
    add_mesh_object,
    configure_fluid_modifier,
    configure_flow,
)
from .particles import _add_particle_system, set_particle_seed

_CAP_SEGMENTS = 24
_CAP_RINGS = 12
_VARIANT_SEED_OFFSET = {"upper": 31, "lower": 7}


def _hemisphere(bm, radius, upper):
    """Build a spherical-cap emitter mesh: a UV sphere split at the equator."""
    bmesh.ops.create_uvsphere(
        bm, u_segments=_CAP_SEGMENTS, v_segments=_CAP_RINGS, radius=radius
    )
    to_delete = [
        v for v in bm.verts
        if (v.co.z < 0.0 if upper else v.co.z > 0.0)
    ]
    bmesh.ops.delete(bm, geom=to_delete, context="VERTS")


def _particle_seed(numerical_seed, suffix):
    """Deterministic per-cap particle seed from the blast seed."""
    return (
        int(numerical_seed) * 2654435761 + _VARIANT_SEED_OFFSET.get(suffix, 3)
    ) % 2147483647


def _build_burst_flow(context, collection, controller, config, suffix, upper):
    """Cap mesh + particle system + particle-source flow for one half."""
    physical = config["physical"]
    numerical = config["numerical"]
    profile = config["profile"]
    blast_id = controller["blastfx_id"]
    fps = context.scene.render.fps / context.scene.render.fps_base
    radius = physical.characteristic_radius_m * profile.source_radius
    start = int(config["start_frame"])
    emission, lifetime, _ = profile.burst_timing(fps)

    name = component_name(blast_id, suffix)
    obj = add_mesh_object(
        collection,
        name,
        lambda bm: _hemisphere(bm, radius, upper),
        controller.location,
    )

    def configure_particles(settings):
        settings.type = "EMITTER"
        settings.count = numerical.burst_count
        settings.frame_start = start
        settings.frame_end = start + emission
        settings.lifetime = lifetime
        settings.lifetime_random = 0.25
        settings.physics_type = "NEWTON"
        settings.emit_from = "VOLUME"
        settings.distribution = "RAND"
        settings.render_type = "NONE"
        settings.child_type = "NONE"
        # The fluid carries the motion; particles only seed it. Gravity on the
        # particles would fight the buoyancy-driven ascension (research tip).
        settings.effector_weights.gravity = 0.0
        settings.mass = 0.1
        set_particle_seed(settings, _particle_seed(numerical.seed, suffix))

    psys = _add_particle_system(obj, f"{name}_psys", configure_particles)

    _, flow = configure_fluid_modifier(obj, "FLOW")
    # Initial velocity comes from the particle system; the cap mesh itself
    # never injects (flow_source=PARTICLE_SYSTEM). Research flow-heat trick:
    # keep the injected temperature tiny (profile.flow_heat ~ 0.05, the
    # Mantaflow "Flow Heat" slider maps to this RNA property) so buoyancy
    # doesn't blow the fire out and burning stays visible longer.
    configure_flow(
        flow,
        flow_type="BOTH",
        flow_source="PARTICLES",
        particle_system=psys,
        temperature=profile.flow_heat * numerical.temperature_scale,
        density=numerical.density_scale,
        fuel=profile.fuel_amount,
        subframes=5,
    )
    # The particle system IS the injection window: particles are seeded over
    # `emission` frames and live `lifetime` frames, so smoke stops being fed
    # once they die (verified empirically: cache sizes plateau after the last
    # particle). Mesh inflow gating is unnecessary with PARTICLES sources.
    obj.hide_render = True
    obj.display_type = "WIRE"
    obj["blastfx_role"] = "burst_emitter"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "fireball_burst"
    obj["blastfx_generated"] = True
    return obj


def build_burst(context, collection, controller, config):
    """Create the upper/lower burst caps and their particle-driven flows."""
    upper = _build_burst_flow(
        context, collection, controller, config, "FireballBurstUpper", True
    )
    _build_burst_flow(context, collection, controller, config, "FireballBurstLower", False)
    return upper
