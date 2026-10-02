"""crown shape (Michael: "crown is still visibly flattened in a way that looks very odd / bugged"): along rays from the
head centre in the sagittal (front-back) and coronal (ear-ear) planes, every 5 deg from -85 to 85 off vertical, the
hair's outermost radius minus the skull's (standoff, cm). A good crown keeps the standoff smooth and the outline's
curvature close to the skull's; flags: the standoff's range and its largest step between neighbouring rays, and the
outline's flattest stretch (radius of curvature over the skull's, at the top)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ANG = np.arange(-85, 86, 5)


def ray_r(P, C, v, cone=2.5):
    d = P - C; r = np.linalg.norm(d, axis=1); u = d / r[:, None]
    m = np.degrees(np.arccos(np.clip(u @ v, -1, 1))) < cone
    return r[m].max() if m.any() else np.nan


def crown(bdir):
    A = np.load(os.path.join(bdir, 'arrays.npz')); M = json.load(open(os.path.join(bdir, 'bundle.json')))
    ez = M['assembly']['eye_z']; C = np.array([0.0, 0.0185, ez + 0.025])
    sk = next(o['name'] for o in M['objects'] if o['group'] == 'skin')
    S = A['o/%s/eval/V' % sk]; S = S[S[:, 2] > ez - 0.05]
    H = np.concatenate([A['o/%s/eval/V' % o['name']] for o in M['objects'] if o['group'] == 'hair'
                        and 'ahoge' not in o['name'] and ('o/%s/eval/V' % o['name']) in A])
    out = {}
    for plane, axis in (('sagittal', 1), ('coronal', 0)):
        so, rh, rs = [], [], []
        for a in ANG:
            v = np.zeros(3); v[2] = np.cos(np.radians(a)); v[axis] = np.sin(np.radians(a)) * (-1 if axis == 1 else 1)
            h, s = ray_r(H, C, v), ray_r(S, C, v)
            rh.append(h); rs.append(s); so.append((h - s) * 100)
        so = np.array(so); rh = np.array(rh)
        # curvature of the hair outline in the plane (polar r(a)) against the skull's, over the top 60 deg
        def curv(r):
            t = np.radians(ANG); x, y = r * np.sin(t), r * np.cos(t)
            dx, dy = np.gradient(x), np.gradient(y); ddx, ddy = np.gradient(dx), np.gradient(dy)
            return np.abs(dx * ddy - dy * ddx) / np.maximum((dx * dx + dy * dy) ** 1.5, 1e-12)
        top = np.abs(ANG) <= 30
        kh, ks = curv(rh), curv(np.array(rs))
        out[plane] = dict(standoff=[round(float(x), 2) for x in so], range=round(float(np.nanmax(so[top]) - np.nanmin(so[top])), 2),
                          max_step=round(float(np.nanmax(np.abs(np.diff(so)))), 2),
                          flatness=round(float(np.nanmin(kh[top] / np.maximum(ks[top], 1e-9))), 2))
    return out


if __name__ == '__main__':
    for b in sys.argv[1:]:
        r = crown(b)
        print(os.path.basename(b))
        for p in r:
            print('  %-9s range %.2f cm, max step %.2f cm, flattest curvature/skull %.2f | standoff (cm) %s' % (
                p, r[p]['range'], r[p]['max_step'], r[p]['flatness'], ' '.join('%.1f' % x for x in r[p]['standoff'][5:-5])))
