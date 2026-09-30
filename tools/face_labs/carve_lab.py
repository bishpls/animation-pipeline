"""the hull's face carve (charkit.geom.hull.carve_face) looked at: the body hull built up to the carve as hull.build's
fast path does, then the carve with its detail (every voxel it would take without the hair rule: where, how far in front
of the face, hair in some view or not, kept or not), saved and summarised by region (the fringe over the eyes, the
cheeks' sides, the jaw), for choosing hair_keep.
    python carve_lab.py OUT_DIR [SPEC] [HAIR_KEEP ...]"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np


def main(out, spec_path='charkit/spec/clawd_body.json', keeps=(0.0, 0.02, 0.03, 0.04)):
    from charkit import bodyeval, code_base, eyes as eyelib, manifest, refcheck, styles
    from charkit.geom import hull
    t0 = time.time()
    spec = bodyeval.resolve(spec_path)
    bs = spec['ref']['body_sheet']
    prior = styles.load(spec.get('style', 'anime'))['hull']
    ex = eyelib._knobs(spec.get('eyes'))['x']
    views, info = hull.views_from_sheet(refcheck._load(bs['image']), ex, bs.get('facing', -1))
    A = hull.axes_for(views, 0.01)
    masks = manifest.produced(spec, 'outfit_masks', print)
    P = hull.attach_pieces(views, masks) if masks and os.path.exists(masks) else None
    info['refined_L'] = hull.refine(views, A, prior)
    V0 = hull.rounded(views, A, list(views), **prior)
    Sh, Ch, _ = code_base.head_sections(spec, print)
    os.makedirs(out, exist_ok=True)
    rep = {'seconds_to_carve': round(time.time() - t0, 1), 'y_e': info['y_e']}
    for k in keeps:
        V = V0.copy()
        det = {}
        n = hull.carve_face(V, A, views, Sh, info['y_e'], P=P, hair_keep=k, detail=det)
        xyz, ah, hr, kept = det['xyz'], det['ahead'], det['hair'], det['kept']
        y_eye = xyz[:, 1] - info['y_e']
        region = np.where(xyz[:, 2] > -0.05, 'fringe', np.where(np.abs(xyz[:, 0]) > 0.22, 'side', 'jaw'))
        R = {'carved': n, 'would_carve': int(len(xyz)), 'kept': int(kept.sum())}
        for g in ('fringe', 'side', 'jaw'):
            sel = region == g
            R[g] = {'would_carve': int(sel.sum()), 'hair': int((sel & hr).sum()), 'kept': int((sel & kept).sum()),
                    'hair_ahead_pct': [round(float(v), 4) for v in np.percentile(ah[sel & hr], [10, 50, 90])]
                    if (sel & hr).any() else None}
        rep['keep_%.3f' % k] = R
        if k == keeps[-1]:
            np.savez_compressed(os.path.join(out, 'carve_detail.npz'), xyz=xyz, ahead=ah, hair=hr, kept=kept, y_e=info['y_e'])
        print('hair_keep %.3f:' % k, json.dumps(R))
    json.dump(rep, open(os.path.join(out, 'carve_lab.json'), 'w'), indent=1)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1] if len(a) > 1 else 'charkit/spec/clawd_body.json', [float(v) for v in a[2:]] or (0.0, 0.02, 0.03, 0.04))
