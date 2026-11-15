"""Build the installable extension zip:  python tools/build_extension.py  ->  dist/blastfx-<version>.zip

The version comes from blastfx/blender_manifest.toml; the manifest sits at the zip root so
Blender installs the zip as an extension.
"""
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "blastfx"
VERSION = re.search(r'^version = "([^"]+)"', (ADDON / "blender_manifest.toml").read_text(), re.M).group(1)

OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)
TARGET = OUT / f"blastfx-{VERSION}.zip"

with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(ADDON.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store":
            zf.write(path, path.relative_to(ADDON))

print(TARGET)
