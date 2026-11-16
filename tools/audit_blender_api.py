"""Run inside Blender 5.2's Python environment.

Usage from Blender's Text Editor: Run Script.
"""
import bpy
from blastfx.core.blender_api import runtime_self_test

print("BlastFX Blender version:", bpy.app.version_string)
errors = runtime_self_test()
if errors:
    print("BLASTFX API AUDIT: FAIL")
    for error in errors:
        print(" -", error)
else:
    print("BLASTFX API AUDIT: PASS")
