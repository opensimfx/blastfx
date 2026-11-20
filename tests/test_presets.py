import blastfx.presets.registry as registry
from blastfx.presets.apply import apply_preset
from blastfx.presets.registry import Preset


class FakeProps:
    def __init__(self, quality: str = "PREVIEW"):
        self.resolution = 64
        self.noise_upres = 1
        self.preset_id = ""
        self.explosion_type = ""
        self.use_stem = True
        self.quality = quality
        self.yield_kt = 1.0
        self.use_rapatronic = False
        self.use_debris = False
        self.use_dust = True


def _install(preset):
    registry.PRESETS = {preset.id: preset}


def test_builtin_resolution_key_applies():
    preset = Preset(
        id="t", label="t", description="", explosion_type="FUEL",
        simulation={"resolution": 220, "noise": 2},
    )
    _install(preset)
    props = FakeProps()
    apply_preset(props, "t")
    assert props.resolution == 220
    assert props.noise_upres == 2


def test_json_legacy_resolution_keys_apply():
    preset = Preset(
        id="t", label="t", description="", explosion_type="FUEL",
        simulation={"preview_resolution": 96, "final_resolution": 220, "noise": 2},
    )
    _install(preset)
    props = FakeProps()
    apply_preset(props, "t")
    assert props.resolution == 220

    preview_only = Preset(
        id="t2", label="t", description="", explosion_type="FUEL",
        simulation={"preview_resolution": 96},
    )
    _install(preview_only)
    props2 = FakeProps()
    apply_preset(props2, "t2")
    assert props2.resolution == 96


def test_draft_quality_pre_scales_resolution():
    preset = Preset(
        id="t", label="t", description="", explosion_type="FUEL",
        simulation={"resolution": 128},
    )
    _install(preset)
    draft = FakeProps(quality="DRAFT")
    apply_preset(draft, "t")
    assert draft.resolution == 64  # halved once here, not at build time
    preview = FakeProps(quality="PREVIEW")
    apply_preset(preview, "t")
    assert preview.resolution == 128


def test_heavy_builtin_preset_maps_profile():
    from blastfx.core.explosion_profile import profile_for

    # Earlier tests in this module swap the registry; reload the real one.
    registry.load_presets_from_directory()
    heavy = registry._builtin_presets()["heavy"]
    assert heavy.explosion_type == "HEAVY"
    assert heavy.components["debris"] is True

    props = FakeProps()
    apply_preset(props, "heavy")
    assert props.explosion_type == "HEAVY"
    # Factory presets no longer pin resolution: 0 = size-derived auto.
    assert props.resolution == 0
    assert profile_for("HEAVY").stem


def test_nuclear_builtin_presets_map_profile_and_components():
    from blastfx.core.explosion_profile import profile_for

    # Earlier tests in this module swap the registry; reload the real one.
    registry.load_presets_from_directory()

    airburst = registry._builtin_presets()["nuclear_airburst"]
    ground = registry._builtin_presets()["nuclear_groundburst"]
    assert airburst.explosion_type == "NUCLEAR"
    assert ground.explosion_type == "NUCLEAR"

    props = FakeProps()
    apply_preset(props, "nuclear_groundburst")
    assert props.explosion_type == "NUCLEAR"
    assert props.yield_kt == 15.0
    assert props.resolution == 0
    assert props.use_rapatronic is True
    assert props.use_debris is True

    air_props = FakeProps()
    apply_preset(air_props, "nuclear_airburst")
    assert air_props.use_rapatronic is True
    assert air_props.use_stem is False
    assert air_props.use_dust is False
    assert air_props.use_debris is False

    profile = profile_for("NUCLEAR")
    assert profile.stem and profile.ground_surge


def test_factory_presets_use_real_world_sizes():
    registry.load_presets_from_directory()
    builtins = registry._builtin_presets()
    sizes = [builtins[name].defaults["scale"] for name in ("small", "medium", "large", "large_ground", "heavy")]
    assert sizes == sorted(sizes) and sizes[0] >= 2.0
    for preset in builtins.values():
        assert 0.05 <= preset.defaults["speed"] <= 1.0
        assert "resolution" not in preset.simulation


def test_json_cannot_shadow_factory_presets(tmp_path):
    (tmp_path / "small.json").write_text(
        '{"id": "small", "label": "x", "type": "GROUND", "defaults": {"duration": 99}}'
    )
    registry.load_presets_from_directory(tmp_path)
    assert registry.PRESETS["small"].defaults["duration"] != 99
    registry.load_presets_from_directory()


def test_preset_without_resolution_clears_stale_override():
    preset = Preset(id="t", label="t", description="", explosion_type="FUEL", simulation={"noise": 2})
    _install(preset)
    props = FakeProps()
    props.resolution = 300
    apply_preset(props, "t")
    assert props.resolution == 0
    registry.load_presets_from_directory()


def test_saved_presets_round_trip_and_first_folder_wins(tmp_path, monkeypatch):
    user, legacy = tmp_path / "user", tmp_path / "legacy"
    registry.save_preset_to_json(Preset(id="mine", label="New", description="", explosion_type="FUEL"), user)
    registry.save_preset_to_json(Preset(id="mine", label="Old", description="", explosion_type="FUEL"), legacy)
    monkeypatch.setattr(registry, "_preset_dirs", lambda: [user, legacy])
    registry.load_presets_from_directory()
    assert registry.PRESETS["mine"].label == "New"
    monkeypatch.undo()
    registry.load_presets_from_directory()


def test_source_checkout_uses_repository_preset_folder():
    # Not installed as an extension (tests, development): the repo's presets/.
    assert not registry._installed()
    assert registry.user_preset_dir() == registry._LEGACY_PRESET_DIR


def test_version_comes_from_the_manifest():
    import tomllib
    from pathlib import Path
    from blastfx.core.version import VERSION

    manifest = tomllib.loads((Path(__file__).resolve().parents[1] / "blastfx" / "blender_manifest.toml").read_text())
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert VERSION == manifest["version"] == pyproject["project"]["version"]


# ------------------------------------------------------------ saved presets are files: names and contents are checked
def test_preset_ids_cannot_leave_the_preset_folder(tmp_path):
    import pytest
    from blastfx.presets.registry import Preset, is_valid_preset_id, save_preset_to_json

    assert is_valid_preset_id("my_blast_2")
    for bad in ("../evil", "a/b", "..", "", "Big Blast", "C:\\\\x", "x" * 49, None):
        assert not is_valid_preset_id(bad)
        with pytest.raises(ValueError):
            save_preset_to_json(Preset(id=bad, label="x", description="", explosion_type="FIREBALL"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_saved_presets_are_utf8_and_round_trip(tmp_path):
    from blastfx.presets import registry

    p = registry.Preset(id="ma_pr\u00e9", label="x", description="", explosion_type="FIREBALL")
    assert not registry.is_valid_preset_id(p.id)                       # ids stay ASCII ...
    p = registry.Preset(id="cafe_blast", label="Caf\u00e9 \u2013 \u7206\u767a", explosion_type="FIREBALL",
                        description="d\u00e9j\u00e0 vu", defaults={"scale": 2.0})
    registry.save_preset_to_json(p, tmp_path)                           # ... labels need not be
    raw = (tmp_path / "cafe_blast.json").read_bytes()
    assert "\u7206".encode("utf-8") in raw
    saved = dict(registry.PRESETS)
    try:
        registry.load_presets_from_directory(tmp_path)
        assert registry.PRESETS["cafe_blast"].label == p.label
    finally:
        registry.PRESETS.clear()
        registry.PRESETS.update(saved)


def test_preset_files_without_a_valid_id_are_skipped(tmp_path):
    from blastfx.presets import registry

    (tmp_path / "bad.json").write_text('{"id": "../x", "label": "x", "type": "FIREBALL"}', encoding="utf-8")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    saved = dict(registry.PRESETS)
    try:
        registry.load_presets_from_directory(tmp_path)
        assert "../x" not in registry.PRESETS
    finally:
        registry.PRESETS.clear()
        registry.PRESETS.update(saved)


def test_presets_only_set_their_own_settings():
    from types import SimpleNamespace
    from blastfx.presets import apply, registry

    preset = registry.Preset(id="sneaky", label="x", description="", explosion_type="FIREBALL",
                             defaults={"scale": 3.0, "cache_subdir": "../../elsewhere"},
                             components={"camera_fx": False})
    props = SimpleNamespace(preset_id="", explosion_type="", scale=1.0, cache_subdir="blastfx_cache",
                            use_camera_fx=True, quality="PREVIEW", resolution=0, noise_upres=0)
    registry.PRESETS["sneaky"] = preset
    try:
        apply.apply_preset(props, "sneaky")
    finally:
        del registry.PRESETS["sneaky"]
    assert props.scale == 3.0
    assert props.cache_subdir == "blastfx_cache"                       # not a preset setting
    assert props.use_camera_fx is False                                 # saved camera FX now applies
