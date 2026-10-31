def phase_frames(scene, start_frame, phases):
    """Convert phase durations in seconds into scene frames."""
    fps = scene.render.fps / scene.render.fps_base
    current = float(start_frame)
    result = {}

    for name, duration_s in phases.items():
        begin = current
        current += duration_s * fps
        result[name] = (begin, current)

    return result
