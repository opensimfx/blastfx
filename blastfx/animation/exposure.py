from ..utils.animation import action_fcurves


def build_exposure_fx(scene, start_frame, config):
    """Optional exposure impulse. Must be non-destructive to unrelated animation."""
    # This would typically animate the scene's exposure or a compositor node
    # For now, we'll keyframe the scene's view_settings.exposure if available
    if hasattr(scene, "view_settings"):
        duration_s = config.get(
            "timeline_duration_s", config["physical"].characteristic_time_s
        )
        fps = scene.render.fps / scene.render.fps_base
        total_frames = int(duration_s * fps)
        end_frame = start_frame + total_frames

        # Animate exposure: 0 -> peak -> 0
        scene.view_settings.keyframe_insert("exposure", frame=start_frame)
        scene.view_settings.exposure = 3.0
        scene.view_settings.keyframe_insert("exposure", frame=start_frame + int(total_frames * 0.05))
        scene.view_settings.exposure = 2.0
        scene.view_settings.keyframe_insert("exposure", frame=start_frame + int(total_frames * 0.15))
        scene.view_settings.exposure = 0.0
        scene.view_settings.keyframe_insert("exposure", frame=end_frame)

        for fcurve in action_fcurves(scene.view_settings):
            for kp in fcurve.keyframe_points:
                kp.interpolation = "BEZIER"


def build_exposure(context, collection, controller, config):
    """Build exposure animation."""
    start_frame = int(config.get("start_frame", 1))
    build_exposure_fx(context.scene, start_frame, config)
    return None
