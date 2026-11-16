"""The add-on version, read from blender_manifest.toml so there is one place to change it."""

import tomllib
from pathlib import Path

_MANIFEST = Path(__file__).resolve().parents[1] / "blender_manifest.toml"
VERSION: str = tomllib.loads(_MANIFEST.read_text(encoding="utf-8"))["version"]
