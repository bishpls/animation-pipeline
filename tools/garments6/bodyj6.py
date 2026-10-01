"""bodyj (tools/garments5/bodyj.py) for the neck's flare and the bridge's top: the same body built without Blender per
variant (body.* overrides, the head's neck included: character.assemble), measured against the base body sheet
(shm.measure_labels: the score, the top line), the whole skin's neck crease (faceregion.crease_of, as neck_crease reads
it), the bridge's rise over the torso's top (its vertices above the torso's top ring: the round-5 defect, the bridge's
top loops overlapping the torso's top rows by the neck) and the posed raises (pose side / front, the rig's pivot); one
zoomed picture of the neck and shoulder per variant (front and back, the sheet's body grey, ours by part: head blue,
torso green, bridge and arm red).
    python tools/garments6/bodyj6.py BUILD VARIANTS.json [--out DIR] [--only a,b] [--no-pose]"""
import sys, os, json, copy
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join('tools', 'garments5'))
import numpy as np
import bodyj, shm
from charkit import bundle, qa3d, bodyqa, code_body

args = [a for a in sys.argv[1:]]
def opt(k, d=None):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
out = opt('--out', 'charkit/out/garments6/bodyj6')
only = opt('--only')
nopose = '--no-pose' in args
args = [a for a in args if a != '--no-pose']
build, var = args[0], json.load(open(args[1]))
os.makedirs(out, exist_ok=True)
Bk = bundle.load(build + '/bundle')
D = qa3d.Design(Bk)
bb = shm.bb_views(D)
spec0 = json.load(open(os.path.join(build, 'clawd.spec.json')))
res, pics = {}, []
for name, ov in var.items():
    if name.startswith('_') or (only and name not in only.split(',')):
        continue
    spec = copy.deepcopy(spec0)
    for k, v in (ov or {}).items():
        bodyj.setp(spec, k, v)
    npz = os.path.join(out, name + '_body_code.npz')
    try:
        Bd = bodyj.body_data(spec, npz)
    except Exception as ex:
        import traceback; traceback.print_exc()
        res[name] = dict(error=repr(ex)); print(name, 'ERROR', ex); continue
    L = float(Bd['head_len'])
    Z = np.load(npz)
    V = np.asarray(Bd['verts'], float)
    Oz = float(np.mean(V[Bd['neck_ring'], 2])) - code_body.CUT * L
    lab = bodyj.views(bodyj.labels(Bd, Bk, 1e9), Bk, D)
    # the head's own triangles labelled HEAD (labels() does it by vertex index: the assembled skin's head is after n_body)
    M = shm.measure_labels(D, lab, name)
    top = bodyj.topology(Bd)
    rec = dict(score=bodyj.score(M), topology_ok=top['boundary_edges'] == 0 and top['nonmanifold_edges'] == 0
               and top['flipped_edges'] == 0, components=top['components'])
    fl = M['views']['front']['left']
    rec['front_top_rms'], rec['front_outer_rms'] = fl['top_loose'].get('rms'), fl['outer'].get('rms')
    rec['front_top_line'] = fl['st_top']
    bl = M['views']['back']['left']
    rec['back_top_rms'] = bl['top_loose'].get('rms')
    rec['back_top_line'] = bl['st_top']
    # the bridge's rise over the torso's top ring (L)
    ring_z = float(np.mean(V[Bd['neck_ring'], 2]))
    a_, b_ = Bd['parts']['shoulder_left']
    rise = (V[a_:b_, 2] - ring_z) / L
    rec['bridge_over_ring'] = dict(n=int((rise > 0.005).sum()), max=round(float(rise.max()), 4))
    from charkit import faceregion
    c_, L_, _ = faceregion.frame(Bk)
    T = bodyj.tris(Bd['faces'])
    T = T[np.isfinite(V[T]).all((1, 2))]
    K = faceregion.crease_of(V, T, c_, L_)
    rec['crease_whole'] = dict(max=K['max'], worst=K['worst'], median=K['median']) if K else None
    if not nopose:
        for key, tgt in (('pose_side', (1.0, 0.0, 0.0)), ('pose_front', (0.0, -1.0, 0.0))):
            P = bodyj.pose(Bd, 'left', tgt, pivot=0.0)
            pm = bodyj.posed_measures(Bd, P, 'left', L, bodyj.tris(Bd['faces']), R=bodyj.pose.R)
            pm['inside'] = bodyj.inside_torso(Bd, P, 'left', Z, L, Oz)['n']
            rec[key] = {k: pm.get(k) for k in ('strain_p95', 'folded_area', 'collapsed_area', 'inside')}
    res[name] = rec
    print('SUMMARY %-10s score %.4f crease %s | front top %s outer %s back top %s | bridge over ring %s | %s %s %s' % (
        name, rec['score'], rec['crease_whole'] and rec['crease_whole']['max'], rec['front_top_rms'],
        rec['front_outer_rms'], rec['back_top_rms'], rec['bridge_over_ring'],
        'topology ok' if rec['topology_ok'] else 'TOPOLOGY %s' % top, rec.get('pose_side'), rec.get('pose_front')))
    print('   front top z (ours, ref):', rec['front_top_line'])
    pics.append((name, lab, Bd))
json.dump(res, open(os.path.join(out, 'bodyj6.json'), 'w'), indent=1, default=str)

import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from skimage import measure as skm
W = bodyqa.WIN
ppl = D.sheet_context()['ppl']
vs = ('front', 'back', 'profile')
fig, ax = plt.subplots(len(pics), len(vs), figsize=(6 * len(vs), 4.6 * len(pics)), squeeze=False)
for r, (name, lab, Bd) in enumerate(pics):
    for j, v in enumerate(vs):
        x0, x1 = (-0.05, 0.8) if v != 'profile' else (-0.4, 0.6)
        r0, r1 = shm.rc(-0.3, 0, ppl)[0], shm.rc(-0.85, 0, ppl)[0]
        c0, c1 = shm.rc(0, x0, ppl)[1], shm.rc(0, x1, ppl)[1]
        ref, cls = bb[v]['fg'][r0:r1, c0:c1], bb[v]['cls'][r0:r1, c0:c1]
        im = np.ones(ref.shape + (3,))
        im[ref] = (0.75, 0.75, 0.78)
        im[ref & (cls == bodyqa.CLASS['hair'])] = (0.95, 0.75, 0.6)
        ext = [c0 / ppl - W['x'], c1 / ppl - W['x'], W['top'] - r1 / ppl, W['top'] - r0 / ppl]
        ax[r, j].imshow(im, extent=ext)
        L_ = lab[v][r0:r1, c0:c1]
        for m, col in ((L_ == shm.HEAD, 'tab:blue'), (L_ == shm.TORSO, 'tab:green'), (L_ == shm.ARM, 'tab:red')):
            for C in skm.find_contours(np.pad(m, 1).astype(float), 0.5):
                C = C - 1
                ax[r, j].plot(C[:, 1] / ppl + ext[0], ext[3] - C[:, 0] / ppl, '-', color=col, lw=0.9)
        ax[r, j].axhline(-0.52, color='k', lw=0.5, ls=':')
        ax[r, j].set_title('%s %s (%s)' % (name, v, json.dumps({k: res[name].get(k) for k in ('score',)})), fontsize=8)
        ax[r, j].set_aspect('equal'); ax[r, j].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(out, 'bodyj6.png'), dpi=80)
print(os.path.join(out, 'bodyj6.png'))
