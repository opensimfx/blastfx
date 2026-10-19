from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "blastfx"
# Version is read from the controller source so it stays the single source of truth
# without importing bpy.
VERSION = re.search(r'obj\["blastfx_version"\] = "([^"]+)"', (ROOT / "blastfx" / "core" / "controller.py").read_text()).group(1)

OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)
TARGET = OUT / f"blastfx_v{VERSION}.zip"

with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in ADDON.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.name != ".DS_Store":
            zf.write(path, path.relative_to(ROOT))

print(TARGET)
