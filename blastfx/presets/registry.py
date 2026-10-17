import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    description: str
    explosion_type: str
    defaults: Dict[str, object] = field(default_factory=dict)
    components: Dict[str, bool] = field(default_factory=dict)
    simulation: Dict[str, object] = field(default_factory=dict)


PRESETS = {}


def _builtin_presets() -> Dict[str, Preset]:
    return {
        "small": Preset(
            id="small",
            label="Small Blast",
            description="Small conventional explosion.",
            explosion_type="GROUND",
            defaults={"scale": 1.0, "intensity": 1.0, "speed": 1.0, "duration": 5.0},
            components={"fireball": True, "stem": False, "dust": False, "shockwave": True, "flash": True},
            simulation={"resolution": 128, "noise": 1},
        ),
        "medium": Preset(
            id="medium",
            label="Fuel / Vehicle Explosion",
            description="Medium ground explosion with base surge.",
            explosion_type="FUEL",
            defaults={"scale": 1.0, "intensity": 1.0, "speed": 1.0, "duration": 8.0},
            components={"fireball": True, "stem": False, "dust": True, "shockwave": True, "flash": True},
            simulation={"resolution": 220, "noise": 2},
        ),
        "large": Preset(
            id="large",
            label="Medium Ground Blast",
            description="Ground blast using the medium explosion profile.",
            explosion_type="FUEL",
            defaults={"scale": 1.0, "intensity": 1.0, "speed": 1.0, "duration": 14.0},
            components={"fireball": True, "stem": True, "dust": True, "shockwave": True, "flash": True},
            simulation={"resolution": 256, "noise": 2},
        ),
        "large_ground": Preset(
            id="large_ground",
            label="Large Ground Blast",
            description="Large conventional blast with rising column.",
            explosion_type="LARGE",
            defaults={"scale": 1.0, "intensity": 1.0, "speed": 1.0, "duration": 24.0},
            components={"fireball": True, "stem": True, "dust": True, "shockwave": True, "flash": True},
            simulation={"resolution": 256, "noise": 2},
        ),
    }


def load_presets_from_directory(preset_dir: Optional[Path] = None):
    """Load presets from JSON files in the preset directory."""
    global PRESETS
    PRESETS = _builtin_presets()

    if preset_dir is None:
        preset_dir = Path(__file__).parent.parent.parent / "presets"

    if not preset_dir.exists():
        return

    for json_file in preset_dir.glob("*.json"):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            preset = Preset(
                id=data["id"],
                label=data["label"],
                description=data.get("description", ""),
                explosion_type=data["type"],
                defaults=data.get("defaults", {}),
                components=data.get("components", {}),
                simulation=data.get("simulation", {}),
            )
            PRESETS[preset.id] = preset
        except Exception as e:
            print(f"[BlastFX] Failed to load preset {json_file}: {e}")


def save_preset_to_json(preset: Preset, preset_dir: Optional[Path] = None):
    """Save a preset to a JSON file."""
    if preset_dir is None:
        preset_dir = Path(__file__).parent.parent.parent / "presets"

    preset_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "id": preset.id,
        "label": preset.label,
        "description": preset.description,
        "type": preset.explosion_type,
        "defaults": preset.defaults,
        "components": preset.components,
        "simulation": preset.simulation,
    }

    filepath = preset_dir / f"{preset.id}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# Initialize on import
load_presets_from_directory()


def get_preset(preset_id: str) -> Preset:
    return PRESETS[preset_id]


def all_presets():
    return tuple(PRESETS.values())
