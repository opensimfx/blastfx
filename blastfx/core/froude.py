"""Froude similarity: make a Mantaflow gas blast behave correctly at any size.

Mantaflow's gas solver is not scale-correct. Measured in Blender 5.2.3
(docs/REALISM_PLAN.md, section 1.1):

* Buoyancy coefficients are divided by the domain size in metres
  (``smoke_script.h``), so buoyant rise in metres collapses past a ~4 m
  domain: a 100 m domain rose 1 cm where a 4 m one rose 38 cm.
* ``velocity_coord`` and particle-sourced velocities are true m/s (they
  matched across resolution and domain size).
* ``velocity_normal`` is in grid units: its push shrinks as resolution
  rises and grows with the domain. ``v / (2.5 * voxel)`` converts m/s into
  it exactly (calibrated against ``velocity_coord``).

The fix is to simulate every blast as a reference-sized model and stretch
time. A buoyant flow of size S looks like one of size S0 replayed
sqrt(S/S0) times slower (Froude scaling), so the solver runs at
``time_scale = sqrt(S/S0)`` and every injected velocity is divided by the
same factor. A 40 m domain then matched the 4 m reference within 2 %.

Profiles therefore describe a blast in scale-free units: velocities in
multiples of ``U = sqrt(g*R)`` and times in multiples of ``T = sqrt(R/g)``
(R = fireball radius). The same profile then reads the same at 2 m and at
200 m; only the real-world timing changes, as it does in reality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Domain size whose Mantaflow buoyancy matches the reference model. The
# probe's rise was flat from 1 m to 4 m and fell beyond it.
REFERENCE_DOMAIN_M = 4.0
# Hard RNA limits in Blender 5.2 (FluidDomainSettings.time_scale, alpha, beta).
MAX_TIME_SCALE = 10.0
MIN_TIME_SCALE = 1e-4
MAX_BUOYANCY = 5.0
# Mantaflow's flow-velocity unit factor: DT_DEFAULT (0.1) at 25 fps.
_GRID_VELOCITY_FACTOR = 2.5


# Rates in profiles (burning rate, vorticity) are tuned for a 2 m-radius blast
# in an 8 R (16 m) domain at real time: the small preset's size.
RATE_REFERENCE_RADIUS_M = 2.0
_RATE_REFERENCE_DOMAIN_M = 8.0 * RATE_REFERENCE_RADIUS_M
_STANDARD_GRAVITY = 9.80665


def velocity_unit(radius_m: float, gravity: float) -> float:
    """U = sqrt(g*R): the speed scale of a buoyant fireball of radius R."""
    return math.sqrt(max(gravity, 1e-9) * max(radius_m, 1e-9))


def time_unit(radius_m: float, gravity: float) -> float:
    """T = sqrt(R/g): the time scale of a buoyant fireball of radius R."""
    return math.sqrt(max(radius_m, 1e-9) / max(gravity, 1e-9))


@dataclass(frozen=True)
class SolverScaling:
    """How one blast maps onto the Mantaflow solver.

    ``playback_speed`` is the shot's speed relative to real time: 0.5 plays
    the event at half speed (2x slow motion). Slow motion is the same time
    stretch as Froude scaling, so it folds into the same solver time scale.
    """

    domain_size_m: float
    playback_speed: float
    time_scale: float
    # Extra buoyancy needed when time_scale hits its limit (1.0 otherwise).
    buoyancy_gain: float

    @property
    def particle_velocity_factor(self) -> float:
        """FluidFlowSettings.velocity_factor for particle-sourced flows.

        Particles fly through the scene at real (playback) speed; the
        solver receives that speed divided by the time scale.
        """
        return 1.0 / self.time_scale

    def scene_velocity(self, event_mps: float) -> float:
        """Velocity in scene metres per scene second (particles, objects)."""
        return event_mps * self.playback_speed

    def flow_velocity(self, event_mps: float) -> float:
        """Value for FluidFlowSettings.velocity_coord (true m/s)."""
        return self.scene_velocity(event_mps) / self.time_scale

    def flow_normal_velocity(self, event_mps: float, voxel_size_m: float) -> float:
        """Value for FluidFlowSettings.velocity_normal (grid units)."""
        voxel = max(voxel_size_m, 1e-9)
        return self.flow_velocity(event_mps) / (_GRID_VELOCITY_FACTOR * voxel)

    def scene_frames(self, event_seconds: float, fps: float) -> float:
        """Scene frames covering ``event_seconds`` of the real event."""
        return event_seconds / self.playback_speed * fps

    def dissolve_frames(self, scene_frames: float) -> int:
        """Mantaflow dissolve_speed so smoke fades over ``scene_frames``.

        Dissolve runs per solver step, so a time scale k fades smoke k times
        faster per scene frame; the setting is scaled up to compensate.
        """
        return max(1, int(round(scene_frames * self.time_scale)))

    def solver_seconds_per_T(self, time_unit_s: float) -> float:
        """Unscaled solver time that passes during one T of the event.

        A T spans ``T / playback`` scene seconds and each runs ``time_scale``
        solver seconds, so playback cancels and only size remains.
        """
        return self.time_scale / self.playback_speed * max(time_unit_s, 1e-9)

    def rate_factor(self, time_unit_s: float) -> float:
        """Multiplier for per-solver-time rates (burning, vorticity).

        Solver time per T grows with size, so a fixed burning rate burned a
        40 m fireball out ~10x sooner (in T) than a 4 m one (measured). The
        factor holds rates per T constant, normalised so the reference
        blast (RATE_REFERENCE_RADIUS_M in an 8 R domain) is unchanged.
        """
        return _REFERENCE_SOLVER_SECONDS_PER_T / self.solver_seconds_per_T(time_unit_s)

    def buoyancy(self, coefficient: float) -> float:
        """Domain alpha/beta after the clamp top-up, inside the RNA range."""
        return max(-MAX_BUOYANCY, min(MAX_BUOYANCY, coefficient * self.buoyancy_gain))

    def buoyancy_shortfall(self, coefficient: float) -> float:
        """Fraction of the needed buoyancy the RNA limit could not deliver."""
        wanted = abs(coefficient * self.buoyancy_gain)
        if wanted <= MAX_BUOYANCY or wanted == 0.0:
            return 0.0
        return 1.0 - MAX_BUOYANCY / wanted


_REFERENCE_SOLVER_SECONDS_PER_T = math.sqrt(
    _RATE_REFERENCE_DOMAIN_M / REFERENCE_DOMAIN_M
) * time_unit(RATE_REFERENCE_RADIUS_M, _STANDARD_GRAVITY)


def solver_scaling(
    domain_size_m: float,
    playback_speed: float = 1.0,
    reference_m: float = REFERENCE_DOMAIN_M,
) -> SolverScaling:
    """Solver time scale for a domain whose longest side is ``domain_size_m``.

    Ideal: ``playback * sqrt(S / S0)``. Above the RNA limit the time scale
    clamps and buoyancy makes up the rest: Mantaflow's buoyant
    displacement goes as ``beta * time_scale**2``, so the needed gain is
    ``(ideal / clamped)**2``.
    """
    speed = max(float(playback_speed), 1e-3)
    size = max(float(domain_size_m), 1e-6)
    ideal = speed * math.sqrt(size / reference_m)
    clamped = max(MIN_TIME_SCALE, min(MAX_TIME_SCALE, ideal))
    return SolverScaling(
        domain_size_m=size,
        playback_speed=speed,
        time_scale=clamped,
        buoyancy_gain=(ideal / clamped) ** 2,
    )
