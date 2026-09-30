"""The body, garment and hair knobs, and what each does to the silhouette (docs/CHARKIT.md §4): an inventory of every knob
the body, the garment builders and the hair read (the spec's value or the builder's default, a step and a range), and a
sensitivity table measured through the fast evaluator (charkit.bodyeval): each knob moved a step each way from the spec,
every silhouette measurement (bodymeasure.MEASURES) read, the central difference kept. Measurements that no knob moves, or
that no single knob can move far enough within its range to close today's error, are listed as needing a capability.

    python -m charkit bodysens SPEC [--out DIR] [--only body,garments,hair] [--pieces skirt,top]
        -> DIR/sensitivity.json (the table) and DIR/sensitivity.md (a readable summary)
    python -m charkit bodysens --report DIR/sensitivity.json      # the summary again

Knob paths are bodyeval's dotted paths (list items by name or kind): body.proportions.leg, garments.skirt.flare,
garments.top.cuts.0.3, hair.shape.below, accessories.star.size.
"""
import ast, json, os, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (step, lo, hi, note); None for a range = no bound
BODY = {
    'height_m': (0.05, 1.3, 1.9, 'metres'), 'heads_tall': (0.2, 4.5, 8.0, 'head lengths'),
    'sex': (0.1, 0.0, 1.0, 'MakeHuman macro'), 'age': (0.05, 0.5, 1.0, 'MakeHuman macro'),
    'muscle': (0.1, 0.0, 1.0, 'MakeHuman macro'), 'weight': (0.1, 0.0, 1.0, 'MakeHuman macro'),
    'height': (0.1, 0.0, 1.0, 'MakeHuman macro'), 'ideal': (0.1, 0.0, 1.0, 'MakeHuman macro'),
    'ethnic.0': (0.1, 0.0, 1.0, 'MakeHuman macro'), 'ethnic.1': (0.1, 0.0, 1.0, 'MakeHuman macro'),
}
PROPORTION = (0.05, 0.5, 1.6, 'scale along / across the bones')
POSE_KNOBS = {'arm_down': (3.0, -20.0, 40.0, 'the rest pose: arms lowered at the shoulders, degrees'),
        'elbow': (3.0, -20.0, 40.0, 'the rest pose: forearms bent in at the elbows, degrees'),
        'leg_in': (1.5, -10.0, 15.0, 'the rest pose: legs brought together at the hips, degrees')}

# per garment kind: knob -> (default, step, lo, hi, note). Defaults are the builders' (charkit/garments.py).
GARMENT = {
    'shell': {'offset': (0.012, 0.004, 0.0, 0.06, 'lift off the body, L'),
              'thick': (0.008, 0.004, 0.0, 0.04, 'solidify inward (the build only; no silhouette)')},
    'band': {'t': (0.5, 0.03, 0.0, 1.0, 'along the bone'), 'width': (0.08, 0.02, 0.01, 0.4, 'L'),
             'offset': (0.01, 0.005, 0.0, 0.1, 'L'), 'flare': (0.0, 0.01, -0.05, 0.1, 'far edge wider, L'),
             'thick': (0.02, 0.005, 0.0, 0.08, 'L'), 'segs': (48, 8, 12, 96, 'resolution'),
             'radius': (None, 0.01, 0.01, 0.5, 'a fixed radius, L (unset: the limb\'s own plus offset)')},
    'shoe': {'offset': (0.02, 0.005, 0.0, 0.08, 'L'), 'sole': (0.03, 0.01, 0.0, 0.15, 'L'),
             'instep': (0.10, 0.02, 0.0, 0.3, 'L'), 'rows': (22, 4, 8, 40, 'resolution'), 'segs': (28, 4, 12, 48, 'resolution')},
    'belt': {'waist': (0.55, 0.05, 0.0, 1.8, 'hips -> spine (past 1: up the chest)'), 'width': (0.12, 0.02, 0.02, 0.4, 'L'),
             'offset': (0.03, 0.005, 0.0, 0.1, 'L'), 'thick': (0.02, 0.005, 0.0, 0.08, 'L'), 'cols': (96, 16, 32, 192, 'resolution')},
    'skirt': {'waist': (0.55, 0.05, 0.0, 1.8, 'hips -> spine (past 1: up the chest)'), 'length': (0.9, 0.05, 0.3, 2.0, 'L'),
              'back': (0.0, 0.05, 0.0, 0.8, 'longer back, L'), 'flare': (38.0, 3.0, 0.0, 70.0, 'degrees'),
              'pleats': (24, 2, 0, 48, 'count'), 'pleat': (0.05, 0.01, 0.0, 0.15, 'depth, L'),
              'panel': (0.0, 0.1, 0.0, 1.5, 'front panel half-width, radians (colour only)'),
              'offset': (0.015, 0.005, 0.0, 0.1, 'L'), 'cols': (144, 24, 48, 288, 'resolution'), 'rows': (16, 4, 4, 32, 'resolution')},
    'sleeve': {'t0': (-0.02, 0.03, -0.3, 0.5, 'along the upper arm'), 't1': (0.45, 0.05, 0.1, 1.2, 'along the upper arm'),
               'puff': (0.9, 0.1, 0.0, 2.5, 'swell'), 'offset': (0.012, 0.005, 0.0, 0.08, 'L'),
               'armhole': (0.65, 0.1, 0.0, 1.0, 'root turned toward the armhole'),
               'rows': (14, 2, 6, 28, 'resolution'), 'segs': (40, 8, 12, 80, 'resolution')},
    'collar': {'v_depth': (0.62, 0.05, 0.1, 1.2, 'L'), 'side_depth': (0.30, 0.05, 0.05, 0.8, 'L'),
               'back_depth': (0.5, 0.05, 0.1, 1.2, 'L'), 'v_half': (36.0, 4.0, 0.0, 70.0, 'degrees'),
               'rise': (0.0, 0.02, -0.2, 0.2, 'L'), 'offset': (0.03, 0.005, 0.0, 0.1, 'L'),
               'stripe.0': (0.72, 0.05, 0.0, 1.0, 'stripe start (colour only)'), 'stripe.1': (0.86, 0.05, 0.0, 1.0, 'stripe end (colour only)'),
               'cols': (96, 16, 32, 192, 'resolution'), 'rows': (12, 2, 4, 24, 'resolution')},
    'bow': {'size': (0.5, 0.05, 0.1, 1.5, 'L'), 'height': (0.72, 0.05, 0.0, 1.2, 'chest -> upper chest'),
            'offset': (0.03, 0.01, 0.0, 0.15, 'L'), 'tail': (0.62, 0.05, 0.1, 1.5, 'the tails\' length, a share of size')},
    'panel': {'az': (180.0, 6.0, -180.0, 180.0, 'degrees round the waist (0 the front, + her left)'),
              'width': (0.4, 0.04, 0.05, 1.5, 'L round the ring'), 'length': (1.0, 0.05, 0.2, 2.5, 'L'),
              'flare': (30.0, 3.0, 0.0, 70.0, 'degrees'), 'spread': (0.2, 0.05, 0.0, 1.0, 'widening at the hem'),
              'offset': (0.02, 0.005, 0.0, 0.1, 'L'), 'waist': (0.5, 0.05, 0.0, 1.8, 'hips -> spine (past 1: up the chest)'),
              'cols': (24, 4, 8, 48, 'resolution'), 'rows': (16, 4, 4, 32, 'resolution')},
}
COLOURS = ('color', 'panel_color', 'hem_color', 'stripe_color', 'sole_color', 'shade')
NOT_KNOBS = ('kind', 'name', 'side', 'bone', 'region', 'cuts', 'smooth', 'panel', 'sole', 'repeat', 'line', 'hem', 'steps',
             # a hull-sourced piece's settings (garments.hull_pieces): where its shape comes from and how it's read off
             # the hull, not what a fit moves
             'source', 'piece', 'fold', 'under', 'tuck', 'hem_q', 'hem_drop', 'hem_smooth', 'waist_q', 'span', 'step',
             'round', 'nth', 'conform', 'conform_k', 'cell', 'reach', 'lift', 'mass', 'q', 'occluders', 'occluded_span', 'front_band', 'panel_mass', 'overlap', 'drawn', '_spec', 'knot', 'lift', 'round_xs', 'roll', 'clear', 'over', 'tail', 'sweep', 'out', 'taper', 'tail_rows', 'trim', 'band', 'step_h', 'bones', 'narrow', 'train', 'gap', 'blend', 'aline',
             'tip', 'stair', 'az_waist', 'neckline', 'neck_sectors', 'neck_q', 'neck_smooth', 'neck_min_pts', 'neck_drop',
             'keep_edge', 'v_edge', 'conform_smooth', 'front_smooth', 'clear_hands', 'clear_slope')

# hair.shape (mesh / geom mode): knob -> (default, step, lo, hi, note)
HAIR_SHAPE = {
    'below': (0.25, 0.03, 0.0, 0.8, 'the hair kept below the chin, L'),
    'shoulder_x': (0.16, 0.02, 0.05, 0.4, 'no hair beyond this |x| below the chin, m'),
    'clear_skin': (0.025, 0.005, 0.0, 0.08, 'outside our skin by at least this, L (select outside)'),
    'clear': (0.02, 0.01, -0.05, 0.1, 'face cull clearance, L'),
    'eye_depth': (0.01, 0.01, -0.05, 0.08, 'the alignment: eyes behind the face plane, L'),
    'spacing': (1.0, 0.02, 0.8, 1.2, 'the alignment: eye spacing scale'),
    'smooth': (6, 2, 0, 20, 'smoothing iterations'), 'smooth_factor': (0.5, 0.1, 0.0, 1.0, 'smoothing factor'),
    'min_part': (150, 20, 1, 1000, 'faces: smaller loose pieces dropped'),
    'decimate': (0.5, 0.1, 0.1, 1.0, 'Blender decimation ratio (not modelled: silhouette-neutral, measured)'),
}
HAIR_SHAPE_OTHER = {
    'glb': 'the generated shape (a file)', 'mode': 'mesh | geom | analytic locks (categorical, measured as variants)',
    'select': 'outside | exclude | hue (categorical)', 'hue': 'hue selection (select hue only)', 'sat': 'hue selection',
    'colors': 'colour selection (no select)', 'max_d': 'colour selection (no select)', 'carries': 'accessories the shape carries',
    'voxel': 'a voxel remesh (Blender only; 0 on Clawd)', 'vox': 'volume selection (Blender only)',
    'inflate': 'volume selection (Blender only)', 'under': 'the cranium fit at resolve time (a head knob)',
    'fit_cranium': 'the cranium fit at resolve time', 'normal_mix': 'shading', 'cap': 'geom mode: keep the analytic cap',
    'geom': 'geom mode: the extracted part', 'geom_opts': 'geom mode: extraction options', 'normals': 'shading',
    'shape_min': 'MeshVolume bound (accessories only)', 'shape_max': 'MeshVolume bound (accessories only)',
    'crown_el': 'MeshVolume crown (accessories only)',
}
# the analytic volume (the cap under generated hair, and the locks' ground) and the locks
HAIR_VOLUME = {'thick': (1.0, 0.1, 0.5, 2.0, 'volume thickness'), 'crown': (1.0, 0.1, 0.5, 2.0, 'crown height'),
               'length': (0.25, 0.05, 0.0, 1.0, 'hang below the jaw, L'), 'flare': (0.08, 0.04, 0.0, 0.4, 'hang bulge'),
               'part': (6.0, 4.0, -40.0, 40.0, 'degrees')}
ACCESSORY = {'az': (0.0, 4.0, -180.0, 180.0, 'degrees'), 'el': (0.0, 4.0, -40.0, 90.0, 'degrees'),
             'size': (0.2, 0.03, 0.02, 0.8, 'L'), 'tilt': (0.0, 6.0, -90.0, 90.0, 'degrees'),
             'lean': (0.0, 6.0, -60.0, 60.0, 'degrees'), 'lift': (0.0, 0.01, -0.05, 0.1, 'L')}
NOISE = {'iou': 0.0015, 'angle': 0.15, 'L': 0.003, 'ratio': 0.004, 'sheet': 0.004}   # below: rasterisation noise
UNBOUNDED = 5                                                  # steps a knob without a bound is trusted to go


def _noise(m):
    return info(m)[2]


# ------------------------------------------------------------------------------------------------------------ inventory
def inventory(spec):
    """every body, garment and hair knob of a spec: [dict(path, group, piece, value, step, lo, hi, note, kind)], kind
    'geometry' (measured), 'colour' (palette, not a silhouette), 'resolution', 'inactive' (read by a path this spec
    doesn't take) or 'categorical'."""
    from .body import DEFAULT_BODY
    from .bodyeval import get_knob
    K = []

    def add(path, group, piece, value, step, lo, hi, note, kind='geometry'):
        K.append(dict(path=path, group=group, piece=piece, value=value, step=step, lo=lo, hi=hi, note=note, kind=kind))
    # the body
    for k, (st, lo, hi, note) in BODY.items():
        top = k.split('.')[0]
        d = DEFAULT_BODY[top]
        d = d[int(k.split('.')[1])] if '.' in k else d
        add('body.' + k, 'body', None, get_knob(spec, 'body.' + k, d), st, lo, hi, note)
        if '.' in k and get_knob(spec, 'body.' + top) is None:          # a list the spec leaves at its default
            K[-1]['variant'] = {'body.' + top: list(DEFAULT_BODY[top])}
    for k, d in DEFAULT_BODY['proportions'].items():
        st, lo, hi, note = PROPORTION
        add('body.proportions.' + k, 'body', None, get_knob(spec, 'body.proportions.' + k, d), st, lo, hi, note)
    for k, d in DEFAULT_BODY['pose'].items():
        st, lo, hi, note = POSE_KNOBS[k]
        add('body.pose.' + k, 'body', None, get_knob(spec, 'body.pose.' + k, d), st, lo, hi, note)
    # the garments: every piece's knobs (its own value or the builder's default)
    for s in spec.get('garments') or []:
        nm, kind = s['name'], s['kind']
        base = 'garments.%s.' % nm
        for k, (d, st, lo, hi, note) in GARMENT[kind].items():
            v = get_knob(s, k, d)
            kk = 'resolution' if note == 'resolution' else 'colour' if 'colour only' in note else \
                'inactive' if 'build only' in note or v is None else 'geometry'
            add(base + k, 'garments', nm, v, st, lo, hi, note, kk)
        if kind == 'shell':
            for i, (bone, t0, t1) in enumerate(s.get('region', [])):
                for j, t in ((1, t0), (2, t1)):
                    if -0.5 < t < 1.2:
                        add(base + 'region.%d.%d' % (i, j), 'garments', nm, t, 0.04, -0.5, 1.5,
                            'region %s: %s along the bone' % (bone, 'start' if j == 1 else 'end'))
            for i, c in enumerate(s.get('cuts', [])):
                add(base + 'cuts.%d.1' % i, 'garments', nm, c[1], 0.05, -0.5, 1.5, 'cut at %s: t along the bone' % c[0])
                add(base + 'cuts.%d.3' % i, 'garments', nm, c[3], 0.03, -0.5, 0.5, 'cut at %s: offset, L' % c[0])
            if 'panel' in s:
                for k in ('half_top', 'half_bottom'):
                    add(base + 'panel.' + k, 'garments', nm, s['panel'][k], 0.02, 0.0, 0.5, 'panel (colour only)', 'colour')
        for k in COLOURS:
            if k in s:
                add(base + k, 'garments', nm, s[k], None, 0.0, 1.0, 'colour', 'colour')
    # the hair
    hs = spec.get('hair') or {}
    shape = hs.get('shape')
    mode = shape.get('mode', 'mesh') if shape else 'analytic'
    if shape:
        for k, (d, st, lo, hi, note) in HAIR_SHAPE.items():
            kind = 'inactive' if k == 'decimate' or (k == 'clear_skin' and shape.get('select') != 'outside') else 'geometry'
            if mode == 'geom' and k in ('smooth', 'smooth_factor', 'min_part', 'decimate', 'clear_skin', 'clear'):
                kind = 'inactive'
            add('hair.shape.' + k, 'hair', 'shape', shape.get(k, d), st, lo, hi, note, kind)
        for k, note in HAIR_SHAPE_OTHER.items():
            add('hair.shape.' + k, 'hair', 'shape', shape.get(k), None, None, None, note,
                'categorical' if k in ('mode', 'select') else 'inactive')
    for k, (d, st, lo, hi, note) in HAIR_VOLUME.items():
        add('hair.' + k, 'hair', 'volume', hs.get(k, d), st, lo, hi,
            note + (' (the cap under the generated hair)' if shape else ''), 'geometry' if (not shape or k != 'part') else 'inactive')
    from .hair import DEFAULT_STYLE
    for r in lock_knobs(hs):
        top = r['path'].split('.')[1]
        var = {} if top in hs or top not in DEFAULT_STYLE else {'hair.' + top: json.loads(json.dumps(DEFAULT_STYLE[top]))}
        if shape:                                     # measured on the analytic variant (hair.shape off), see sensitivity
            var['hair.shape'] = None
            r = dict(r, note=r['note'] + ' (inactive in hair.shape.mode %s: measured with the analytic locks)' % mode)
        if var:
            r['variant'] = var
        K.append(r)
    for k in ('lit', 'shade', 'deep', 'ring', 'line', 'strand', 'inner'):
        if k in (spec.get('hair_colors') or {}):
            add('hair_colors.' + k, 'hair', 'colours', spec['hair_colors'][k], None, 0.0, 1.0, 'colour', 'colour')
    carried = set(shape.get('carries', ['bun'])) if shape and mode in ('mesh', 'geom') else set()
    for i, a in enumerate(spec.get('accessories') or []):
        nm = a.get('name') or ('%s_%d' % (a['kind'], i))
        for k, (d, st, lo, hi, note) in ACCESSORY.items():
            kind = 'inactive' if a['kind'] in carried else 'geometry'
            add('accessories.%d.%s' % (i, k), 'hair', nm, a.get(k, d), st, lo, hi,
                note + (' (carried by the generated hair)' if a['kind'] in carried else ''), kind)
        for k in ('color', 'line'):
            if k in a:
                add('accessories.%d.%s' % (i, k), 'hair', nm, a[k], None, 0.0, 1.0, 'colour', 'colour')
    return K


def lock_knobs(hs):
    """the analytic hairstyle's knobs (charkit.hair.DEFAULT_STYLE, the spec's values over it): every number in it, lists
    and dicts walked (bangs.tips.2.1 is the third fringe tip's elevation)."""
    from .hair import _style
    S = _style({k: v for k, v in (hs or {}).items() if k != 'shape'})
    out = []
    steps = {'part': 4.0, 'flick': 0.02, 'wave': 0.2, 'length': 0.05, 'thick': 0.1, 'crown': 0.1, 'flare': 0.04,
             'count': 2, 'inner': 2, 'width': 0.02, 'sway': 4.0, 'drop': 4.0, 'az': 6.0, 'bow': 0.02, 'tuck': 0.01,
             'tip': 0.05, 'sharp': 0.2}

    def walk(path, v, key):
        if isinstance(v, bool) or v is None or isinstance(v, str):
            out.append(dict(path=path, group='hair', piece='locks', value=v, step=None, lo=None, hi=None,
                            note='the analytic locks (a switch)', kind='categorical'))
        elif isinstance(v, (int, float)):
            if key in ('seed',):
                out.append(dict(path=path, group='hair', piece='locks', value=v, step=None, lo=None, hi=None,
                                note='unused by the generator', kind='inactive'))
                return
            st = steps.get(key)
            if st is None:                                  # (az, el) degrees in lists, a width scale in a tip triple
                st = 0.1 if (isinstance(v, float) and abs(v) <= 2 and '.tips.' in path and path.endswith('.2')) else 4.0
            isint = isinstance(v, int) and float(st).is_integer() and key in ('count', 'inner')
            out.append(dict(path=path, group='hair', piece='locks', value=v, step=st, lo=0 if isint else None, hi=None,
                            note='the analytic locks', kind='geometry'))
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                walk(path + '.' + k2, v2, k2)
        elif isinstance(v, (list, tuple)):
            for i, v2 in enumerate(v):
                walk('%s.%d' % (path, i), v2, key)
    for k, v in S.items():
        if k in ('silhouette',):
            out.append(dict(path='hair.' + k, group='hair', piece='locks', value='(fitted)', step=None, lo=None, hi=None,
                            note='the design outline the volume is fitted to (charkit.refs.fit)', kind='inactive'))
            continue
        if k in HAIR_VOLUME:
            continue                                        # listed with the volume
        walk('hair.' + k, v, k)
    return out


def builder_keys():
    """the spec keys each garment builder reads (charkit/garments.py, parsed): {kind: set(keys)}; the inventory test holds
    GARMENT to it, so a new builder knob can't go unlisted."""
    src = open(os.path.join(ROOT, 'charkit', 'garments.py')).read()
    out = {}
    for fn in ast.parse(src).body:
        if not isinstance(fn, ast.FunctionDef) or fn.name not in GARMENT:
            continue
        keys = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'get' and \
                    isinstance(n.func.value, ast.Name) and n.func.value.id == 'spec' and n.args and \
                    isinstance(n.args[0], ast.Constant):
                keys.add(n.args[0].value)
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == 'spec' and \
                    isinstance(n.slice, ast.Constant):
                keys.add(n.slice.value)
            if isinstance(n, ast.Tuple) and len(n.elts) == 2 and isinstance(n.elts[0], ast.Constant) and \
                    isinstance(n.elts[0].value, str) and isinstance(n.elts[1], ast.Constant) and \
                    isinstance(n.elts[1].value, (int, float)):
                keys.add(n.elts[0].value)                        # (key, default) pairs read in a loop (the collar)
        out[fn.name] = keys
    return out


# ---------------------------------------------------------------------------------------------------------- sensitivity
def _eval(E, knobs, sheet=True):
    """the measurements at a knob setting: bodymeasure.MEASURES (against the generated shape) and the model sheet's body
    checks' values (body_<view>_<check>, charkit.bodyqa)."""
    from . import bodyeval
    G = E.geometry(knobs)
    M = bodyeval.measures(G, E.qa(G, labels=True))
    if sheet:
        for k, v in E.sheet_checks(G, palette=False).items():
            x = v.get('value')
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                M[k] = float(x)
    return M


def info(m):
    """a measurement's (target, tolerance, noise floor, description): ours minus the target's (MEASURES) toward 0, IoUs
    toward 1; the sheet's checks as charkit.bodyqa grades them (lengths in L, width ratios, IoUs, the arms' angle)."""
    from .bodymeasure import MEASURES
    from .bodyqa import LIMITS as B
    if m in MEASURES:
        if 'iou' in m:
            return 1.0, 0.02, NOISE['iou'], MEASURES[m]
        if 'angle' in m:
            return 0.0, 0.5, NOISE['angle'], MEASURES[m]
        return 0.0, 0.02, NOISE['L'], MEASURES[m]
    if m.startswith('body_'):
        view = next((v for v in ('three_quarter', 'front', 'profile', 'back') if m.startswith('body_%s_' % v)), '?')
        chk = m[len('body_%s_' % view):]
        desc = 'model sheet, %s view: %s' % (view.replace('_', ' '), chk)
        if chk.startswith('iou'):
            return 1.0, 1 - B['iou' if chk == 'iou' else 'iou_part'][0], NOISE['iou'], desc + ' (IoU)'
        if chk in ('skirt_width', 'hair_width', 'sleeves'):
            return 1.0, B['width'][0], NOISE['ratio'], desc + ' (ours / the design\'s)'
        if chk == 'arms':
            return 0.0, 3.0, NOISE['angle'], desc + ' (degrees, ours - the design\'s)'
        return 0.0, B['length'][0], NOISE['sheet'], desc + ' (L, ours - the design\'s)'
    return 0.0, 0.02, NOISE['L'], m


def _clip(v, lo, hi):
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def sensitivity(E, knobs=None, only=None, pieces=None, log=lambda *a: print(*a, flush=True)):
    """the table: for every geometry knob, each measurement's change per step (central difference over +- one step,
    clipped to the knob's range). -> dict(base (measurements at the spec), knobs [inventory rows + d {measure: change per
    step}, t (seconds)], variants {name: d})."""
    from . import bodyeval
    K = knobs or inventory(E.spec)
    t0 = time.time()
    base = _eval(E, {})
    bases = {}                                          # a variant's own base measurements
    rows = []
    for k in K:
        k = dict(k)
        if only and k['group'] not in only or pieces and k['piece'] not in pieces:
            continue
        if k['kind'] not in ('geometry', 'resolution') or not isinstance(k['value'], (int, float)) or k['step'] is None:
            rows.append(k)
            continue
        t = time.time()
        v = k['value']
        isint = isinstance(v, int) and not isinstance(v, bool) and float(k['step']).is_integer()
        up, dn = _clip(v + k['step'], k['lo'], k['hi']), _clip(v - k['step'], k['lo'], k['hi'])
        if isint:
            up, dn = int(round(up)), int(round(dn))
        span = (up - dn) / k['step'] if up != dn else 0
        if span == 0:
            k['d'] = {}
            rows.append(k)
            continue
        var = k.get('variant') or {}
        if var:
            vk = json.dumps(var, sort_keys=True)
            if vk not in bases:
                bases[vk] = _eval(E, var)
        Mu = _eval(E, dict(var, **{k['path']: up}))
        Md = _eval(E, dict(var, **{k['path']: dn}))
        k['d'] = {m: float((Mu[m] - Md[m]) / span) for m in base if m in Mu and m in Md and
                  np.isfinite(Mu[m]) and np.isfinite(Md[m])}
        k['t'] = round(time.time() - t, 2)
        top = sorted(((abs(d) / _noise(m), m, d) for m, d in k['d'].items() if not m.endswith(('_ours', '_target'))),
                     reverse=True)[:3]
        log('%-40s %8s  %5.1fs  %s' % (k['path'], k['value'], k['t'], ', '.join('%s %+.4f' % (m, d) for _, m, d in top)))
        rows.append(k)
    variants = {}
    shape = (E.spec.get('hair') or {}).get('shape')
    if shape and (not only or 'hair' in only) and not pieces:
        for name, kn in (('hair.shape.mode=geom', {'hair.shape.mode': 'geom'}), ('hair.shape=none (analytic locks)',
                                                                                 {'hair.shape': None})):
            if kn.get('hair.shape.mode', '-') == shape.get('mode'):
                continue
            try:
                t = time.time()
                M = _eval(E, kn)
                variants[name] = {m: float(M[m] - base[m]) for m in base
                                  if m in M and np.isfinite(M[m]) and np.isfinite(base[m])}
                log('%-40s %5.1fs' % (name, time.time() - t))
            except Exception as e:                         # a variant that can't be evaluated says why
                variants[name] = {'error': '%s: %s' % (type(e).__name__, e)}
    return dict(base=base, variant_bases=bases, knobs=rows, variants=variants, seconds=round(time.time() - t0, 1))


def _tol(m):
    return info(m)[1]


POSE = ('arm_angle', 'leg_angle', 'body_front_arms', 'body_back_arms')   # limb directions: only body.pose turns a limb


def capabilities(T, share=0.5):
    """what the knobs can do about each measurement's error, linearised: -> [dict(measure, value, gap, status, best,
    reach, cost)]. status: 'ok' (within tolerance); 'no knob moves it' (every change under the noise floor); 'no knob
    reaches it' (the best single knob, within its range, closes under `share` of the gap); 'no knob turns a limb' (a pose
    measurement, in a table without the rest-pose knobs: the proportions scale along and across the bones, so a limb's
    direction moves only through what else they change); 'only at a cost' (closing `share` of the gap with the best knob pushes other measurements further out
    of tolerance than it brings this one in, each counted in its own tolerances); 'a knob reaches it'. The aggregate IoUs
    are left to the fit (every knob moves them a little)."""
    base = T['base']
    err = {m: v - info(m)[0] for m, v in base.items() if not m.endswith(('_ours', '_target')) and v is not None and
           np.isfinite(v)}
    out = []
    for m in err:
        gap = -err[m]
        best, reach, moved, bk = None, 0.0, False, None
        for k in T['knobs']:
            d = (k.get('d') or {}).get(m)
            if d is None or k['kind'] != 'geometry' or 'hair.shape' in (k.get('variant') or {}):
                continue                                         # (a variant's knobs act on another character)
            if abs(d) >= _noise(m):
                moved = True
            bound = k['hi'] if d * gap > 0 else k['lo']
            room = UNBOUNDED if bound is None else abs(bound - k['value']) / k['step']
            if abs(d) * room > reach:
                best, reach, bk = k['path'], abs(d) * room, k
        cost = {}
        if bk is not None and abs(bk['d'][m]) > 0:
            steps = share * gap / bk['d'][m]                         # signed steps closing `share` of the gap
            for j, dj in bk['d'].items():
                if j in err and j != m and 'iou' not in j:
                    e1 = err[j] + steps * dj
                    worse = (abs(e1) - max(abs(err[j]), _tol(j))) / _tol(j)
                    if worse > 0:
                        cost[j] = round(worse, 2)
        gain = share * abs(gap) / _tol(m)
        if abs(gap) <= _tol(m):
            status = 'ok'
        elif 'iou' in m:
            status = 'left to the fit'
        elif not moved:
            status = 'no knob moves it'
        elif m in POSE and not any(k['path'].startswith('body.pose.') for k in T['knobs']):
            status = 'no knob turns a limb'
        elif reach < share * abs(gap):
            status = 'no knob reaches it'
        elif sum(cost.values()) > gain:
            status = 'only at a cost'
        else:
            status = 'a knob reaches it'
        out.append(dict(measure=m, value=base[m], gap=gap, status=status, best=best, reach=reach, cost=cost))
    return out


def report(T, spec_name=''):
    """a readable summary (markdown) of a sensitivity table."""
    L = ['# Knob sensitivity: %s' % spec_name, '',
         'Each knob moved one step each way from the spec through the fast evaluator (charkit/bodyeval.py); the change '
         'per step of each silhouette measurement: against the generated shape (charkit.bodymeasure.MEASURES; widths '
         'and extents are ours minus its, in head lengths L) and against the model sheet (body_<view>_<check>, '
         'charkit.bodyqa). %d knobs, %.0f s.' % (len(T['knobs']), T['seconds']), '']
    L += ['## Today\'s measurements', '', '| measure | value | target | what |', '| --- | --- | --- | --- |']
    for m, v in T['base'].items():
        if v is not None and not m.endswith(('_ours', '_target')):
            L.append('| %s | %.3f | %s | %s |' % (m, v, info(m)[0], info(m)[3]))
    caps = capabilities(T)
    L += ['', '## Needs a capability', '',
          'Measurements off by more than their tolerance that no knob moves, that no single knob can move half way '
          'within its range, that need a limb turned, or that the best knob closes only by pushing other measurements '
          'further out of tolerance (linearised; costs in tolerances):', '',
          '| measure | today | best knob | its reach | status |', '| --- | --- | --- | --- | --- |']
    for c in caps:
        if c['status'] in ('no knob moves it', 'no knob reaches it', 'no knob turns a limb', 'only at a cost'):
            cost = sorted(c['cost'].items(), key=lambda kv: -kv[1])[:3]
            L.append('| %s | %+.3f | %s | %.3f | %s%s |' % (c['measure'], c['value'], c['best'] or '-', c['reach'], c['status'],
                                                         ' (half way pushes out: %s)' % ', '.join('%s %.1f tol' % kv for kv in cost)
                                                         if cost else ''))
    L += ['', 'Reachable by one knob: ' + ', '.join('%s (%s)' % (c['measure'], c['best'])
                                             for c in caps if c['status'] == 'a knob reaches it') + '.', '']
    for g in ('body', 'garments', 'hair'):
        L += ['## %s' % g.capitalize(), '', '| knob | value | step | moves most (change per step) |', '| --- | --- | --- | --- |']
        for k in T['knobs']:
            if k['group'] != g:
                continue
            if k['kind'] not in ('geometry', 'resolution'):
                L.append('| %s | %s | | %s: %s |' % (k['path'], _short(k['value']), k['kind'], k['note']))
                continue
            d = k.get('d') or {}
            top = sorted(((abs(v) / _noise(m), m, v) for m, v in d.items() if not m.endswith(('_ours', '_target'))
                          and abs(v) >= _noise(m)), reverse=True)[:4]
            L.append('| %s | %s | %s | %s |' % (k['path'], _short(k['value']), k['step'],
                                                ', '.join('%s %+.3f' % (m, v) for _, m, v in top) or '(nothing measurable)'))
        L.append('')
    if T.get('variants'):
        L += ['## Variants', '']
        for n, d in T['variants'].items():
            if 'error' in d:
                L.append('- %s: %s' % (n, d['error']))
            else:
                top = sorted(((abs(v) / _noise(m), m, v) for m, v in d.items() if not m.endswith(('_ours', '_target'))),
                             reverse=True)[:6]
                L.append('- %s: %s' % (n, ', '.join('%s %+.3f' % (m, v) for _, m, v in top)))
    return '\n'.join(L) + '\n'


def _short(v):
    s = json.dumps(v)
    return s if len(s) < 28 else s[:25] + '...'


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    from . import bodyeval
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if '--report' in args:                                        # the summary again from a table
        p = bodyeval._abs(opt('--report'))
        T = json.load(open(p))
        open(os.path.join(os.path.dirname(p), 'sensitivity.md'), 'w').write(report(T, os.path.basename(os.path.dirname(p))))
        print('wrote', os.path.join(os.path.dirname(p), 'sensitivity.md'))
        return
    spec_path = args[0]
    E = bodyeval.Evaluator(spec_path)
    name = E.spec.get('name', 'char')
    out = bodyeval._abs(opt('--out', 'charkit/out/bodyeval/%s' % name))
    os.makedirs(out, exist_ok=True)
    only = opt('--only'); only = only.split(',') if only else None
    pieces = opt('--pieces'); pieces = pieces.split(',') if pieces else None
    T = sensitivity(E, only=only, pieces=pieces)
    T['spec'] = spec_path
    json.dump(T, open(os.path.join(out, 'sensitivity.json'), 'w'), indent=1, default=float)
    open(os.path.join(out, 'sensitivity.md'), 'w').write(report(T, name))
    print('wrote', os.path.join(out, 'sensitivity.json'), os.path.join(out, 'sensitivity.md'))
