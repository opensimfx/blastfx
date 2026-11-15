"""Physically informed, deterministic VFX profiles for each explosion type."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShadingConfig:
    """Scale-free volume shading for one explosion type (Phase B).

    Smoke: the Mantaflow density grid sets the extinction, normalised by the
    fireball radius so ``optical_depth`` is the depth across one radius of
    grid-density-1 smoke at any size (Cycles density is per metre, so a fixed
    multiplier made small blasts see-through and big ones opaque). The
    ColorRamp maps density to scattering albedo: thin edges scatter, dense
    soot mostly absorbs, but never below ~0.05 so the fire can light it.

    Fire: the flame grid maps linearly onto ``fire_temperature_k`` and a
    Blackbody node colours the emission (white-hot core, orange body, deep
    red edges). Emission is extinction x brightness x flame**fire_gamma
    (Kirchhoff), so ``fire_brightness`` is the radiance of an optically
    thick, fully burning core at any size. Mantaflow density runs ~0-3 in
    these blasts (measured), hence the ramp gain.
    """
    smoke_ramp: tuple  # ((density x ramp_gain, rgba albedo), ...) ascending
    optical_depth: float = 8.0
    ramp_gain: float = 0.35
    fire_temperature_k: tuple = (900.0, 2600.0)
    fire_brightness: float = 28.0
    fire_gamma: float = 1.5
    # How much a fully burning cell darkens the smoke albedo (0-1).
    burning_soot: float = 0.9
    # Fire grade applied only under AgX (Blender's default view), which turns
    # raw blackbody orange salmon-pink at any exposure and bleaches bright
    # emission (measured against Filmic on the same bake). Filmic and other
    # views get the raw blackbody colour and full brightness.
    agx_hue_shift: float = 0.02
    agx_saturation: float = 1.6
    agx_brightness: float = 0.3
    anisotropy: float = 0.15
    # Fire light (animation/flash.py): glow length in T and colour temperature.
    fire_light_T: float = 2.0
    fire_light_k: float = 1900.0

    def as_dict(self):
        return asdict(self)


SHADING = {
    # High-explosive charge: hot short flash, brown earth-laden smoke.
    "GROUND": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.40, 0.33, 0.26, 1.0)),
            (0.2, (0.24, 0.19, 0.14, 1.0)),
            (0.6, (0.10, 0.08, 0.06, 1.0)),
            (1.0, (0.05, 0.042, 0.035, 1.0)),
        ),
        optical_depth=7.0,
        fire_temperature_k=(1250.0, 3000.0),
        fire_brightness=35.0,
        fire_light_T=1.2,
        fire_light_k=2200.0,
    ),
    # Petroleum fire: the darkest, sootiest smoke and the coolest, most
    # orange flame.
    "FUEL": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.30, 0.28, 0.26, 1.0)),
            (0.2, (0.14, 0.13, 0.12, 1.0)),
            (0.6, (0.06, 0.055, 0.05, 1.0)),
            (1.0, (0.035, 0.032, 0.03, 1.0)),
        ),
        optical_depth=10.0,
        fire_temperature_k=(1100.0, 2500.0),
        fire_brightness=25.0,
        fire_light_T=2.5,
        fire_light_k=1800.0,
    ),
    "LARGE": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.38, 0.35, 0.31, 1.0)),
            (0.2, (0.20, 0.18, 0.155, 1.0)),
            (0.6, (0.08, 0.07, 0.06, 1.0)),
            (1.0, (0.045, 0.04, 0.036, 1.0)),
        ),
        optical_depth=8.0,
        fire_temperature_k=(1150.0, 2700.0),
        fire_light_T=3.0,
    ),
    "HEAVY": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.30, 0.26, 0.22, 1.0)),
            (0.2, (0.15, 0.13, 0.11, 1.0)),
            (0.6, (0.06, 0.052, 0.045, 1.0)),
            (1.0, (0.035, 0.032, 0.029, 1.0)),
        ),
        optical_depth=9.0,
        fire_temperature_k=(1150.0, 2800.0),
        fire_light_T=4.0,
    ),
    # Fallout-grey column with a near-white incandescent core; the brown-
    # orange cap comes from the cooler flame edges against grey smoke.
    "NUCLEAR": ShadingConfig(
        smoke_ramp=(
            (0.0, (0.55, 0.53, 0.50, 1.0)),
            (0.45, (0.32, 0.30, 0.27, 1.0)),
            (1.0, (0.16, 0.15, 0.14, 1.0)),
        ),
        optical_depth=6.0,
        # Preview review: 1800-6500 K at 60 kept the fireball white past 2 T.
        fire_temperature_k=(1500.0, 5000.0),
        fire_brightness=35.0,
        anisotropy=0.2,
        fire_light_T=2.0,
        fire_light_k=4500.0,
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
    # Closed domain top: the plume spreads under it like a mushroom cap at its
    # stabilisation altitude instead of being sliced off by the open border.
    ceiling: bool = False

    # Fireball burst: particles leave the emitter at burst_speed_U and seed
    # fuel for burst_lifetime_T; speed x lifetime is the fuel's reach in R.
    burst_count: int = 1200
    burst_speed_U: float = 3.0
    burst_random_U: float = 1.5
    burst_emission_T: float = 0.3
    burst_lifetime_T: float = 0.3

    # Rising column: starts once the fireball has lifted (a column fed from
    # frame 1 rendered as a black chimney standing in the fireball). It is
    # mostly buoyant hot smoke with a gentle push: an imposed jet of ~1 U
    # shed regular horizontal sheets (measured banding at 1.2 U, faint at
    # 0.5 U, none when buoyancy alone drives it).
    stem_speed_U: float = 0.25
    stem_feed_T: float = 2.0
    stem_delay_T: float = 0.5

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
    # Time for the raised-dust ring to sweep out to full size; matches the
    # default feed so the ring is still emitting when it reaches full size.
    shock_sweep_T: float = 0.4

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
        stem_speed_U=0.25, stem_feed_T=2.0,
        camera_distance_factor=2.2,
    ),
    # Large conventional ground blast: hot source, buoyant column, surge.
    "LARGE": ExplosionProfile(
        # Preview review: burning 0.22 / fuel 4.5 kept the whole cloud glowing
        # peach through 2 T; real large blasts go dark with pockets of fire.
        source_radius=0.5, fuel_amount=3.5, temperature=1.2, density=1.55,
        burning_rate=0.45, flame_vorticity=0.62, flame_smoke=2.7,
        buoyancy_density=1.3, buoyancy_heat=3.1, turbulence=1.65,
        noise_strength=1.4, noise_scale=2, flame_ignition=1.8, flow_heat=0.85,
        stem=True, ground_surge=True, burst_flip_lower=True,
        event_T=10.0, envelope_lateral_R=5.0, envelope_top_R=10.0, envelope_bottom_R=1.0,
        burst_count=2400, burst_speed_U=3.0, burst_random_U=1.5,
        burst_emission_T=0.3, burst_lifetime_T=0.3,
        stem_speed_U=0.25, stem_feed_T=2.5,
        dust_spread_U=0.6, dust_lift_U=0.03, dust_feed_T=2.0, dust_ring_T=1.2,
        dust_density_factor=0.8, dust_velocity_random=0.25, dust_temperature=-2.5,
        shock_spread_U=1.5, shock_feed_T=0.5,
        shockwave_radius_factor=6.0, camera_distance_factor=2.5,
    ),
    # Massive ground burst: long-burning fireball, heavy column, wide surge.
    "HEAVY": ExplosionProfile(
        # Preview review: burning 1.2 burned this "long-burning" burst out by
        # 2 T with pale smoke; slower burn, more soot.
        source_radius=0.5, fuel_amount=6.0, temperature=1.5, density=1.6,
        burning_rate=0.4, flame_vorticity=0.35, flame_smoke=3.6,
        buoyancy_density=1.6, buoyancy_heat=3.6, turbulence=1.2,
        noise_strength=1.5, noise_scale=2, flame_ignition=2.0, flow_heat=1.4,
        stem=True, ground_surge=True, burst_flip_lower=True,
        event_T=10.0, envelope_lateral_R=5.5, envelope_top_R=11.0, envelope_bottom_R=1.0,
        burst_count=4000, burst_speed_U=3.5, burst_random_U=1.5,
        burst_emission_T=0.3, burst_lifetime_T=0.26,
        stem_speed_U=0.3, stem_feed_T=3.0,
        dust_spread_U=0.7, dust_lift_U=0.03, dust_feed_T=2.0, dust_ring_T=1.2,
        dust_density_factor=1.2, dust_velocity_random=0.30,
        shock_delay_T=0.04, shock_spread_U=1.8, shock_feed_T=0.5,
        shockwave_radius_factor=8.0, camera_distance_factor=3.0,
    ),
    # Trinity-style burst. Burst speed comes from the old tuning at its real
    # size (14x r/t at R = 86 m = 2.6 U, a hand-made Froude scaling); windows
    # likewise (48 / 80 frames = 0.67 T / 1.12 T). The old 2.2 U stem jet is
    # cut to 0.5 U now that buoyancy works (jets band, see stem_speed_U). Shock stays near the 5-psi relation (~3.7x R).
    "NUCLEAR": ExplosionProfile(
        # Preview review: fuel 5.0 kept the core white-hot past 2 T (6 s).
        source_radius=1.0, fuel_amount=3.5, temperature=1.5, density=1.6,
        burning_rate=0.22, flame_vorticity=0.35, flame_smoke=3.0,
        buoyancy_density=1.4, buoyancy_heat=3.4, turbulence=1.0,
        noise_strength=1.2, noise_scale=2, flame_ignition=2.2, flow_heat=1.3,
        stem=True, ground_surge=True, burst_flip_lower=True,
        # Slimmer domain (was 5.4 R lateral, 932 m): the time scale clamps at 10
        # beyond ~400 m and buoyancy then falls short (30 % before, ~8 % now),
        # which left the cloud squat with no rise. Less random burst spread
        # tames the spikes.
        event_T=5.4, envelope_lateral_R=3.5, envelope_top_R=6.0, envelope_bottom_R=1.5, ceiling=True,
        burst_count=4000, burst_speed_U=2.6, burst_random_U=1.0,
        burst_emission_T=0.67, burst_lifetime_T=1.12,
        stem_speed_U=0.5, stem_feed_T=3.2,
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