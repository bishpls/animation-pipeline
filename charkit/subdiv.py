"""Catmull-Clark subdivision as Blender's Subdivision Surface modifier evaluates it (limit surface on, creases used,
boundaries 'ALL': open edges sharp), for charkit.faceeval, charkit.code_base (the cage's limit fit) and
charkit.geom.headfit: a thin front on charkit.geom.subsurf, the evaluator's exact port of the modifier (OpenSubdiv's
rules, measured against Blender to 1e-5 L; docs/workstreams/evalmesh.md). One subdivision in the kit: this module had its
own Catmull-Clark, which put carried vertex data (weights) through the limit stencils and read open-border corners at
the true limit; Blender carries vertex data linearly and evaluates at its adaptive level (face round 5).

    V1, quads, parent = subdiv.catmull_clark(V, faces, sharp_edges)   # parent: each quad's source face
"""
import numpy as np


def catmull_clark(V, faces, sharp=(), limit=True, levels=1):
    """Catmull-Clark subdivision (charkit.geom.subsurf.subdivide). V (N, 3), or (N, 3 + k): positions and per-vertex
    data; faces: polygons (lists of vertex indices, or an (F, k) array); sharp: (a, b) vertex pairs of the creased edges
    (Blender's crease 1.0: infinitely sharp; open edges are sharp too); levels: how many refinements (the modifier's
    `levels` in the viewport, which charkit.trace.mesh_arrays reads; `render_levels` in a render).
    limit: the refined vertices at their limit positions (Blender's evaluation), the data columns carried as Blender
    carries vertex data (linear: kept at the vertices, the mean of the ends at an edge's point, of the corners at a
    face's); limit False: a plain refinement, the data columns refined with the positions (Catmull-Clark's own rules:
    a region refined before it is cut, charkit.garments).
    -> (V1 (the input vertices, then one per edge, then one per face, each level; data columns after the positions),
    quads (M, 4), parent (M,): each quad's face in the input)."""
    from .geom import subsurf
    V = np.asarray(V, float)
    s = np.asarray(sharp, np.int64).reshape(-1, 2) if len(sharp) else np.zeros((0, 2), np.int64)
    creases = (s, np.ones(len(s))) if len(s) else None
    if not limit or V.shape[1] == 3:
        R = subsurf.subdivide(V, faces, levels=levels, creases=creases, limit_surface=limit)
        return R['V'], R['quads'], R['parent']
    R = subsurf.subdivide(V[:, :3], faces, levels=levels, creases=creases, limit_surface=True, carry=V[:, 3:])
    return np.concatenate([R['V'], R['carry']], 1), R['quads'], R['parent']


def region(V, faces, keep):
    """the faces with every vertex in `keep` (bool per vertex), compacted: -> (V', faces', face indices, vertex indices)."""
    fk = [i for i, f in enumerate(faces) if all(keep[v] for v in f)]
    used = np.unique(np.concatenate([faces[i] for i in fk]))
    remap = np.full(len(V), -1, np.int64); remap[used] = np.arange(len(used))
    return V[used], [tuple(remap[list(faces[i])]) for i in fk], np.array(fk), used
