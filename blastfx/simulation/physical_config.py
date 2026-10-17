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
):
    quality_factor = {"DRAFT": 0.5, "PREVIEW": 1.0, "FINAL": 1.5}.get(quality, 1.0)
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
        turbulence_strength=max(0.0, min(4.0, float(turbulence) * turbulence_base)),
        buoyancy_density=max(0.0, min(5.0, multiplier.buoyancy_density if multiplier else (0.8 + 0.15 * intensity))),
        buoyancy_heat=max(0.0, min(5.0, multiplier.buoyancy_heat if multiplier else (1.0 + 0.35 * intensity))),
        burning_rate=max(0.05, min(4.0, multiplier.burning_rate if multiplier else (0.9 / max(intensity, 0.25)))),
        flame_smoke=max(0.0, min(8.0, float(smoke_density) * (multiplier.flame_smoke if multiplier else (1.0 + 0.25 * intensity)))),
        flame_vorticity=max(0.0, min(2.0, multiplier.flame_vorticity if multiplier else (0.25 + 0.08 * intensity))),
        flame_ignition=max(0.5, min(5.0, 1.5)),
        flame_max_temp=max(1.0, min(10.0, 3.0 + 0.25 * intensity)),
        noise_strength=multiplier.noise_strength if multiplier else 1.0,
        noise_pos_scale=multiplier.noise_scale if multiplier else 2.0,
        noise_time_anim=0.1,
        use_dissolve_smoke=True,
        dissolve_speed=150,
        temperature_scale=max(0.1, min(10.0, float(fire_temperature) * (multiplier.temperature if multiplier else (1.0 + intensity)))),
        density_scale=max(0.1, min(10.0, float(smoke_density) * (multiplier.density if multiplier else 1.0))),
        seed=int(seed),
    )
