from .flash import build_flash
from .shockwave import build_shockwave_geometry
from .camera import build_camera_fx
from .exposure import build_exposure
from .heat_distortion import build_heat_distortion, build_heat_distortion_compositor
from .dust_light import build_ground_dust_fill
from ..core.blast_plan import plan_blast


def build_animation(context, collection, controller, props, plan=None):
    plan = plan or plan_blast(props, context.scene)
    config = plan.config_dict(props)

    if props.use_flash:
        build_flash(context, collection, controller, config)
    if props.use_shockwave:
        build_shockwave_geometry(context, collection, controller, config)
    if (
        getattr(config.get("profile"), "ground_surge", False)
        and getattr(config.get("profile"), "shockwave_radius_factor", 3.0) > 3.0
    ):
        build_ground_dust_fill(context, collection, controller, config)

    if props.use_camera_fx:
        build_camera_fx(context, collection, controller, config)
    if props.use_exposure:
        build_exposure(context, collection, controller, config)
    if props.use_heat_distortion:
        build_heat_distortion(context, collection, controller, config)
        build_heat_distortion_compositor(context, controller, config)
    return config