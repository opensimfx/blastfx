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
    """Factory presets at real-world sizes.

    ``scale`` is the fireball diameter in metres, ``duration`` the real event
    time the shot covers and ``speed`` the playback speed (0.5 = 2x slow
    motion, as practical explosions are shot at high frame rates). Timing
    follows Froude scaling from the size (core.froude), so shot lengths sit
    near the profile's ``event_T``. Resolution is not pinned: it derives
    from the size per quality tier (sim_config.VOXELS_PER_RADIUS).
    """
    return {
        "small": Preset(
            id="small",
            label="Small Blast",
            description="Charge-scale ground blast, 4 m fireball, 2x slow motion.",
            explosion_type="GROUND",
            defaults={"scale": 4.0, "intensity": 1.0, "speed": 0.5, "duration": 3.5},
            components={"fireball": True, "stem": False, "dust": False, "shockwave": True, "flash": True},
            simulation={"noise": 1},
        ),
        "medium": Preset(
            id="medium",
            label="Fuel / Vehicle Explosion",
            description="Vehicle fuel explosion, 10 m fireball with base surge.",
            explosion_type="FUEL",
            defaults={"scale": 10.0, "intensity": 1.0, "speed": 0.75, "duration": 6.0},
            components={"fireball": True, "stem": False, "dust": True, "shockwave": True, "flash": True},
            simulation={"noise": 2},
        ),
        "large": Preset(
            id="large",
            label="Medium Ground Blast",
            description="20 m fuel-rich ground blast with a rising column.",
            explosion_type="FUEL",
            defaults={"scale": 20.0, "intensity": 1.0, "speed": 1.0, "duration": 9.0},
            components={"fireball": True, "stem": True, "dust": True, "shockwave": True, "flash": True},
            simulation={"noise": 2},
        ),
        "large_ground": Preset(
            id="large_ground",
            label="Large Ground Blast",
            description="40 m conventional blast with rising column and ground surge.",
            explosion_type="LARGE",
            defaults={"scale": 40.0, "intensity": 1.0, "speed": 1.0, "duration": 10.0},
            components={"fireball": True, "stem": True, "dust": True, "shockwave": True, "flash": True},
            simulation={"noise": 2},
        ),
        "heavy": Preset(
            id="heavy",
            label="Heavy Ground Burst",
            description="80 m massive ground burst: long-burning fireball, heavy column, dust surge, debris.",
            explosion_type="HEAVY",
            defaults={"scale": 80.0, "intensity": 1.0, "speed": 1.0, "duration": 12.0},
            components={"fireball": True, "stem": True, "dust": True, "shockwave": True, "flash": True, "debris": True},
            simulation={"noise": 2},
        ),
        "nuclear_airburst": Preset(
            id="nuclear_airburst",
            label="Nuclear Air Burst (15 kt)",
            description="Air-detonated nuclear burst; place the 3D cursor at the burst height. Yield prop drives the diameter.",
            explosion_type="NUCLEAR",
            defaults={"scale": 1.0, "intensity": 1.0, "speed": 1.0, "duration": 14.0, "yield_kt": 15.0},
            components={
                "fireball": True, "stem": False, "dust": False, "shockwave": True,
                "flash": True, "rapatronic": True,
            },
            simulation={"noise": 2},
        ),
        "nuclear_groundburst": Preset(
            id="nuclear_groundburst",
            label="Nuclear Ground Burst (15 kt)",
            description="Trinity-style surface nuclear burst with fallout column, dust surge and debris.",
            explosion_type="NUCLEAR",
            defaults={"scale": 1.0, "intensity": 1.0, "speed": 1.0, "duration": 16.0, "yield_kt": 15.0},
            components={
                "fireball": True, "stem": True, "dust": True, "shockwave": True,
                "flash": True, "rapatronic": True, "debris": True,
            },
            simulation={"noise": 2},
        ),
    }


# Saved presets. Installed as an extension the package is
# ``bl_ext.<repo>.blastfx`` and presets go to the add-on's user data folder
# (bpy.utils.extension_path_user): writable, kept across updates and outside
# the extension's own files, as Blender's extension rules require. Run from
# source (tests, development) they stay in the repository's presets/ folder.
_PACKAGE = (__package__ or "blastfx").rsplit(".", 1)[0]
# 0.2 and 0.3 saved presets next to the add-on folder (inside Blender's
# extension repository); they are still loaded so nobody loses one.
_LEGACY_PRESET_DIR = Path(__file__).parent.parent.parent / "presets"


def _installed() -> bool:
    return _PACKAGE.startswith("bl_ext.")


def user_preset_dir() -> Path:
    """Folder that Save as Preset writes to and the preset menu reads from."""
    if _installed():
        try:
            import bpy

            return Path(bpy.utils.extension_path_user(_PACKAGE, path="presets", create=True))
        except Exception as exc:  # e.g. imported before Blender is ready
            print(f"[BlastFX] No user preset folder ({exc}); saved presets are unavailable this session.")
    return _LEGACY_PRESET_DIR


def _preset_dirs():
    dirs = [user_preset_dir()]
    if _installed() and _LEGACY_PRESET_DIR.exists() and _LEGACY_PRESET_DIR not in dirs:
        dirs.append(_LEGACY_PRESET_DIR)
    return dirs


def load_presets_from_directory(preset_dir: Optional[Path] = None):
    """Load factory presets plus saved JSON presets (``preset_dir``, or the user folders)."""
    global PRESETS
    PRESETS = _builtin_presets()
    factory = set(PRESETS)

    dirs = [preset_dir] if preset_dir is not None else _preset_dirs()
    for json_file in (f for d in dirs if d.exists() for f in sorted(d.glob("*.json"))):
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
            if preset.id in factory:
                # Factory presets win: a stale JSON copy (e.g. the old
                # 24 s large_ground.json) must not silently replace them.
                print(f"[BlastFX] Ignoring {json_file.name}: '{preset.id}' is a factory preset id")
                continue
            # The first folder wins: the user folder over the legacy one.
            PRESETS.setdefault(preset.id, preset)
        except Exception as e:
            print(f"[BlastFX] Failed to load preset {json_file}: {e}")


def save_preset_to_json(preset: Preset, preset_dir: Optional[Path] = None):
    """Save a preset to a JSON file."""
    if preset_dir is None:
        preset_dir = user_preset_dir()

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
