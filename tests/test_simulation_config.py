from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blastfx.core.physics import PhysicalConfig, derive_physics
_SPEC = spec_from_file_location(
    "blastfx_simulation_physical_config",
    Path(__file__).resolve().parents[1] / "blastfx" / "simulation" / "physical_config.py",
)
_MODULE = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
build_simulation_config = _MODULE.build_simulation_config


def test_quality_changes_resolution_not_physical_values():
    physical = derive_physics(
        PhysicalConfig(scale_m=10.0, reference_energy=1.0, intensity=2.0, duration_s=5.0)
    )
    draft = build_simulation_config(physical, "DRAFT", 128, 1, 7)
    final = build_simulation_config(physical, "FINAL", 128, 2, 7)

    assert draft.domain_resolution < final.domain_resolution
    assert draft.characteristic_velocity_mps == final.characteristic_velocity_mps
    assert draft.seed == final.seed == 7


def test_artist_simulation_controls_reach_derived_configuration():
    physical = derive_physics(
        PhysicalConfig(scale_m=10.0, reference_energy=1.0, intensity=1.0, duration_s=5.0)
    )
    config = build_simulation_config(
        physical,
        "PREVIEW",
        128,
        1,
        3,
        turbulence=2.0,
        smoke_density=2.0,
        fire_temperature=2.0,
    )

    assert config.turbulence_strength > 0.7
    assert config.density_scale == 2.0
    assert config.temperature_scale > 3.0
