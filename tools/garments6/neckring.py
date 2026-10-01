"""the torso's neck ring and the shoulder tops against the neck's axis: per azimuth round the neck (0 front, 90 her
side, 180 back) the ring's horizontal distance from the neck bone's head and its height, and the body's top surface
height at distances r out (L from the eye line), and the hull collar's neckline (where the drawn collar starts).
    python tools/garments6/neckring.py BUILD"""
import sys, os, math
sys.path.insert(0, '.')
import numpy as np
from charkit import sweep, bodyeval, garments as gm
from charkit.geom import loft
build = sys.argv[1]
B0 = sweep.load_bundle(build, True)
spec = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
E = bodyeval.Evaluator(spec)
A, how = E.assembly(spec)
L = A['head']['L']
ez = float(np.mean(np.asarray(A['eyes'] if 'eyes' in A else [[0, 0, A['head'].get('eye_z', 0)]])[:, 2])) if False else None
from charkit import qa3d
ez = float(np.mean(np.array(qa3d.iris_centres(B0))[:, 2]))
nb, nt = gm.bone_seg(A, 'neck')
print('neck bone head', np.round((nb - [0, 0, ez]) / L, 3), 'tail', np.round((nt - [0, 0, ez]) / L, 3))
ring = A['body']['neck_ring']
R = A['verts'][ring]
az = np.degrees(np.arctan2(np.abs(R[:, 0] - nb[0]), nb[1] - R[:, 1]))
dist = np.hypot(R[:, 0] - nb[0], R[:, 1] - nb[1]) / L
for a0 in (0, 30, 60, 90, 120, 150, 180):
    k = np.abs(az - a0) < 12
    if k.any():
        print('ring az %3d: r %.3f z %.3f' % (a0, dist[k].mean(), ((R[k, 2] - ez) / L).mean()))
V = A['verts']
body = np.zeros(len(V), bool)
for k_, (a_, b_) in A['body']['parts'].items():
    if k_ == 'torso' or k_.startswith('shoulder_'):
        body[a_:b_] = True
dV = np.hypot(V[:, 0] - nb[0], V[:, 1] - nb[1]) / L
aV = np.degrees(np.arctan2(np.abs(V[:, 0] - nb[0]), nb[1] - V[:, 1]))
zV = (V[:, 2] - ez) / L
print('the body top (max z) by azimuth and distance from the neck axis (L):')
for a0 in (0, 30, 60, 90, 120, 150, 180):
    row = []
    for r0 in (0.12, 0.16, 0.2, 0.24, 0.28, 0.32, 0.4, 0.5):
        k = body & (np.abs(aV - a0) < 8) & (np.abs(dV - r0) < 0.02) & (zV > -1.0)
        row.append('%.3f' % zV[k].max() if k.any() else '  -  ')
    print('  az %3d: %s' % (a0, ' '.join(row)))
hull = gm.hull_pieces(spec, A)
cs = next(g for g in spec['garments'] if g['name'] == 'collar')
P = gm._hull_points(hull, cs)
ax = loft.Axis((nb[0], nb[1], 0.0), (0, 0, -1), (0, -1, 0))
top = gm.hull_edge(P, ax, n=cs.get('neck_sectors', 36), q=cs.get('neck_q', 3.0), low=False,
                   smooth=cs.get('neck_smooth', 1.5), min_pts=cs.get('neck_min_pts', 10))
print('hull collar neckline z (L) by azimuth (loft theta):', ' '.join('%d:%.3f' % (a, (top(math.radians(a)) - ez) / L) for a in range(-180, 181, 30)))
top_s = next(g for g in spec['garments'] if g['name'] == 'top')
for c in top_s.get('cuts', []):
    if c[0] == 'neck':
        h, tl = gm.bone_seg(A, 'neck'); zc = (h + (tl - h) * c[1])[2] + c[3] * L
        print('jacket neck cut z', round((zc - ez) / L, 3))
