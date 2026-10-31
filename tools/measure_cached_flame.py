"""Measure flame and smoke phases from an existing completed Blender snapshot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :]
    blend_path = Path(args[0]).resolve()
    output_path = Path(args[1]).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(blend_path), load_ui=False)
    scene = bpy.context.scene
    domain = next(obj for obj in bpy.data.objects if obj.get("blastfx_role") == "domain")
    records = []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        evaluated = domain.evaluated_get(bpy.context.evaluated_depsgraph_get())
        settings = next(
            modifier.domain_settings
            for modifier in evaluated.modifiers
            if modifier.type == "FLUID" and modifier.domain_settings is not None
        )
        values = {}
        for name in ("flame_grid", "density_grid"):
            grid = list(getattr(settings, name, []) or [])
            values[name] = {
                "max": max(grid) if grid else 0.0,
                "mean": sum(grid) / len(grid) if grid else 0.0,
            }
        records.append({"frame": frame, "grids": values})
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
