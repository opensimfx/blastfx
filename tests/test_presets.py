import blastfx.presets.registry as registry
from blastfx.presets.apply import apply_preset
from blastfx.presets.registry import Preset


class FakeProps:
    def __init__(self):
        self.resolution = 64
        self.noise_upres = 1
        self.preset_id = ""
        self.explosion_type = ""
        self.use_stem = True


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
