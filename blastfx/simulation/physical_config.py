from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    domain_resolution: int
    noise_upres: int
    voxel_size_m: float
    characteristic_velocity_mps: float
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
    burst_normal_velocity: float
    burst_random_velocity: float


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
):
    # DRAFT scaling is done once by presets/apply.py (preset resolution is
    # pre-halved); manual resolution edits reach the build 1:1.
    quality_factor = {"DRAFT": 1.0, "PREVIEW": 1.0, "FINAL": 1.5}.get(quality, 1.0)
    # Burst particles refine fuel filaments in denser domains (CrossMind:
    # particle count is the detail dial); the hero band 8-10k is reached at
    # FINAL quality.
    burst_quality_factor = {"DRAFT": 1.0, "PREVIEW": 2.0, "FINAL": 4.0}.get(quality, 1.0)
    base_resolution = resolution or 128
    domain_resolution = max(16, int(base_resolution * quality_factor))
    intensity = max(0.1, derived.intensity)
    multiplier = profile
    turbulence_base = multiplier.turbulence if multiplier else (0.12 + 0.25 * intensity)
    return SimulationConfig(
        domain_resolution=domain_resolution,
        noise_upres=max(1, min(8, int(noise))),
        voxel_size_m=max(derived.characteristic_radius_m / domain_resolution, 1e-5),
        characteristic_velocity_mps=max(0.1, float(derived.characteristic_velocity_mps)),
        time_scale_multiplier=1.0,
        # Expert ceiling for vorticity is 0.2 (froth above it); artist
        # turbulence 1.0 maps into the middle of the band.
        turbulence_strength=max(0.0, min(0.2, float(turbulence) * turbulence_base * 0.12)),
        buoyancy_density=max(0.0, min(5.0, multiplier.buoyancy_density if multiplier else (0.8 + 0.15 * intensity))),
        buoyancy_heat=max(0.0, min(5.0, multiplier.buoyancy_heat if multiplier else (1.0 + 0.35 * intensity))),
        burning_rate=max(0.05, min(4.0, multiplier.burning_rate if multiplier else (0.9 / max(intensity, 0.25)))),
        flame_smoke=max(0.0, min(8.0, float(smoke_density) * (multiplier.flame_smoke if multiplier else (1.0 + 0.25 * intensity)))),
        flame_vorticity=max(0.0, min(2.0, multiplier.flame_vorticity if multiplier else (0.25 + 0.08 * intensity))),
        flame_ignition=max(0.5, min(5.0, multiplier.flame_ignition if multiplier else 1.5)),
        flame_max_temp=max(1.0, min(10.0, 3.0 + 0.25 * intensity)),
        noise_strength=multiplier.noise_strength if multiplier else 1.0,
        noise_pos_scale=multiplier.noise_scale if multiplier else 2.0,
        noise_time_anim=0.1,
        use_dissolve_smoke=True,
        # Dissolve as the second half of the timeline (CG Geek used ~1/3 of
        # the clip duration): smoke must linger across the render, and a
        # quarter-timeline dissolve wiped GROUND blasts clean by frame ~40
        # (probe evidence: examples/burst_probe/ground_close_f040.png).
        dissolve_speed=max(12, int(round(timeline_duration_s * fps * 0.5))),
        temperature_scale=max(0.1, min(10.0, float(fire_temperature) * (multiplier.temperature if multiplier else (1.0 + intensity)))),
        density_scale=max(0.1, min(10.0, float(smoke_density) * (multiplier.density if multiplier else 1.0))),
        seed=int(seed),
        # Hero presets need 8-10k burst particles at final quality (plan T1.2);
        # profile counts describe the interactive DRAFT bake and scale up per
        # quality tier (LARGE FINAL: 2400 * 4 = 9600).
        burst_count=max(200, int(round((multiplier.burst_count if multiplier else 1500) * burst_quality_factor))),
        # Particle speeds are domain-relative like the benchmarks (4-6 m/s in
        # a ~2 m domain); scale up only when the characteristic speed is higher.
        burst_normal_velocity=max(0.5, float(multiplier.burst_normal_velocity if multiplier else 4.5) * max(1.0, derived.characteristic_velocity_mps)),
        burst_random_velocity=max(0.0, float(multiplier.burst_random_velocity if multiplier else 4.5) * max(1.0, derived.characteristic_velocity_mps)),
    )
