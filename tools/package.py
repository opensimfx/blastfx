from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "blastfx"
OUT = ROOT / "blastfx_v1.zip"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in ADDON.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            zf.write(path, path.relative_to(ROOT))

print(OUT)
