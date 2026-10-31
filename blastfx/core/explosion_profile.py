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
    source_radius: float
    source_duration: float
    fuel_amount: float
    temperature: float
    density: float
    velocity_factor: float
    velocity_random: float
    burning_rate: float
    flame_vorticity: float
    flame_smoke: float
    buoyancy_density: float
    buoyancy_heat: float
    turbulence: float
    noise_strength: float
    noise_scale: int
    smoke_dissipation: float
    expansion_factor: float
    fireball: bool = True
    stem: bool = False
    ground_surge: bool = False
    shockwave_delay: float = 0.0
    shockwave_radius_factor: float = 3.0
    shockwave_end_fraction: float = 1.0
    camera_distance_factor: float = 1.0
    dust_duration_factor: float = 0.35
    dust_density_factor: float = 2.0
    dust_velocity_random: float = 0.65
    dust_velocity_normal_factor: float = 0.30
    dust_temperature: float = -2.0
    flame_ignition: float = 1.5
    flow_heat: float = 0.90
    burst_count: int = 1200
    burst_normal_velocity: float = 4.5
    burst_random_velocity: float = 4.5
    # 0 = derive the window from source_duration at scene fps (burst_timing).
    burst_emission_frames: int = 0
    burst_lifetime_frames: int = 0
    # Ground-surge blasts fire at the ground: the reflected blast turns the
    # bottom half upward, so the lower cap's particles must pour up instead
    # of straight into the ground collider (which eats them).
    burst_flip_lower: bool = False
    # Stem rise speed as a multiple of the characteristic velocity (r/t).
    # Long timelines shrink that velocity, so profiles needing a mushroom
    # raise this; 0.8 keeps the historical behaviour of short blasts.
    stem_velocity_factor: float = 0.8

    def burst_timing(self, fps: float):
        """(emission_frames, particle_lifetime_frames, active_flow_frames).

        Expert benchmark (Iridesium 2.m82+ / CrossMind 7): the fuel burst
        fires over 1-5 frames; short-lived fast particles keep injecting
        smoke only while they travel, then the flow closes (start 10 -> end
        14-15, life 5-7 at 24 fps). Profiles with explicit frame overrides
        bypass the duration derivation.
        """
        fps = max(1.0, float(fps))
        emission = (
            self.burst_emission_frames
            if self.burst_emission_frames > 0
            else max(2, min(5, int(round(fps * self.source_duration * 0.35))))
        )
        lifetime = (
            self.burst_lifetime_frames
            if self.burst_lifetime_frames > 0
            else max(3, int(round(fps * self.source_duration * 0.3)))
        )
        return emission, lifetime, emission + lifetime + 1


PROFILES = {
    "GROUND": ExplosionProfile(
        # fuel_amount (3rd value) matrix-probed in
        # examples/burst_probe/matrix_D_flip_fuel: 0.75 starves the flame
        # grid by ~f010; 2.0 keeps the fireball burning past f014.
        0.72, 0.10, 2.0, 1.15, 0.95, 1.5, 0.32, 1.15, 0.38, 1.25,
        1.0, 2.2, 1.05, 0.8, 1, 0.8, 1.15, ground_surge=True, shockwave_delay=0.12,
        camera_distance_factor=2.0,
        flame_ignition=1.2, flow_heat=1.0,
        burst_count=1400, burst_normal_velocity=5.0, burst_random_velocity=3.5,
        # Proportional shortest fire: 6/14 keeps the small blast's burn
        # ≈ 1.5-2 s (small blast = shortest, per the size-scaling ask).
        burst_emission_frames=6, burst_lifetime_frames=14, burst_flip_lower=True,
    ),
    "FUEL": ExplosionProfile(
        1.0, 1.25, 2.5, 1.35, 1.25, 1.15, 0.6, 0.32, 0.78, 2.25,
        1.15, 2.7, 1.45, 1.2, 2, 2.2, 1.4, shockwave_delay=0.18,
        camera_distance_factor=2.2,
        flame_ignition=1.5, flow_heat=0.9,
        burst_count=1800, burst_normal_velocity=4.5, burst_random_velocity=4.5,
        # Burn matrix variant B (/var 24/28 windows): visible fire ≈ 3 s.
        burst_emission_frames=24, burst_lifetime_frames=28,
    ),
    "LARGE": ExplosionProfile(
        # fuel 4.5 + burn 0.22 from burn-matrix variant D (fire ≈ 5 s):
        # slower burn + more injected fuel stretches visible flame past
        # ~f96-120 at 24 fps instead of the old 1 s flash.
        1.45, 0.56, 4.5, 1.2, 1.55, 1.08, 0.48, 0.22, 0.62, 2.7,
        1.3, 3.1, 1.65, 1.4, 2, 2.8, 1.9, stem=True, ground_surge=True,
        shockwave_delay=0.16, shockwave_radius_factor=6.0,
        camera_distance_factor=2.5,
        dust_duration_factor=0.85, dust_density_factor=0.8,
        dust_velocity_random=0.25, dust_velocity_normal_factor=0.12,
        dust_temperature=-2.5,
        flame_ignition=1.8, flow_heat=0.85,
        burst_count=2400, burst_normal_velocity=4.0, burst_random_velocity=5.0,
        burst_flip_lower=True,  # same ground-surge logic as GROUND
        burst_emission_frames=36, burst_lifetime_frames=48,
    ),
    "HEAVY": ExplosionProfile(
        # Massive ground burst: ground-burst fireballs burn 1-3 s (vs
        # 2-5 s airbursts) — long override windows keep fuel injecting for
        # ~1.5 s at 24 fps while the enormous column rolls up.
        2.2, 0.60, 6.0, 1.5, 1.6, 1.25, 0.5, 1.2, 0.35, 3.0,
        1.6, 3.6, 1.2, 1.5, 2, 2.0, 2.2, stem=True, ground_surge=True,
        shockwave_delay=0.10, shockwave_radius_factor=8.0,
        camera_distance_factor=3.0,
        dust_duration_factor=1.2, dust_density_factor=1.2,
        dust_velocity_random=0.30, dust_velocity_normal_factor=0.15,
        flame_ignition=2.0, flow_heat=1.4,
        burst_count=4000, burst_normal_velocity=5.5, burst_random_velocity=4.0,
        burst_emission_frames=36, burst_lifetime_frames=40, burst_flip_lower=True,
    ),
    # Trinity-style ground burst. The glitch/cap rolls up through the first
    # seconds; stem + surge hand that to the solver. Fire ~5 s visible
    # (48-frame injection + 80-frame particle tail) fits the 14-16 s ring.
    # Shockwave stays near the 5-psi relation (~3.7x fireball radius).
    "NUCLEAR": ExplosionProfile(
        1.0, 0.5, 5.0, 1.5, 1.6, 1.2, 0.5, 0.22, 0.35, 3.0,
        1.4, 3.4, 1.0, 1.2, 2, 2.0, 0.9, stem=True, ground_surge=True,
        # expansion 0.6 keeps the domain ~3.6x the 15 kt fireball (2.4 gave a
        # 2.5 km domain at ~44 m voxels: fireball collapsed to a dim speck)
        # but 0.6 is still tight enough that a cinematic camera parked
        # outside the box shows a fog-cut wall seam; 0.9 (~466 m half-width)
        # admits the ~5.5-radii camera while presets at res 256 keep
        # ~3.6 m voxels. Burning 0.22/fuel 5.0 mirrors the LARGE recipe
        # for the >=5 s fire.
        shockwave_delay=0.14, shockwave_radius_factor=4.0,
        camera_distance_factor=5.5,
        # A cold dust sheet fed for the whole 16 s timeline drowned the stem in
        # a flat pancake (64-res probe, Oct 20): feed it ~5 s instead, lighter
        # and with less lateral push so the column can establish.
        dust_duration_factor=0.3, dust_density_factor=0.9,
        dust_velocity_random=0.25, dust_velocity_normal_factor=0.12,
        dust_temperature=-2.5,
        flame_ignition=2.2, flow_heat=1.3,
        # Burst velocity = multiplier x radius/timeline (5.4 m/s at 16 s), so
        # profile values must be large to keep a real upward punch; 4.5/5.5
        # collapsed the blast into a ground-hugging pancake at 64 res.
        # A 16 s timeline otherwise caps every flow at ~5 m/s and the plume
        # can never rise into a stem+cap silhouette, so the stem is driven at
        # 12x (65 m/s) and the burst kick raised to 14x/10x.
        burst_count=4000, burst_normal_velocity=14.0, burst_random_velocity=10.0,
        burst_emission_frames=48, burst_lifetime_frames=80, burst_flip_lower=True,
        stem_velocity_factor=12.0,
    ),
}


def profile_for(explosion_type: str) -> ExplosionProfile:
    """Return the stable profile for a Blender explosion type."""
    return PROFILES.get(explosion_type, PROFILES["FUEL"])


def profile_state(profile: ExplosionProfile) -> dict:
    """Return profile values suitable for the existing cache identity."""
    return asdict(profile)