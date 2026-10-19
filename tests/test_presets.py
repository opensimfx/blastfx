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
    assert props.resolution == 256

    profile = profile_for("HEAVY")
    assert profile.burst_emission_frames == 36
    assert profile.burst_lifetime_frames == 40
