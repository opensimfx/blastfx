from ..utils.animation import action_fcurves

# Stops relative to the artist's own exposure.
FLASH_STOPS = 1.0
IRIS_DIP_STOPS = -0.35


def build_exposure_fx(scene, start_frame, config):
    """Camera exposure reacting to the detonation, relative to the artist's.

    One frame overexposed at the flash, then a slight dip (a camera iris
    closing down after the flash), recovering over ~1.5 T. The old version
    keyed +3 stops, held +2 through 15 % of the shot and ended at 0 whatever
    the scene's exposure had been.
    """
    if not hasattr(scene, "view_settings"):
        return
    plan = config["plan"]
    T = config["physical"].time_unit_s
    base = float(scene.view_settings.exposure)
    start = int(start_frame)

    def at(event_T):
        return start + max(1, int(round(plan.event_frames(event_T * T))))

    dip = max(start + 2, at(0.15))
    recover = max(dip + 1, at(1.5))
    keys = ((start - 1, base), (start, base), (start + 1, base + FLASH_STOPS),
            (dip, base + IRIS_DIP_STOPS), (recover, base))
    for frame, value in keys:
        scene.view_settings.exposure = value
        scene.view_settings.keyframe_insert("exposure", frame=frame)
    scene.view_settings.exposure = base

    for fcurve in action_fcurves(scene.view_settings):
        for kp in fcurve.keyframe_points:
            if start - 1 <= kp.co[0] <= recover:
                kp.interpolation = "BEZIER"


def build_exposure(context, collection, controller, config):
    """Build exposure animation."""
    build_exposure_fx(context.scene, int(config.get("start_frame", 1)), config)
    return None
