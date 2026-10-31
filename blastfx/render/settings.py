"""Render, world, and camera helpers for Blast FX scenes."""

import bpy


def configure_render_settings(scene, quality="PREVIEW"):
    """Apply Cycles render settings optimized for volume-heavy explosions."""
    scene.render.engine = "CYCLES"
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.01
    scene.cycles.adaptive_min_samples = 4
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_quality = "HIGH"
    scene.cycles.use_light_tree = True
    scene.cycles.volume_bounces = 4
    scene.cycles.volume_step_rate = 1.0
    scene.cycles.volume_max_steps = 4096
    scene.cycles.volume_biased = False
    scene.cycles.max_bounces = 12
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 12
    scene.cycles.film_exposure = 1.0
    scene.render.film_transparent = True
    if quality == "DRAFT":
        scene.cycles.samples = 32
    elif quality == "FINAL":
        scene.cycles.samples = 512
    else:
        scene.cycles.samples = 128
    scene.render.image_settings.file_format = "PNG"


def configure_world(scene, world_name="BlastFX_World"):
    """Create a world with procedural sky and atmospheric volume scatter."""
    if scene.world is None or scene.world.name != world_name:
        world = bpy.data.worlds.new(world_name)
        scene.world = world
    else:
        world = scene.world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type = "PREETHAM"
    sky.sun_elevation = 0.3
    sky.turbidity = 2.0
    vol_scatter = nodes.new("ShaderNodeVolumeScatter")
    vol_scatter.inputs["Density"].default_value = 0.001
    vol_scatter.inputs["Anisotropy"].default_value = 0.3

    links.new(sky.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], out.inputs["Surface"])
    links.new(vol_scatter.outputs["Volume"], out.inputs["Volume"])
    bg.inputs["Strength"].default_value = 1.0
    return world


def configure_camera_dof(camera, focus_object=None, fstop=2.8, focus_distance=10.0):
    """Enable depth of field on a camera."""
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = focus_distance
    camera.data.dof.aperture_fstop = fstop
    if focus_object is not None:
        camera.data.dof.focus_object = focus_object
    return camera