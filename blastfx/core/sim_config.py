"""Numerical Mantaflow configuration for one blast (pure Python, no bpy)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .domain_envelope import build_domain_envelope, longest_side
from .explosion_profile import profile_for
from .froude import solver_scaling


@dataclass(frozen=True)
class SimulationConfig:
    domain_resolution: int
    noise_upres: int
    # True voxel edge in metres (longest domain side / resolution).
    voxel_size_m: float
    # Froude velocity scale U = sqrt(g*R).
    characteristic_velocity_mps: float
    # Solver time scale: Froude scaling x playback speed (core.froude).
    time_scale_multiplier: float
    turbulence_strength: float
    buoyancy_density: float
    buoyancy_heat: float
    burning_rate: float
    flame_smoke: float
    flame_vorticity: float
    flame_ignition: float
    flame_max_temp: float
    noise_strength: float
    noise_pos_scale: float
    noise_time_anim: float
    use_dissolve_smoke: bool
    dissolve_speed: int
    temperature_scale: float
    density_scale: float
    seed: int
    burst_count: int
    # Burst particle speeds in scene m/s (event speed x playback speed).
    burst_normal_velocity: float
    burst_random_velocity: float
    # FluidFlowSettings.velocity_factor for particle-sourced flows.
    particle_velocity_factor: float = 1.0
    # FluidFlowSettings.particle_size for the burst, in simulation cells.
    burst_particle_size_cells: float = 1.0
    playback_speed: float = 1.0
    # Fraction of the Froude buoyancy the RNA limit (|beta| <= 5) dropped.
    buoyancy_shortfall: float = 0.0
    # Solver-cost knobs chosen per quality tier (see TIER_SOLVER).
    cfl_condition: float = 2.0
    timesteps_min: int = 2
    timesteps_max: int = 8
    adapt_margin: int = 20
    adapt_threshold: float = 0.001
    additional_res: int = 4
    # Adaptive domain off: its moving box clipped rising smoke every step
    # into horizontal bands (measured on medium/large_ground; margins 4 and
    # 12 banded, 20 mostly not), and inside the tight Froude envelope it
    # saved little (margin 4: 38 s, off: 48 s, margin 20: 53 s at Draft).
    use_adaptive_domain: bool = False


# Solver cost per quality tier. Tiers never change the physical event, only
# how finely it is resolved. Measured on medium at Preview (46 frames):
# 257 s as before; the noise pass alone was ~50 % of the cost and CFL 4
# saved another ~20 %; without noise and at CFL 4 it took 104 s with the
# same shape and timing (smoother billows, no fine soot detail). Draft and
# Preview judge motion and shape, so they skip noise and use CFL 4; Final
# keeps the noise pass and CFL 2 for full fidelity.
TIER_SOLVER = {
    "DRAFT": {"noise": False, "cfl": 4.0, "timesteps_min": 1, "timesteps_max": 4,
              "adapt_margin": 4, "adapt_threshold": 0.002, "additional_res": 0},
    "PREVIEW": {"noise": False, "cfl": 4.0, "timesteps_min": 1, "timesteps_max": 6,
                "adapt_margin": 8, "adapt_threshold": 0.002, "additional_res": 2},
    "FINAL": {"noise": True, "cfl": 2.0, "timesteps_min": 1, "timesteps_max": 8,
              "adapt_margin": 12, "adapt_threshold": 0.001, "additional_res": 4},
}

# Automatic resolution: voxels across the fireball radius per tier. The old
# fixed 128-256 over a padded domain left 4-10 voxels per radius on the
# conventional presets, which is why fireballs read as blobs.
VOXELS_PER_RADIUS = {"DRAFT": 8, "PREVIEW": 14, "FINAL": 24}
AUTO_RESOLUTION_LIMITS = (24, 512)


def tier_solver(quality):
    """Solver-cost settings for a quality tier (unknown tiers use PREVIEW)."""
    return TIER_SOLVER.get(quality, TIER_SOLVER["PREVIEW"])


def resolve_resolution(quality, override, domain_size_m, radius_m) -> int:
    """Domain resolution: an explicit override, or voxels-per-radius.

    An override keeps its historical meaning (FINAL scales it by 1.5; Draft
    halving happens once when a preset is applied). Auto resolution derives
    from the radius so detail is the same at every blast size.
    """
    if override and int(override) > 0:
        factor = {"FINAL": 1.5}.get(quality, 1.0)
        return max(16, int(int(override) * factor))
    per_radius = VOXELS_PER_RADIUS.get(quality, VOXELS_PER_RADIUS["PREVIEW"])
    low, high = AUTO_RESOLUTION_LIMITS
    wanted = math.ceil(float(domain_size_m) * per_radius / max(float(radius_m), 1e-6))
    return max(low, min(high, wanted))


def build_simulation_config(
    derived,
    quality,
    resolution,
    noise,
    seed,
    turbulence=1.0,
    smoke_density=1.0,
    fire_temperature=1.0,
    profile=None,
    timeline_duration_s=0.0,
    fps=24.0,
    playback_speed=1.0,
):
    """Map derived physics + profile + artist controls onto solver values.

    ``timeline_duration_s`` is in scene seconds (event length / playback
    speed). Profiles default to FUEL so callers without one stay valid.
    """
    profile = profile or profile_for("FUEL")
    # Particle count is the detail dial for fuel filaments (CrossMind); the
    # hero band 8-10k is reached at FINAL quality.
    burst_quality_factor = {"DRAFT": 1.0, "PREVIEW": 2.0, "FINAL": 4.0}.get(quality, 1.0)
    radius = float(derived.characteristic_radius_m)
    domain_size = longest_side(build_domain_envelope(derived, profile))
    domain_resolution = resolve_resolution(quality, resolution, domain_size, radius)
    scaling = solver_scaling(domain_size, playback_speed)
    velocity_unit = max(float(derived.characteristic_velocity_mps), 1e-6)
    # Per-solver-time rates held constant per T (core.froude.rate_factor).
    rate = scaling.rate_factor(derived.time_unit_s)
    intensity = max(0.1, derived.intensity)
    tier = tier_solver(quality)
    # Smoke fades over the profile's fade time (in T, so it scales with the
    # blast, not with the shot length). Dissolve runs per solver step, so
    # the frame count is scaled by the time scale to stay in scene frames.
    # Burst fuel injection: Mantaflow sizes particle emission in cells, so a
    # fixed size injected ~1/27 the volume per particle at Final vs Draft and
    # Final burned out sooner (measured: flame -33 %, smoke -23 % at the same
    # frame). Hold each particle's radius in metres, shrinking it as the tier
    # adds particles, so total injected volume matches Draft (the tuned look).
    burst_count = max(200, int(round(profile.burst_count * burst_quality_factor)))
    voxel_size = domain_size / domain_resolution
    draft_radius_m = radius / VOXELS_PER_RADIUS["DRAFT"]
    particle_radius_m = draft_radius_m * (profile.burst_count / burst_count) ** (1.0 / 3.0)
    burst_particle_size_cells = max(0.1, particle_radius_m / voxel_size)
    dissolve_scene_frames = max(
        12.0, scaling.scene_frames(profile.smoke_fade_seconds(derived.time_unit_s), fps)
    )
    return SimulationConfig(
        domain_resolution=domain_resolution,
        # Draft and Preview skip the noise pass: it doubles bake time and disk
        # and adds only fine detail, which those tiers are not for.
        noise_upres=max(1, min(8, int(noise))) if tier["noise"] else 1,
        voxel_size_m=voxel_size,
        characteristic_velocity_mps=velocity_unit,
        time_scale_multiplier=scaling.time_scale,
        # Expert ceiling for vorticity is 0.2 (froth above it); artist
        # turbulence 1.0 maps into the middle of the band.
        # The 0.2 froth ceiling applies at the reference size; the rate factor
        # then keeps the same look at other sizes (RNA allows up to 4).
        turbulence_strength=min(4.0, max(0.0, min(0.2, float(turbulence) * profile.turbulence * 0.12)) * rate),
        buoyancy_density=scaling.buoyancy(profile.buoyancy_density),
        buoyancy_heat=scaling.buoyancy(profile.buoyancy_heat),
        burning_rate=max(0.01, min(4.0, profile.burning_rate * rate)),
        flame_smoke=max(0.0, min(8.0, float(smoke_density) * profile.flame_smoke)),
        flame_vorticity=max(0.0, min(2.0, profile.flame_vorticity * rate)),
        flame_ignition=max(0.5, min(5.0, profile.flame_ignition)),
        flame_max_temp=max(1.0, min(10.0, 3.0 + 0.25 * intensity)),
        noise_strength=profile.noise_strength,
        noise_pos_scale=profile.noise_scale,
        noise_time_anim=0.1,
        use_dissolve_smoke=True,
        dissolve_speed=scaling.dissolve_frames(dissolve_scene_frames),
        temperature_scale=max(0.1, min(10.0, float(fire_temperature) * profile.temperature)),
        density_scale=max(0.1, min(10.0, float(smoke_density) * profile.density)),
        seed=int(seed),
        burst_count=burst_count,
        burst_normal_velocity=scaling.scene_velocity(profile.burst_speed_U * velocity_unit),
        burst_random_velocity=scaling.scene_velocity(profile.burst_random_U * velocity_unit),
        particle_velocity_factor=scaling.particle_velocity_factor,
        burst_particle_size_cells=burst_particle_size_cells,
        playback_speed=scaling.playback_speed,
        buoyancy_shortfall=round(scaling.buoyancy_shortfall(profile.buoyancy_heat), 4),
        cfl_condition=tier["cfl"],
        timesteps_min=tier["timesteps_min"],
        timesteps_max=tier["timesteps_max"],
        adapt_margin=tier["adapt_margin"],
        adapt_threshold=tier["adapt_threshold"],
        additional_res=tier["additional_res"],
    )
