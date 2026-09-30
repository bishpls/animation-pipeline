"""the neck's silhouette per row, ours against the design's: the front view's skin run through the midline (its left
and right edges, L from the eyes' middle) and the profile's front edge (L), from the chin to the chest."""
import sys
import numpy as np
sys.path.insert(0, '/Users/michaelbishop/animation-pipeline-face')
from charkit import bundle as bl, bodyqa, qa3d

SK = bodyqa.CLASS['skin']


def run_at(row, c):
    """the skin run through column c (or the nearest skin within 5 px) -> (left, right) columns or None."""
    s = np.nonzero(row)[0]
    if not len(s):
        return None
    if not row[c]:
        k = s[np.argmin(np.abs(s - c))]
        if abs(k - c) > 5:
            return None
        c = k
    l = c
    while l > 0 and row[l - 1]:
        l -= 1
    r = c
    while r < len(row) - 1 and row[r + 1]:
        r += 1
    return l, r


def table(b, zs):
    B = bl.load(b + '/bundle')
    Dz = qa3d.Design(B)
    ctx = Dz.sheet_context(); dv = Dz.design_views(); ppl = ctx['ppl']
    meshes, _ = qa3d.scene_classes(B)
    iw = np.array(qa3d.iris_centres(B))
    Z = bodyqa.zbuffer_views(meshes, ctx['az3'], iw, B.assembly['centre'], B.assembly['L'], ppl, views=('front', 'profile'))
    W = bodyqa.WIN
    c0 = int(round(W['x'] * ppl))
    out = []
    for z in zs:
        r = int(round((W['top'] - z) * ppl))
        row = {}
        for who, fm, pm in (('des', dv['front']['cls'] == SK, dv['profile']['fg']),
                            ('our', Z['front'][1] == SK, Z['profile'][1] >= 0)):
            ru = run_at(fm[r], c0)
            half = (ru[1] - ru[0] + 1) / ppl / 2 if ru else np.nan
            cols = np.nonzero(pm[r])[0]
            fe = (cols.min() + 0.5) / ppl - W['x'] if len(cols) else np.nan
            row[who] = (half, fe)
        out.append((round(z, 2), row))
    return out


if __name__ == '__main__':
    zs = np.arange(-0.34, -0.78, -0.02)
    for b in sys.argv[1:]:
        print(b)
        print('    z    half des  ours  diff |  front des  ours  diff')
        for z, r in table(b, zs):
            (hd, fd), (ho, fo) = r['des'], r['our']
            print('  %5.2f   %.3f %.3f %+.3f |  %+.3f %+.3f %+.3f' % (z, hd, ho, ho - hd, fd, fo, fo - fd))
