import bpy

ROOT_NAME = "BlastFX"


def get_or_create_root_collection(scene):
    root = bpy.data.collections.get(ROOT_NAME)
    if root is None:
        root = bpy.data.collections.new(ROOT_NAME)
        scene.collection.children.link(root)
    elif root.name not in {c.name for c in scene.collection.children}:
        scene.collection.children.link(root)
    return root


def create_blast_collection(scene, blast_id: str):
    root = get_or_create_root_collection(scene)
    name = f"Blast_{blast_id}"
    collection = bpy.data.collections.new(name)
    root.children.link(collection)
    return collection


def remove_collection(collection):
    for obj in list(collection.objects):
        if obj.get("blastfx_generated", False):
            bpy.data.objects.remove(obj, do_unlink=True)
    if not collection.objects:
        bpy.data.collections.remove(collection)
