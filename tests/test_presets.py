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
