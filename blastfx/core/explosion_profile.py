"""Physically informed, deterministic VFX profiles for each explosion type."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShadingConfig:
    """Volume shading inputs derived per profile (plan T2.5).

    Fire renders from the Mantaflow `flame` grid through Emission; smoke
    colors through a density ColorRamp (light thin wisps -> near-black
    dense core). Blackbody stays wired but off until visually tuned:
    flame-grid emission + blackbody together double the fire exposure.
    """
    smoke_ramp: tuple  # ((position, rgba), ...) ascending positions
    density_multiplier: float
    temperature_multiplier: float = 1.0
    blackbody_intensity: float = 0.0
    flame_color: tuple = (1.0, 0.34, 0.03, 1.0)
    flame_multiplier: float = 5.0
    anisotropy: float = 0.0

    def as_dict(self):
        return asdict(self)


SHADING = {
    "GROUND": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.45, 0.36, 0.28, 1.0)),
            (0.18, (0.34, 0.24, 0.16, 1.0)),
            (0.55, (0.09, 0.06, 0.045, 1.0)),
            (1.0, (0.015, 0.01, 0.008, 1.0)),
        ),
        density_multiplier=0.35,
    ),
    "FUEL": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.50, 0.45, 0.40, 1.0)),
            (0.18, (0.30, 0.25, 0.20, 1.0)),
            (0.55, (0.08, 0.06, 0.05, 1.0)),
            (1.0, (0.012, 0.01, 0.008, 1.0)),
        ),
        density_multiplier=0.30,
    ),
    "LARGE": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.55, 0.50, 0.44, 1.0)),
            (0.18, (0.36, 0.31, 0.26, 1.0)),
            (0.55, (0.11, 0.09, 0.075, 1.0)),
            (1.0, (0.014, 0.012, 0.01, 1.0)),
        ),
        density_multiplier=0.22,
    ),
    # Fallout-grey column, near-white incandescent core flash. The brown-
    # orange NOx cap comes free from the fire's emission against grey smoke.
    "NUCLEAR": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.45, 0.43, 0.40, 1.0)),
            (0.45, (0.22, 0.19, 0.16, 1.0)),
            (1.0, (0.08, 0.07, 0.06, 1.0)),
        ),
        density_multiplier=0.30,
        flame_color=(1.0, 0.88, 0.62, 1.0),
        anisotropy=0.1,
    ),
}


def shading_for(explosion_type: str) -> ShadingConfig:
    """Return the stable shading configuration for an explosion type."""
    return SHADING.get(explosion_type, SHADING["FUEL"])


@dataclass(frozen=True)
class ExplosionProfile:
    """Scale-free description of one explosion type.

    Velocities ending in ``_U`` are multiples of ``U = sqrt(g*R)`` and times
    ending in ``_T`` are multiples of ``T = sqrt(R/g)``; lengths ending in
    ``_R`` are multiples of the fireball radius R. ``core.froude`` turns them
    into solver values, so a profile reads the same at any size and only
    its real-world timing changes (see docs/REALISM_PLAN.md).

    Combustion values (fuel, burning rate, buoyancy coefficients, ...) are
    Mantaflow settings of the reference-sized model and stay unscaled.
    """

    # Combustion and solver settings of the reference model.
    source_radius: float          # burst emitter radius, in R
    fuel_amount: float
    temperature: float
    density: float
    burning_rate: float
    flame_vorticity: float
    flame_smoke: float
    buoyancy_density: float
    buoyancy_heat: float
    turbulence: float
    noise_strength: float
    noise_scale: int
    flame_ignition: float = 1.5
    flow_heat: float = 0.90

    # Components and morphology.
    fireball: bool = True
    stem: bool = False
    ground_surge: bool = False
    # Ground-surge blasts fire at the ground: the lower cap's particles must
    # pour up instead of straight into the ground collider (which eats them).
    burst_flip_lower: bool = False

    # Default shot length (event seconds = event_T * T).
    event_T: float = 8.0
    # Smoke fade time (Mantaflow dissolve) in T. A physical property, so it
    # does not stretch when the shot gets longer; 0 = half of event_T.
    smoke_fade_T: float = 0.0
    # Domain envelope around the burst origin, in R. Voxel size and solver
    # time scale both follow from it, so it stays tight.
    envelope_lateral_R: float = 4.5
    envelope_top_R: float = 7.0
    envelope_bottom_R: float = 1.5

    # Fireball burst: particles leave the emitter at burst_speed_U and seed
    # fuel for burst_lifetime_T; speed x lifetime is the fuel's reach in R.
    burst_count: int = 1200
    burst_speed_U: float = 3.0
    burst_random_U: float = 1.5
    burst_emission_T: float = 0.3
    burst_lifetime_T: float = 0.3

    # Rising column.
    stem_speed_U: float = 1.0
    stem_feed_T: float = 2.0

    # Ground dust surge: cool (negative temperature) smoke spreading outward.
    dust_spread_U: float = 0.5
    dust_lift_U: float = 0.05
    dust_feed_T: float = 1.5
    dust_ring_T: float = 1.0
    dust_density_factor: float = 2.0
    dust_velocity_random: float = 0.65
    dust_temperature: float = -2.0

    # Shock-driven dust ring flow. A real shock crosses the scene in a few
    # frames, so the delay is short.
    shock_delay_T: float = 0.05
    shock_spread_U: float = 1.2
    shock_feed_T: float = 0.4

    # Visible ring and camera framing (cinematic layer).
    shockwave_radius_factor: float = 3.0
    shockwave_end_fraction: float = 1.0
    camera_distance_factor: float = 1.0

    def event_seconds(self, time_unit_s: float) -> float:
        """Default shot length in real (event) seconds."""
        return self.event_T * time_unit_s

    def smoke_fade_seconds(self, time_unit_s: float) -> float:
        """Real seconds over which smoke dissolves."""
        fade_T = self.smoke_fade_T if self.smoke_fade_T > 0 else 0.5 * self.event_T
        return fade_T * time_unit_s

    def burst_frames(self, time_unit_s: float, playback_speed: float, fps: float):
        """(emission_frames, particle_lifetime_frames, active_flow_frames).

        Windows are event times scaled into scene frames, so slow motion
        and size both stretch them consistently. Emission keeps at least one
        frame and lifetime two, so tiny fast blasts still seed fuel.
        """
        to_frames = max(1.0, float(fps)) / max(float(playback_speed), 1e-3)
        emission = max(1, int(round(self.burst_emission_T * time_unit_s * to_frames)))
        lifetime = max(2, int(round(self.burst_lifetime_T * time_unit_s * to_frames)))
        return emission, lifetime, emission + lifetime + 1


PROFILES = {
    # Grenade / charge-scale ground blast: fast, short, hard pop.
    "GROUND": ExplosionProfile(
        source_radius=0.45, fuel_amount=2.0, temperature=1.15, density=0.95,
        burning_rate=1.15, flame_vorticity=0.38, flame_smoke=1.25,
        buoyancy_density=1.0, buoyancy_heat=2.2, turbulence=1.05,
        noise_strength=0.8, noise_scale=1, flame_ignition=1.2, flow_heat=1.0,
        ground_surge=True, burst_flip_lower=True,
        event_T=8.0, envelope_lateral_R=4.0, envelope_top_R=6.0, envelope_bottom_R=1.0,
        burst_count=1400, burst_speed_U=4.0, burst_random_U=1.5,
        burst_emission_T=0.15, burst_lifetime_T=0.22,
        dust_spread_U=0.6, dust_feed_T=1.5,
        shock_spread_U=1.5,
        camera_distance_factor=2.0,
    ),
    # Fuel / vehicle: fuel-rich, slower burn, rolling soot.
    "FUEL": ExplosionProfile(
        source_radius=0.5, fuel_amount=2.5, temperature=1.35, density=1.25,
        burning_rate=0.32, flame_vorticity=0.78, flame_smoke=2.25,
        buoyancy_density=1.15, buoyancy_heat=2.7, turbulence=1.45,
        noise_strength=1.2, noise_scale=2, flame_ignition=1.5, flow_heat=0.9,
        event_T=9.0, envelope_lateral_R=4.5, envelope_top_R=7.0, envelope_bottom_R=1.5,
        burst_count=1800, burst_speed_U=3.0, burst_random_U=1.5,
        burst_emission_T=0.3, burst_lifetime_T=0.3,
        stem_speed_U=1.0, stem_feed_T=2.0,
        camera_distance_factor=2.2,
    ),
    # Large conventional ground blast: hot source, buoyant column, surge.
    "LARGE": ExplosionProfile(
        source_radius=0.5, fuel_amount=4.5, temperature=1.2, density=1.55,
        burning_rate=0.22, flame_vorticity=0.62, flame_smoke=2.7,
        buoyancy_density=1.3, buoyancy_heat=3.1, turbulence=1.65,
        noise_strength=1.4, noise_scale=2, flame_ignition=1.8, flow_heat=0.85,
        stem=True, ground_surge=True, burst_flip_lower=True,
        event_T=10.0, envelope_lateral_R=5.0, envelope_top_R=10.0, envelope_bottom_R=1.0,
        burst_count=2400, burst_speed_U=3.0, burst_random_U=1.5,
        burst_emission_T=0.3, burst_lifetime_T=0.3,
        stem_speed_U=1.2, stem_feed_T=2.5,
        dust_spread_U=0.6, dust_lift_U=0.03, dust_feed_T=2.0, dust_ring_T=1.2,
        dust_density_factor=0.8, dust_velocity_random=0.25, dust_temperature=-2.5,
        shock_spread_U=1.5, shock_feed_T=0.5,
        shockwave_radius_factor=6.0, camera_distance_factor=2.5,
    ),
    # Massive ground burst: long-burning fireball, heavy column, wide surge.
    "HEAVY": ExplosionProfile(
        source_radius=0.5, fuel_amount=6.0, temperature=1.5, density=1.6,
        burning_rate=1.2, flame_vorticity=0.35, flame_smoke=3.0,
        buoyancy_density=1.6, buoyancy_heat=3.6, turbulence=1.2,
        noise_strength=1.5, noise_scale=2, flame_ignition=2.0, flow_heat=1.4,
        stem=True, ground_surge=True, burst_flip_lower=True,
        event_T=10.0, envelope_lateral_R=5.5, envelope_top_R=11.0, envelope_bottom_R=1.0,
        burst_count=4000, burst_speed_U=3.5, burst_random_U=1.5,
        burst_emission_T=0.3, burst_lifetime_T=0.26,
        stem_speed_U=1.5, stem_feed_T=3.0,
        dust_spread_U=0.7, dust_lift_U=0.03, dust_feed_T=2.0, dust_ring_T=1.2,
        dust_density_factor=1.2, dust_velocity_random=0.30,
        shock_delay_T=0.04, shock_spread_U=1.8, shock_feed_T=0.5,
        shockwave_radius_factor=8.0, camera_distance_factor=3.0,
    ),
    # Trinity-style burst. Burst and stem speeds come from the old tuning at
    # its real size (14x / 12x of r/t at R = 86 m equal 2.6 U and 2.2 U),
    # which was a hand-made Froude scaling; windows likewise (48 / 80 frames
    # = 0.67 T / 1.12 T). Shock stays near the 5-psi relation (~3.7x R).
    "NUCLEAR": ExplosionProfile(
        source_radius=1.0, fuel_amount=5.0, temperature=1.5, density=1.6,
        burning_rate=0.22, flame_vorticity=0.35, flame_smoke=3.0,
        buoyancy_density=1.4, buoyancy_heat=3.4, turbulence=1.0,
        noise_strength=1.2, noise_scale=2, flame_ignition=2.2, flow_heat=1.3,
        stem=True, ground_surge=True, burst_flip_lower=True,
        event_T=5.4, envelope_lateral_R=5.4, envelope_top_R=6.0, envelope_bottom_R=1.5,
        burst_count=4000, burst_speed_U=2.6, burst_random_U=1.85,
        burst_emission_T=0.67, burst_lifetime_T=1.12,
        stem_speed_U=2.2, stem_feed_T=3.2,
        dust_spread_U=0.4, dust_lift_U=0.02, dust_feed_T=1.6, dust_ring_T=0.67,
        dust_density_factor=0.9, dust_velocity_random=0.25, dust_temperature=-2.5,
        shock_delay_T=0.1, shock_spread_U=1.2, shock_feed_T=0.5,
        shockwave_radius_factor=4.0, camera_distance_factor=5.5,
    ),
}


def profile_for(explosion_type: str) -> ExplosionProfile:
    """Return the stable profile for a Blender explosion type."""
    return PROFILES.get(explosion_type, PROFILES["FUEL"])


def profile_state(profile: ExplosionProfile) -> dict:
    """Return profile values suitable for the existing cache identity."""
    return asdict(profile)