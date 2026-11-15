"""One place that turns artist properties into a complete blast plan.

Create, Rebuild, the simulation builders and the animation rig all used to
repeat the derive-physics / profile / config / envelope sequence; they now
share this plan so they cannot drift apart. Pure Python: ``props`` and
``scene`` only need the attributes read here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .domain_envelope import build_domain_envelope
from .explosion_profile import ExplosionProfile, profile_for, shading_for
from .froude import time_unit
from .physics import (
    AmbientConditions,
    DerivedPhysics,
    PhysicalConfig,
    derive_physics,
    effective_scale_m,
    gravity_magnitude,
)
from .sim_config import SimulationConfig, build_simulation_config


@dataclass(frozen=True)
class BlastPlan:
    scale_m: float
    physical_config: PhysicalConfig
    physical: DerivedPhysics
    profile: ExplosionProfile
    numerical: SimulationConfig
    envelope: dict
    fps: float
    gravity: float
    # Scene seconds the shot spans (event seconds / playback speed).
    timeline_duration_s: float
    frame_start: int
    frame_end: int
    warnings: tuple = field(default_factory=tuple)

    @property
    def playback_speed(self) -> float:
        return self.numerical.playback_speed

    def event_frames(self, event_seconds: float) -> float:
        """Scene frames for a span of real event time (honours slow motion)."""
        return event_seconds / self.playback_speed * self.fps

    def config_dict(self, props) -> dict:
        """The dict the simulation/animation builders consume."""
        return {
            "type": props.explosion_type,
            "preset": props.preset_id,
            "scale": self.scale_m,
            "intensity": props.intensity,
            "speed": props.speed,
            "duration": props.duration,
            "start_frame": int(props.start_frame),
            "seed": props.seed,
            "quality": props.quality,
            "resolution": props.resolution,
            "noise": props.noise_upres,
            "turbulence": props.turbulence,
            "smoke_density": props.smoke_density,
            "fire_temperature": props.fire_temperature,
            "physical": self.physical,
            "numerical": self.numerical,
            "timeline_duration_s": self.timeline_duration_s,
            "profile": self.profile,
            "shading": shading_for(props.explosion_type),
            "domain_envelope": self.envelope,
            "plan": self,
            "_fps": self.fps,
        }


def plan_blast(props, scene) -> BlastPlan:
    gravity = gravity_magnitude(scene.gravity)
    fps = scene.render.fps / scene.render.fps_base
    scale_m = effective_scale_m(props)
    profile = profile_for(props.explosion_type)
    duration = float(props.duration)
    if duration <= 0.0:
        # Automatic: the profile's natural event length at this size, so a
        # resized blast is never cut off (or padded with empty frames).
        duration = profile.event_seconds(time_unit(scale_m * 0.5, gravity))
    physical_config = PhysicalConfig(
        scale_m=scale_m,
        reference_energy=float(props.reference_energy),
        intensity=float(props.intensity),
        duration_s=duration,
        ambient=AmbientConditions(gravity=gravity),
    )
    physical = derive_physics(physical_config)
    speed = max(float(props.speed), 0.05)
    timeline = physical.characteristic_time_s / speed
    numerical = build_simulation_config(
        physical,
        props.quality,
        props.resolution,
        props.noise_upres,
        props.seed,
        props.turbulence,
        props.smoke_density,
        props.fire_temperature,
        profile,
        timeline_duration_s=timeline,
        fps=fps,
        playback_speed=speed,
    )
    frame_start = int(props.start_frame)
    frame_end = frame_start + max(1, int(round(timeline * fps)))

    warnings = []
    if numerical.buoyancy_shortfall > 0.0:
        warnings.append(
            f"Blast is too large for exact Froude scaling: buoyancy is "
            f"{numerical.buoyancy_shortfall:.0%} short, so the plume rises "
            f"slower than real. Lower the playback speed or the size."
        )
    return BlastPlan(
        scale_m=scale_m,
        physical_config=physical_config,
        physical=physical,
        profile=profile,
        numerical=numerical,
        envelope=build_domain_envelope(physical, profile),
        fps=fps,
        gravity=gravity,
        timeline_duration_s=timeline,
        frame_start=frame_start,
        frame_end=frame_end,
        warnings=tuple(warnings),
    )
