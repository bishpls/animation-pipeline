"""Mesh booleans: exact and robust through manifold3d (Apache-2.0) when both inputs are manifold (closed, every edge on two
faces, consistently wound), and through the volume path (voxel SDF booleans, marching cubes) otherwise: bodies with
internal cavities, self-intersections, holes or double shells, where exact booleans refuse or fail.

    out, how = boolean(a, b, 'difference')           # how: 'exact' or 'volume'
    out = union(a, b); out = difference(a, b); out = intersection(a, b)
"""
import numpy as np

from .mesh import Mesh, as_mesh

OPS = ('union', 'difference', 'intersection')


def to_manifold(m):
    """a manifold3d.Manifold of a mesh (double precision), or None when manifold3d rejects it (not manifold)."""
    import manifold3d as m3d
    m = as_mesh(m)
    if hasattr(m3d, 'Mesh64'):
        M = m3d.Manifold(m3d.Mesh64(np.ascontiguousarray(m.V, np.float64), np.ascontiguousarray(m.F, np.uint64)))
    else:
        M = m3d.Manifold(m3d.Mesh(np.ascontiguousarray(m.V, np.float32), np.ascontiguousarray(m.F, np.uint32)))
    if M.status() != m3d.Error.NoError or M.is_empty():
        return None
    return M


def from_manifold(M):
    mm = M.to_mesh64() if hasattr(M, 'to_mesh64') else M.to_mesh()
    V = np.asarray(mm.vert_properties, np.float64)[:, :3]
    F = np.asarray(mm.tri_verts, np.int64)
    return Mesh(V, F)


def is_manifold(m):
    """closed, 2-manifold and consistently wound (what an exact boolean needs)."""
    from .mesh import unique_edges, half_edges
    m = as_mesh(m)
    if m.nf == 0:
        return False
    E, inv, cnt = unique_edges(m.F)
    if (cnt != 2).any():
        return False
    he = half_edges(m.F)
    fwd = np.bincount(inv, weights=he[:, 0] < he[:, 1], minlength=len(E))
    return bool((fwd == 1).all())


def boolean(a, b, op='difference', h=None, fallback=True, exact=True):
    """a op b. Exact (manifold3d) when both are manifold and exact=True; else, with fallback, the volume path at voxel
    size h (default 1/200 of the combined bounding box's largest side): each input's solid (winding number, so open or
    messy input works) as a signed distance, combined, marching cubes. -> (Mesh, 'exact' | 'volume')."""
    if op not in OPS:
        raise ValueError(f'op must be one of {OPS}')
    a, b = as_mesh(a), as_mesh(b)
    if exact:
        A, B = to_manifold(a), to_manifold(b)
        if A is not None and B is not None:
            R = A + B if op == 'union' else A - B if op == 'difference' else A ^ B
            import manifold3d as m3d
            if R.status() == m3d.Error.NoError:
                return from_manifold(R), 'exact'
    if not fallback:
        raise ValueError('inputs are not manifold (and fallback=False)')
    return volume_boolean(a, b, op, h), 'volume'


def volume_boolean(a, b, op='difference', h=None, band=3.0):
    """the volume path: SDFs of both on one lattice (exact near the surfaces, sign by winding number), min / max, marching
    cubes. -> Mesh (closed, manifold)."""
    from . import volume
    a, b = as_mesh(a), as_mesh(b)
    lo = np.minimum(a.V.min(0), b.V.min(0)); hi = np.maximum(a.V.max(0), b.V.max(0))
    h = h or float((hi - lo).max()) / 200.0
    G = volume.lattice(lo, hi, h, pad=int(band) + 3)
    Sa = volume.sdf(a, grid=G, band=band)
    Sb = volume.sdf(b, grid=G, band=band)
    fn = {'union': volume.union, 'difference': volume.difference, 'intersection': volume.intersection}[op]
    return volume.to_mesh(fn(Sa, Sb))


def union(a, b, **kw):
    return boolean(a, b, 'union', **kw)[0]


def difference(a, b, **kw):
    return boolean(a, b, 'difference', **kw)[0]


def intersection(a, b, **kw):
    return boolean(a, b, 'intersection', **kw)[0]
