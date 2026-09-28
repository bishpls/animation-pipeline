"""charkit.geom: a deterministic geometry kernel for charkit (docs/GEOM.md), so the pipeline doesn't lean on Blender's
modifiers for geometry. Runs in the venv (numpy, scipy, scikit-image, numba; manifold3d for exact booleans); the results
(npz / ply / glb) go to the Blender stage, which needs only numpy to read them (charkit.geom.io, charkit.geom.blender).

    mesh       Mesh (V, F, per-vertex vc / vn / uv), topology: edges, boundary loops, parts, normals, volume
    io         load / save .glb .gltf .ply .obj .npz (glTF base-colour texture sampled to vertex colours)
    repair     merge_close, clean, orient, fill_holes, remove_small_parts, report (health + self-intersection estimate)
    bvh        BVH: nearest / signed distance / winding number / ray casts, vectorised over large point sets
    volume     Grid: occupancy (winding number, parity), solid (hollow shells, holes, walls), sdf, marching cubes,
               union / intersection / difference, dilate / erode / opening / closing / blur, cavities, components
    boolean    exact mesh booleans (manifold3d) on manifold inputs, the volume path otherwise
    smooth     taubin, laplacian, bilateral_normals, smooth_normals, envelope_normals
    remesh     isotropic (Botsch-Kobbelt), decimate (quadric error)
    raster     orthographic silhouettes, IoU and shaded renders in numpy/numba
    parts      a part (hair, skirt) cut from a generated character aligned onto ours
    blender    (inside Blender) a part as a mesh object with custom normals

Import the submodules (`from charkit.geom import volume`); importing the package itself pulls in nothing heavy.
"""

__all__ = ['mesh', 'io', 'repair', 'bvh', 'volume', 'boolean', 'smooth', 'remesh', 'raster', 'parts', 'primitives']


def __getattr__(name):
    if name in __all__:
        import importlib
        return importlib.import_module('.' + name, __name__)
    raise AttributeError(name)
