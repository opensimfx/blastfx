# Test Strategy

Blender add-ons need two test layers.

## Pure Python tests

Test:

- preset registry
- preset application
- naming
- validation
- configuration transformations

These can run with normal Python if the module is kept free of `bpy`
dependencies.

## Blender integration tests

Run inside Blender's bundled Python.

Test:

- registration
- property creation
- collection creation
- controller creation
- object tagging
- rebuild
- deletion
- cache setup
- Mantaflow configuration

Do not require a full high-resolution bake for every CI test.
