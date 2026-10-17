import uuid

CONTROLLER_TAG = "blastfx_controller"


def new_blast_id() -> str:
    return uuid.uuid4().hex[:8]


def tag_controller(obj, props, blast_id: str):
    obj[CONTROLLER_TAG] = True
    obj["blastfx_id"] = blast_id
    obj["blastfx_version"] = "0.1.2"
    obj["blastfx_type"] = props.explosion_type
    obj["blastfx_preset"] = props.preset_id
    obj["blastfx_seed"] = props.seed
    obj["blastfx_generated"] = True


def is_controller(obj) -> bool:
    return bool(obj and obj.get(CONTROLLER_TAG, False))
