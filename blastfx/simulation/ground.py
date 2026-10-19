"""Ground-level collider: smoke bounces off it, debris and sparks land on it.

Expert consensus (Warhawg 2020 collision guide; Iridesium): colliders must be
thin but *tall enough* to prevent tunneling, and the domain bottom border stays
off whenever a collider exists, or smoke gets squeezed out through the floor.
"""


def ground_top_z(config, controller):
    """World Z where the ground surface sits.

    Ground-surge profiles explode at the controller origin (the origin *is*
    the ground); pure airbursts only get the basement floor at the envelope
    bottom, far below the blast, so debris still lands somewhere.
    """
    profile = config.get("profile")
    if profile and profile.ground_surge:
        return float(controller.location[2])
    return float(controller.location[2] + config["domain_envelope"]["min"][2])


def build_ground(context, collection, controller, config, domain):
    import bmesh
    import bpy

    from mathutils import Vector

    from ..utils.compatibility import set_required_rna
    from ..utils.naming import component_name
    from .fluid import add_mesh_object, configure_fluid_modifier

    blast_id = controller["blastfx_id"]
    name = component_name(blast_id, "Ground")
    amount = config["physical"].characteristic_radius_m
    envelope = config["domain_envelope"]
    size = Vector(envelope["size"])
    center = Vector(envelope["center"])

    thickness = max(0.05, amount * 0.1)
    spread = Vector((size.x * 1.05, size.y * 1.05, thickness))
    top = Vector((center.x, center.y, ground_top_z(config, controller)))
    obj = add_mesh_object(
        collection, name,
        lambda bm: bmesh.ops.create_cube(bm, size=2.0),
        controller.location + top - Vector((0.0, 0.0, thickness / 2.0)),
    )
    obj.scale = spread / 2.0

    # Mantaflow collision effector for the smoke.
    _, effector = configure_fluid_modifier(obj, "EFFECTOR")
    set_required_rna(effector, effector_type="COLLISION", surface_distance=0.0)

    # Plain collision modifier for particle deflection (debris, sparks).
    for selected in context.selected_objects:
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    try:
        bpy.ops.object.modifier_add(type="COLLISION")
    except RuntimeError as exc:
        raise RuntimeError(f"Could not add ground collision modifier: {exc}") from exc
    collision = obj.modifiers[-1]
    collision.name = "BlastFX Collision"

    # Collider present: the domain bottom border must be off (leak guard).
    domain_settings = domain.modifiers["BlastFX Fluid"].domain_settings
    domain_settings.use_collision_border_bottom = False

    obj.display_type = "WIRE"
    obj.hide_render = True
    obj["blastfx_role"] = "ground_effector"
    obj["blastfx_id"] = blast_id
    obj["blastfx_component"] = "ground"
    obj["blastfx_generated"] = True
    return obj
