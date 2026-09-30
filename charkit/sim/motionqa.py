"""Motion QA: the loose garments moving as the style profile says they move, measured at motion QA's leg poses (the kick
and the squat), gated like any check (docs/workstreams/xpbd.md, round 2).

The style profile's physics.garment_motion (charkit/styles; a spec's own `physics.garment_motion` laid over it) names
the method and its liberty:
  method      'skinned' (the rig's skinning as shipped: a profile that says nothing), 'xpbd_hips' (XPBD cloth held toward
              the drawn shape carried by the pelvis, the legs and the torso pushing it: the anime default), 'xpbd_anime'
              (held toward the template as skinned), 'xpbd_physics' (no hold: the realistic default)
  hold_shape  the hold's strength (0..1: 0.8 sags 0.025 L under its own weight; charkit.sim.settings)
  loose       the garment kinds that move as cloth (the skirt is the layer the panels lie on)

Per pose and per skirt-kind garment, over the motion (1 s settled at rest, into the pose over 0.4 s, held 0.6 s, 60 fps;
measured every 6 frames and at the end):
  motion_<pose>_<garment>_inside   the worst share of the garment's surface vertices newly inside the posed skin (not
                                   inside at rest as shipped: the top tucked under the band is), signed by winding number
                                   against the build's skin subdivided once, its weights carried, posed the same way
  motion_<pose>_<garment>_stretch  the worst p99 of the coarse mesh's edge stretch |l / l0 - 1|
The panels' numbers are in the table (not graded: their known-bad, the graph's spring chains, isn't the rig's).
Calibrated in charkit/calib/motion.py: the held solve with its nuisance settings nudged must PASS; the plain skinned
skirt (and, for the kick's penetration, the skirt carried by the pelvis alone) must FAIL.
"""
import json, os, time

LIMITS = {'inside': (0.01, 0.03), 'stretch': (0.25, 0.5)}       # (PASS at or under, WARN at or under): see calib records
POSES = ('kick', 'squat')
EVERY = 6


def grade(kind, v):
    p, w = LIMITS[kind]
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def settings(B):
    """the build's garment motion: its style profile's physics.garment_motion under the spec's own (the profile's file
    read into the bundle's open recordings, so a cached part is keyed on it). -> dict(method, hold_shape, loose, style)."""
    from .. import styles
    spec = B.spec
    style = spec.get('style') or 'anime'
    p = os.path.join(styles.HERE, style + '.json')
    for r in B._reads:
        r.files.add(os.path.abspath(p))
    S = styles.load(style)
    gm = dict(method='skinned', hold_shape=0.0, loose=[])
    gm.update((S.get('physics') or {}).get('garment_motion') or {})
    gm.update(((spec.get('physics') or {}).get('garment_motion')) or {})
    gm['style'] = style
    return gm


def loose_pieces(B, gm):
    """the loose garments by kind, the skirt kinds first (the layer the panels lie on) -> [name]."""
    kinds = list(gm.get('loose') or ())
    gs = [g for g in B.spec.get('garments') or () if g.get('kind') in kinds]
    return [g['name'] for g in sorted(gs, key=lambda g: (kinds.index(g['kind']), g['name']))]


def solve(S, pose, gm, every=EVERY, **over):
    """one method through a pose's schedule -> [measured frame: {piece: measures}] (motion.Scene.measure's)."""
    from ..evalmesh import POSES as PS
    from . import motion
    M = motion.method(S, gm['method'], style=gm.get('style', 'anime'), hold_shape=gm.get('hold_shape'), **over)
    fs, n0 = S.schedule(pose, **{k: over[k] for k in ('ramp',) if k in over})
    rows = []
    for k, f in enumerate(fs):
        D = S.rig.skinning(PS[pose], f)
        fin, co = M.frame(D, 1.0 / motion.FPS)
        if k >= n0 - 1 and ((k - n0 + 1) % every == 0 or k == len(fs) - 1):
            r = S.measure(D, fin, co)
            r['_frame'] = k - n0 + 1
            rows.append(r)
    return rows


def checks_of(rows, pieces, pose):
    """the graded checks (the skirt kinds) and the table's numbers (every loose piece) from solve()'s rows."""
    C, T = {}, {}
    for n in pieces:
        ws = max(rows, key=lambda r: r[n]['new_share'])
        wt = max(rows, key=lambda r: r[n]['stretch_p99'])
        e = rows[-1][n]
        T[n] = dict(inside=round(ws[n]['new_share'], 5), inside_frame=ws['_frame'],
                    depth=round(max(r[n]['new_depth'] for r in rows), 5), stretch_p99=round(wt[n]['stretch_p99'], 5),
                    stretch_frame=wt['_frame'], stretch_max=round(max(r[n]['stretch_max'] for r in rows), 5),
                    end=dict(inside=round(e['new_share'], 5), depth=round(e['new_depth'], 5),
                             stretch_p99=round(e['stretch_p99'], 5)))
    return C, T


def scene(B, pieces, log=None):
    """the motion scene of a bundle, made once per bundle (the calibration's runs share it)."""
    from . import motion
    return B.memo(('sim.motion.Scene', tuple(pieces)), lambda: motion.Scene(B, pieces=pieces,
                                                                           log=log or (lambda *a: None)))


def measure(B, gm=None, poses=POSES, log=None, **over):
    """-> (table, checks): the loose garments at each pose under the build's garment motion (gm: another, for the
    calibration's stand-ins)."""
    from . import motion
    t0 = time.time()
    gm = dict(gm or settings(B))
    pieces = loose_pieces(B, gm) or list(motion.PIECES)
    S = scene(B, pieces, log)
    skirts = [n for n in pieces if next((g.get('kind') for g in B.spec.get('garments') or () if g['name'] == n),
                                        None) == 'skirt']
    table = dict(method=gm['method'], hold_shape=gm.get('hold_shape'), style=gm.get('style'), pieces=pieces,
                 poses={}, colliders=[dict(name=c['name'], r_L=round(c['r'] / S.L, 4),
                                           err_p90_L=round(c['err_p90'] / S.L, 4)) for c in S.colliders('body')])
    checks = {}
    for pose in poses:
        rows = solve(S, pose, gm, **over)
        _, T = checks_of(rows, pieces, pose)
        table['poses'][pose] = T
        for n in skirts:
            t = T[n]
            checks['%s_%s_inside' % (pose, n)] = dict(
                value=t['inside'], status=grade('inside', t['inside']), depth_L=t['depth'], frame=t['inside_frame'],
                method=gm['method'])
            checks['%s_%s_stretch' % (pose, n)] = dict(
                value=t['stretch_p99'], status=grade('stretch', t['stretch_p99']), max=t['stretch_max'],
                frame=t['stretch_frame'], method=gm['method'])
    table['seconds'] = round(time.time() - t0, 1)
    return table, checks


try:
    from ..registry import qa_part
except ImportError:                                  # (outside the package)
    def qa_part(*a, **k):
        return lambda f: f


@qa_part('motion', order=2500, prefix='motion_', table='motion')
def motion_qa(B, design=None, out=None):
    """the loose garments (the skirt and the panels) at the kick and the squat, moved as the style profile says
    (physics.garment_motion): the skirt's new penetration into the skin and its stretch, worst over the motion."""
    table, checks = measure(B)
    if out:
        json.dump(table, open(os.path.join(out, 'qa_motion.json'), 'w'), indent=1)
    return table, checks
