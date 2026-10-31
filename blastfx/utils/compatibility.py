def set_rna(target, warnings, **properties):
    """Set Blender RNA properties while reporting API drift.

    Only use this for expected Blender-version differences.
    """
    for key, value in properties.items():
        try:
            setattr(target, key, value)
        except Exception as exc:
            warnings.append(f"{type(target).__name__}.{key}: {exc}")


def set_required_rna(target, **properties):
    """Set required RNA properties and fail with the exact incompatible field."""
    for key, value in properties.items():
        if not hasattr(target, key):
            raise RuntimeError(
                f"{type(target).__name__}.{key} is unavailable in this Blender version"
            )
        try:
            setattr(target, key, value)
        except Exception as exc:
            raise RuntimeError(
                f"Unable to set {type(target).__name__}.{key}: {exc}"
            ) from exc


def input_value(node, socket_name, value):
    socket = node.inputs.get(socket_name)
    if socket is None:
        return False

    try:
        socket.default_value = value
        return True
    except Exception:
        return False
