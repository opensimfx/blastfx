"""Ground collider geometry and profiles (plan Phase 4)."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blastfx.core.explosion_profile import profile_for

_SPEC = spec_from_file_location(
    "blastfx_simulation_ground",
    Path(__file__).resolve().parents[1] / "blastfx" / "simulation" / "ground.py",
)
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
ground_top_z = _MODULE.ground_top_z


class FakeController:
    """Controller empty standing at world origin +Z."""

    location = (0.0, 0.0, 0.0)


def test_ground_sits_at_origin_for_ground_surge_profiles():
    for type_name in ("GROUND", "LARGE"):
        config = {
            "profile": profile_for(type_name),
            "domain_envelope": {"min": [-4.0, -4.0, -8.0]},
        }
        assert ground_top_z(config, FakeController) == 0.0


def test_airburst_floor_is_envelope_bottom():
    config = {
        "profile": profile_for("FUEL"),
        "domain_envelope": {"min": [-4.0, -4.0, -8.0]},
    }
    controller = FakeController()
    controller.location = (0.0, 0.0, 3.0)
    assert ground_top_z(config, controller) == 3.0 - 8.0
