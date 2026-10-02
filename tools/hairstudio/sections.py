"""vertical cross-sections through the head (observability: "is the hair actually fitting the skull?"): the sagittal
plane (x = the head's centre, front to back) and the coronal plane (y = the head's centre, ear to ear), each hair
object's section in its own colour over the skin's section (grey); standoff readings from the skull at named points.
    python sections.py BUNDLE TAG [BUNDLE2 TAG2 ...]  -> studio/sections_TAGS.png"""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.expanduser('~/animation-pipeline-3d'))
from charkit import bundle as bl

COL = {'hair_upper_back': (140, 90, 200), 'hair_lower_back': (230, 110, 150), 'hair_bangs': (220, 60, 60),
       'hair_side_lock_L': (240, 180, 40), 'hair_side_lock_R': (240, 150, 30), 'hair_bun_L': (70, 120, 230),
       'hair_bun_R': (70, 120, 230), 'hair_ahoge': (60, 180, 160), 'hair_flyaways': (120, 190, 60)}


def plane_cut(V, T, axis, val):
    """segments where triangles cross the plane coordinate[axis] == val -> list of ((u0,v0),(u1,v1)) in the other two
    coordinates (sagittal: (y, z); coronal: (x, z))."""
    others = [i for i in range(3) if i != axis]
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    d = [x[:, axis] - val for x in (a, b, c)]
    hit = (np.minimum(np.minimum(d[0], d[1]), d[2]) < 0) & (np.maximum(np.maximum(d[0], d[1]), d[2]) > 0)
    segs = []
    for i in np.where(hit)[0]:
        pts = []
        for (P, dp), (Q, dq) in (((a[i], d[0][i]), (b[i], d[1][i])), ((b[i], d[1][i]), (c[i], d[2][i])),
                                 ((c[i], d[2][i]), (a[i], d[0][i]))):
            if dp * dq < 0:
                t = dp / (dp - dq)
                X = P + (Q - P) * t
                pts.append((X[others[0]], X[others[1]]))
        if len(pts) == 2:
            segs.append(pts)
    return segs


def panel(B, axis, size=520, title=''):
    c = np.array(B.assembly['centre'], float); L = float(B.assembly['L']); ez = float(B.assembly['eye_z'])
    val = c[axis]
    im = Image.new('RGB', (size, size), (248, 248, 250)); d = ImageDraw.Draw(im)
    sc = size / (1.6 * L)
    u0 = c[1] if axis == 0 else c[0]
    to = lambda p: (size / 2 + (p[0] - u0) * sc * (1 if axis == 1 else -1) if axis == 1 else size / 2 + (p[0] - u0) * sc,
                    size * 0.42 - (p[1] - ez) * sc)
    for o in B.objects():
        if o.group not in ('skin', 'hair') or not o.has('eval'):
            continue
        V, T, _, _ = o.mesh('eval')
        col = (150, 150, 155) if o.group == 'skin' else COL.get(o.name, (90, 90, 90))
        for s_ in plane_cut(V, T, axis, val):
            d.line([to(s_[0]), to(s_[1])], fill=col, width=2 if o.group == 'hair' else 1)
    d.line([(0, size * 0.42), (size, size * 0.42)], fill=(210, 210, 215))
    d.text((6, 4), title + ('  sagittal (front at left)' if axis == 0 else '  coronal (ear to ear)'), fill=(30, 30, 30))
    d.text((6, size * 0.42 - 12), 'eye line', fill=(150, 150, 150))
    return np.asarray(im)


def standoff(B):
    """the hair's outermost distance from the skull along fixed rays from the head centre (cm): crown, forehead
    (25 deg above the eye line, front), temple, back."""
    from scipy.spatial import cKDTree
    c = np.array(B.assembly['centre'], float); c[2] = float(B.assembly['eye_z']) + 0.025
    out = {}
    hair = np.concatenate([o.a('eval', 'V') for o in B.objects() if o.group == 'hair' and o.has('eval') and 'bun' not in o.name])
    skin = [o for o in B.objects() if o.group == 'skin'][0].a('eval', 'V')
    for name, th, al in (('crown', 5, 0), ('forehead', 55, 180), ('temple', 75, 130), ('back', 70, 0)):
        dv = np.array([np.sin(np.radians(th)) * np.sin(np.radians(al)), np.sin(np.radians(th)) * np.cos(np.radians(al)),
                       np.cos(np.radians(th))])
        def far(P):
            rel = P - c
            along = rel @ dv
            perp = np.linalg.norm(rel - np.outer(along, dv), axis=1)
            m = (perp < 0.006) & (along > 0)
            return along[m].max() if m.any() else np.nan
        out[name] = round(float((far(hair) - far(skin)) * 100), 2)
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    rows, rep = [], {}
    for bdir, tag in zip(args[::2], args[1::2]):
        B = bl.load(bdir)
        rows.append(np.concatenate([panel(B, 0, title=tag), panel(B, 1, title=tag)], 1))
        rep[tag] = standoff(B)
    Image.fromarray(np.concatenate(rows, 0)).save(os.path.join(HERE, 'studio', 'sections_%s.png' % '_'.join(args[1::2])))
    print(json.dumps(rep))
