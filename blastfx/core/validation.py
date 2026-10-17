from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str):
        self.errors.append(message)
        self.ok = False

    def add_warning(self, message: str):
        self.warnings.append(message)


def validate_props(props) -> ValidationResult:
    result = ValidationResult(ok=True)

    try:
        from ..presets.registry import get_preset
        get_preset(props.preset_id)
    except Exception:
        result.add_error(f"Unknown preset: {props.preset_id}")

    if props.scale <= 0:
        result.add_error("Scale must be greater than zero.")

    if props.duration <= 0:
        result.add_error("Duration must be greater than zero.")

    if props.speed <= 0:
        result.add_error("Speed must be greater than zero.")

    if props.quality == "FINAL" and props.resolution and props.resolution < 128:
        result.add_warning("Final quality with a very low resolution may produce poor results.")

    if props.noise_upres > 1 and props.quality == "DRAFT":
        result.add_warning("Noise is enabled for Draft quality.")

    return result


def validate_scene(scene) -> ValidationResult:
    """Validate scene values required for SI-consistent Mantaflow setup."""
    result = ValidationResult(ok=True)
    unit_scale = float(scene.unit_settings.scale_length)
    if unit_scale <= 0:
        result.add_error("Scene unit scale must be greater than zero.")
    elif abs(unit_scale - 1.0) > 1e-6:
        result.add_error(
            "Scene unit scale must be 1.0 metre per Blender unit for Blast FX."
        )

    fps = float(scene.render.fps) / float(scene.render.fps_base)
    if fps <= 0:
        result.add_error("Scene FPS must be greater than zero.")

    gravity = getattr(scene, "gravity", None)
    if gravity is None or float(gravity.length) <= 0:
        result.add_error("Scene gravity must have a positive magnitude.")
    return result
