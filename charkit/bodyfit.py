"""Per-piece fitting of the body, garments and hair (docs/CHARKIT.md §4). The model sheet's body checks and the generated
shape's silhouettes choose the body's proportions and rest pose, each garment piece's cut and the hair's extent, measured
by the fast evaluator (charkit.bodyeval): a couple of seconds an evaluation instead of a Blender build.

    python -m charkit bodyfit SPEC [--out DIR] [--pieces figure,details,hair] [--palette] [--no-outfit] [--no-draft]
                                   [--budget N] [--workers N] [--baseline QA.json] [--free-head] [--write-spec]
    python -m charkit bodyfit SPEC --probe [--out DIR] [--workers N]   # the tune's look before a full fit (probe())
        (--no-draft: the outfit graph's ties and extents without its draft as the start: to continue a fit;
         --free-head: the head count a knob of its own, the face let move with the body)

  1. resolve the spec as `build` does and measure it as the QA does (every shape_*, body_*, sheet_* and palette_*
     check, and each outfit piece's extent per view); start from the outfit graph's draft (charkit.outfit, the
     manifest's `outfit_graph`): the pieces the spec's list lacks added, its measured first guesses for the fit's knobs,
     and the knobs of attached pieces tied (tie: a skirt hung from the waistband shares its waist line);
  2. the sensitivity table (charkit.fitkit's SCHEMA) of every knob, for the triage;
  3. group by group, charkit.fitkit.optimise: the figure (the body with the skirt, its panels and the boots, as where
     the legs show depends on the hem), then the details (sleeves, cuffs, waistband, collar, bow), then the hair (its
     mode, 'mesh' or 'geom', chosen first by its terms' cost). Least squares over the group's knobs against all its terms
     at once: the sheet's four views, the generated shape's six and the pieces' extents against the outfit graph's, so a
     fix in one view that breaks another costs. Each term is weighted by the manifest's authority map, each knob pulled
     toward its template default, every term kept in the status band it starts in (or has in --baseline's QA), and the
     face's model-sheet checks held where they start (the face fit owns them). fitkit.guard then scales a group's change
     back while a check no term aims at reads worse. The head is held as the spec builds it (hold_head): the body's
     knobs set the height so MakeHuman's head keeps its scale and L, and the head count follows the proportions;
  4. --palette: the colour knobs set to the sheet's palette (charkit.paletteqa's tones), each class's knobs solved in
     CIEDE2000, and the garments' shared shade multiplier;
  5. write DIR/NAME.bodyfit.json (the resolved spec with the fitted knobs), DIR/sensitivity.json and
     DIR/bodyfit_report.json and .md: every check before and after, the knobs per group (and which ended at a bound),
     and the triage of what still fails (needs a knob / knob at bound / trade-off). --write-spec writes the fitted knobs
     (and the added pieces) back into SPEC.

The knobs and terms are charkit.fitkit's (the face fit's machinery), with bodyeval's dotted paths so garment pieces and
mirror pairs can be addressed; declare() and fit() have charkit.facefit's interface.
"""
import copy, json, os, time

import numpy as np

from . import fitkit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTHORITY = {'body_silhouette': 'sheet', 'hair_silhouette': 'sheet', 'hair_shape': 'trellis', 'palette': 'sheet',
             'outfit_pieces': 'outfit_graph'}
VIEWS = ('front', 'three_quarter', 'profile', 'back')
FIT_GROUP = {'body': 'figure', 'skirt': 'figure', 'boots': 'figure', 'details': 'details', 'hair': 'hair'}
SCHEDULE = ('figure', 'details', 'hair')        # the figure's pieces together: where the legs show depends on the hem
FIGURE = ('body', 'skirt', 'boots')


# ------------------------------------------------------------------------------------------------------------ knobs
class Knob(fitkit.Knob):
    """fitkit.Knob over several spec paths (a left/right pair, a tied child piece), by bodyeval's dotted paths (list items
    by name, so garment pieces can be addressed). group: the piece it belongs to (body, skirt, boots, details, hair);
    fit() moves it to its fit group (FIT_GROUP) and keeps the piece."""

    def __init__(self, name, paths, default, step, bounds, group, signs=None, offsets=None, derived=()):
        super().__init__(name, (), default, step, bounds, group)
        self.paths, self.piece = list(paths), group
        self.signs = list(signs) if signs else [1] * len(self.paths)     # a mirrored pair: -1 on the other side (azimuths)
        self.offsets = list(offsets) if offsets else [0.0] * len(self.paths)   # a tied piece: its offset from the knob
        self.derived = list(derived)            # paths set from this knob's with the others' (hold_head's), not by it
        self.hold = None                        # fit(): the head to hold (head_hold's), for the body's knobs

    def get(self, spec):
        from .bodyeval import get_knob
        v = get_knob(spec, self.paths[0], None)
        return float(self.default if v is None else (v - self.offsets[0]) * self.signs[0])

    def put(self, spec, value):
        from .bodyeval import set_knob
        for p, sg, o in zip(self.paths, self.signs, self.offsets):
            set_knob(spec, p, round(float(value) * sg + o, 5))
        if self.hold:
            hold_head(spec, self.hold)

    def declare(self):
        D = {'paths': self.paths, 'default': self.default, 'step': self.step, 'bounds': list(self.bounds),
             'group': self.group, 'piece': self.piece}
        if self.derived:
            D['derived'] = self.derived
        return D


# ------------------------------------------------------------------------------------------------------------ the head
HOLD_HEAD = True
HELD = ['body.height_m', 'body.heads_tall']
_CHIN = {}


def _chin(b):
    """the chin's height above the feet in MakeHuman's units (before body.build_body_data scales the body to the height)
    for body knobs b, memoised by every body knob but the height and the head count (which only scale it)."""
    key = json.dumps({k: v for k, v in (b or {}).items() if k not in ('height_m', 'heads_tall')}, sort_keys=True)
    if key not in _CHIN:
        from .body import build_body_data
        B = build_body_data(b, keep_head=True)
        _CHIN[key] = (B['params']['height_m'] - B['head_len']) / B['scale']
    return _CHIN[key]


def head_hold(spec):
    """the head a spec's body builds, to hold while the body's knobs move: its length L (m) and the scale k on
    MakeHuman's head (body.build_body_data's head_len and scale)."""
    from .body import build_body_data
    B = build_body_data(spec.get('body'), keep_head=True)
    return {'L': float(B['head_len']), 'k': float(B['scale'])}


def hold_head(spec, hold):
    """body.height_m and body.heads_tall set so the body's knobs leave the head as it was: the same L and the same scale
    on MakeHuman's head, so anime_head.reshape wraps the same head and the face comes out the same (its thresholds are in
    metres: a head scaled otherwise moved Clawd's face skin by up to 12 px at the eye QA's scale, which flipped
    eye_lid_span's lash component, while the evaluator's measures stayed put). The figure's length in heads follows from
    the proportions: height = L + k * chin."""
    b = spec.setdefault('body', {})
    Hm = hold['L'] + hold['k'] * _chin(b)
    b['height_m'] = round(Hm, 6)
    b['heads_tall'] = round(Hm / hold['L'], 6)
    return spec


def _pairs(spec, kind):
    """a kind's garment pieces, left/right pairs together: [(name, [piece names])]."""
    names = [g['name'] for g in spec.get('garments') or [] if g['kind'] == kind]
    out, seen = [], set()
    for n in names:
        if n in seen:
            continue
        base = n[:-2] if n.endswith(('_L', '_R')) else None
        mates = [m for m in names if base and m[:-2] == base and m.endswith(('_L', '_R'))] if base else [n]
        seen.update(mates)
        out.append((base or n, mates))
    return out


def knobs(spec, hold=HOLD_HEAD):
    """the knobs the body fit owns for a spec, by piece. Defaults are the templates' (body.DEFAULT_BODY, the garment
    builders', hair.shape's); steps and bounds are bodysens's. The neck's width and length are left to the face fit.
    hold: the head held (hold_head): the head count follows the proportions and isn't a knob of its own."""
    from .body import DEFAULT_BODY
    from .bodysens import GARMENT, HAIR_SHAPE, PROPORTION
    held = HELD if hold else ()
    K = [] if hold else [Knob('body.heads_tall', ['body.heads_tall'], DEFAULT_BODY['heads_tall'], 0.1, (5.0, 7.5), 'body')]
    for k in ('leg', 'shin', 'hip', 'leg_slim', 'arm', 'torso', 'waist'):
        K.append(Knob('body.' + k, ['body.proportions.' + k], DEFAULT_BODY['proportions'][k], PROPORTION[0],
                      (0.7, 1.4), 'body', derived=held))
    for k, st, hi in (('arm_down', 3.0, 35.0), ('leg_in', 1.5, 12.0), ('elbow', 3.0, 25.0)):
        K.append(Knob('body.pose.' + k, ['body.pose.' + k], 0.0, st, (0.0, hi), 'body', derived=held))
    for name, ps in _pairs(spec, 'skirt'):
        G = GARMENT['skirt']
        for k in ('flare', 'length', 'back', 'waist'):
            d, st, lo, hi, _ = G[k]
            K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], d, st, (lo, hi), 'skirt'))
    # boots: a shell over the lower legs (its region's start on each shin together), their cuffs and the shoes' soles
    for g in spec.get('garments') or []:
        if g['kind'] == 'shell' and all(r[0].endswith('LowerLeg') for r in g.get('region', [])) and g.get('region'):
            ps = ['garments.%s.region.%d.1' % (g['name'], i) for i in range(len(g['region']))]
            K.append(Knob(g['name'] + '.top', ps, 0.34, 0.03, (0.05, 0.8), 'boots'))
    for name, ps in _pairs(spec, 'band'):
        bones = {next(x for x in spec['garments'] if x['name'] == p)['bone'] for p in ps}
        if all(b.endswith('LowerLeg') for b in bones):
            K.append(Knob(name + '.t', ['garments.%s.t' % p for p in ps], 0.5, 0.03, (0.05, 0.8), 'boots'))
    # the overskirt panels (a mirror pair: the azimuth mirrored), with the skirt
    for name, ps in _pairs(spec, 'panel'):
        sg = [1 if next(x for x in spec['garments'] if x['name'] == p).get('az', 180.0) >= 0 else -1 for p in ps]
        for k in ('length', 'flare', 'width', 'az', 'waist'):
            d, st, lo, hi, _ = GARMENT['panel'][k]
            K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], abs(d) if k == 'az' else d, st,
                          (0.0, 180.0) if k == 'az' else (lo, hi), 'skirt', signs=sg if k == 'az' else None))
    # the details: sleeves, the sleeves' and wrists' cuffs, the waistband, the collar, the bow
    for name, ps in _pairs(spec, 'sleeve'):
        for k in ('puff', 't1'):
            d, st, lo, hi, _ = GARMENT['sleeve'][k]
            K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], d, st, (lo, hi), 'details'))
    for name, ps in _pairs(spec, 'band'):
        bones = {next(x for x in spec['garments'] if x['name'] == p)['bone'] for p in ps}
        if all(b.endswith(('UpperArm', 'LowerArm')) for b in bones):
            for k in ('t', 'width'):
                d, st, lo, hi, _ = GARMENT['band'][k]
                K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], d, st, (lo, hi), 'details'))
    for kind, ks in (('belt', ('waist', 'width')), ('collar', ('v_depth', 'side_depth', 'back_depth')),
                     ('bow', ('size', 'height', 'tail'))):
        for name, ps in _pairs(spec, kind):
            for k in ks:
                d, st, lo, hi, _ = GARMENT[kind][k]
                K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], d, st, (lo, hi), 'details'))
    shape = (spec.get('hair') or {}).get('shape')
    if shape and shape.get('mode') in ('mesh', 'geom'):
        for k in ('below', 'shoulder_x'):
            d, st, lo, hi, _ = HAIR_SHAPE[k]
            K.append(Knob('hair.shape.' + k, ['hair.shape.' + k], d, st, (lo, hi), 'hair'))
    return K


TIES = {                          # a child piece's knob that follows its parent's (outfit graph attachments)
    'waistband': ('waist', ('skirt', 'panel'), 'waist'),         # hung from the waistband: they share its waist line
    'sleeve': ('t1', ('band',), 't'),                            # a cuff at the sleeve's end
    'boot': ('top', ('band',), 't'),                             # a boot cuff at the boot's top
}


def tie(K, spec, graph):
    """knobs tied by the outfit graph's attachments: a piece hung from the waistband shares its waist line (the skirt, its
    back panels); a cuff sits where its parent ends (a sleeve's cuff at the sleeve's end, a boot's cuff at its top). The
    child's knob goes; the parent's carries the child's paths at their current offset from it. -> knobs."""
    if graph is None:
        return K
    from .bodyeval import get_knob
    hand = {m['draft']: m['hand'] for m in (graph.get('comparison') or {}).get('matched', [])}
    kind = {g['name']: g['kind'] for g in spec.get('garments') or []}
    by_path = {p: k for k in K for p in k.paths}
    drop = set()
    for pc in graph['pieces']:
        par = (pc.get('attach') or {}).get('parent')
        if not par:
            continue
        ptype = next((p['type'] for p in graph['pieces'] if p['id'] == par), None)
        rule = TIES.get(ptype)
        child = hand.get(pc['id'], pc['id'])
        if rule is None or kind.get(child) not in rule[1]:
            continue
        pname = hand.get(par, par)
        if ptype == 'boot':
            pname = 'boots'
        pk = next((k for k in K if k.name.split('.')[-1] == rule[0] and any(p.startswith('garments.%s.' % pname) for p in k.paths)), None)
        ck = by_path.get('garments.%s.%s' % (child, rule[2]))
        if pk is None or ck is None or ck is pk or ck.name in drop:
            continue
        v = pk.get(spec)
        for p, sg in zip(ck.paths, ck.signs):
            if p not in pk.paths:
                pk.paths.append(p); pk.signs.append(sg)
                pk.offsets.append(round(float(get_knob(spec, p, ck.default)) - v * sg, 5))
        if ck.group in FIGURE and pk.group not in FIGURE:
            pk.group = pk.piece = ck.group               # (the skirt's hem moves with the waist: fitted with the figure)
        drop.add(ck.name)
    return [k for k in K if k.name not in drop]


# ------------------------------------------------------------------------------------------------------------ terms
GONE = 8.0                      # a term whose check stops measuring (a skirt width the arms hide): the gate reads a check
                                # that disappears as a failure, so it costs more than any reading of it


class Term(fitkit.Term):
    """fitkit.Term with one more reading, 'hold' (floor = (target, start value)): no further from its target than at the
    start, max(0, |v - target| - |v0 - target|) / tol (a check another fit owns, kept); and a check that stops measuring
    reads GONE, not fitkit.MISSING (the fit only keeps terms its start measures)."""

    def residual(self, checks):
        if self.value(checks) is None:
            return GONE, None
        if self.kind != 'hold':
            return super().residual(checks)
        v = self.value(checks)
        t, v0 = self.floor
        return float(max(0.0, abs(v - t) - abs(v0 - t)) / self.tol), v


def _iou_term(check, pw, measure, ref, view, group, weight=None):
    """an IoU read as a residual toward 1: its tolerance the PASS line's distance from 1 (1 = PASS), its WARN line past
    it."""
    p, w = pw
    return Term(check, None, 'floor', 1 - p, measure, ref, view, group, floor=1.0, warn=(1 - w) / (1 - p), weight=weight)


def terms(spec):
    """the checks the body fit answers to, per piece: the sheet's body checks in every view (lengths to 0.08 L, widths
    to 8 %, IoUs toward 1 with their PASS line at 1, the arms' angle to 3 degrees), the generated shape's IoUs (a
    quarter weight for the body, whose silhouette the sheet decides; full for the hair's shape, which the generated shape
    decides), each with its WARN line (fitkit keeps every term in the status band it starts in)."""
    from .bodyqa import LIMITS as B
    from .qa3d import LIMITS as Q
    T = []
    lw, ww = B['length'][1] / B['length'][0], B['width'][1] / B['width'][0]
    for v in VIEWS:
        T += [Term('body_%s_feet' % v, None, 'abs', B['length'][0], 'body_silhouette', 'sheet', v, 'body', warn=lw),
              _iou_term('body_%s_iou' % v, B['iou'], 'body_silhouette', 'sheet', v, 'body'),
              _iou_term('body_%s_iou_skin' % v, B['iou_part'], 'body_silhouette', 'sheet', v, 'body')]
        if v in ('front', 'back'):
            T += [Term('body_%s_leg' % v, None, 'abs', B['length'][0], 'body_silhouette', 'sheet', v, 'body', warn=lw),
                  Term('body_%s_arms' % v, None, 'abs', 3.0, 'body_silhouette', 'sheet', v, 'body', warn=2.0)]
        T += [Term('body_%s_skirt_width' % v, None, 'ratio', B['width'][0], 'body_silhouette', 'sheet', v, 'skirt', warn=ww),
              Term('body_%s_hem' % v, None, 'abs', B['length'][0], 'body_silhouette', 'sheet', v, 'skirt', warn=lw),
              _iou_term('body_%s_iou_outfit' % v, B['iou_part'], 'body_silhouette', 'sheet', v, 'skirt')]
        if v != 'profile':
            T.append(Term('body_%s_hem_mid' % v, None, 'abs', B['length'][0], 'body_silhouette', 'sheet', v, 'skirt', warn=lw))
            T.append(Term('body_%s_sleeves' % v, None, 'ratio', B['width'][0], 'body_silhouette', 'sheet', v, 'details',
                          warn=ww))
        if v in ('front', 'back'):
            T.append(Term('body_%s_boot' % v, None, 'abs', B['length'][0], 'body_silhouette', 'sheet', v, 'boots', warn=lw))
        T += [Term('body_%s_hair_length' % v, None, 'abs', B['length'][0], 'hair_silhouette', 'sheet', v, 'hair', warn=lw),
              Term('body_%s_hair_width' % v, None, 'ratio', B['width'][0], 'hair_silhouette', 'sheet', v, 'hair', warn=ww),
              _iou_term('body_%s_iou_hair' % v, B['iou_part'], 'hair_silhouette', 'sheet', v, 'hair'),
              Term('body_%s_top' % v, None, 'abs', B['length'][0], 'hair_silhouette', 'sheet', v, 'hair', warn=lw)]
    for band, grp in (('torso', 'body'), ('legs', 'body'), ('skirt', 'skirt')):
        T.append(_iou_term('shape_iou_' + band, Q['shape_iou'], 'body_silhouette', 'trellis', 'shape', grp))
    T.append(_iou_term('shape_iou', Q['shape_iou'], 'body_silhouette', 'trellis', 'shape', 'body'))
    T.append(_iou_term('ref_iou', Q['ref_iou'], 'body_silhouette', 'key3d', 'front', 'body'))
    T.append(_iou_term('shape_iou_hair', Q['shape_iou_hair'], 'hair_shape', 'trellis', 'shape', 'hair'))
    return T



FACE_HOLD = {'sheet_width': 1.0, 'sheet_neck_to_jaw': 1.0, 'sheet_profile': 0.0, 'sheet_profile_chin': 0.0,
             'sheet_nose_reach': 0.0, 'sheet_chin_reach': 0.0, 'sheet_cheek': 0.0, 'sheet_cheek_chin': 0.0}


def hold_terms(before, groups=('body', 'details')):
    """the face's model-sheet checks (the face fit's; the body fit mustn't move them away from their targets): a
    'hold' term per check at its start value, a tenth of its tolerance, in the groups that can move them: the figure
    (the neck, the shoulders) and the details (the collar can cover the neck row the neck-to-jaw check reads). The hair
    is only their cover."""
    from .sheetqa import LIMITS as S
    lim = {'sheet_width': 'width', 'sheet_neck_to_jaw': 'width', 'sheet_profile': 'profile', 'sheet_profile_chin': 'chin',
           'sheet_nose_reach': 'reach', 'sheet_chin_reach': 'reach', 'sheet_cheek': 'cheek', 'sheet_cheek_chin': 'chin'}
    T = []
    for k, target in FACE_HOLD.items():
        v0 = (before.get(k) or {}).get('value')
        if isinstance(v0, (int, float)):
            for g in groups:
                T.append(Term(k, None, 'hold', 0.1 * S[lim[k]][0], 'face_front', 'sheet', 'face', g, (target, v0),
                              weight=1.0))
    return T


def hair_mode(pool, spec, T, authority=None, log=print):
    """the generated hair's mode (hair.shape.mode, a categorical knob): 'mesh' (the generated surface selected and
    smoothed) or 'geom' (charkit.geom's closed hair), the one whose hair terms cost less at the spec. -> (spec, info)."""
    shape = (spec.get('hair') or {}).get('shape') or {}
    if shape.get('mode') not in ('mesh', 'geom'):
        return spec, None
    Th = [t for t in T if t.group == 'hair']
    specs = []
    for mode in ('mesh', 'geom'):
        S = copy.deepcopy(spec); S['hair']['shape']['mode'] = mode
        specs.append(S)
    cs = pool.map([(S, 'hair', True) for S in specs], phase='hair mode')
    costs = {m: round(fitkit.cost(fitkit.residuals(c, Th, authority), loss='soft_l1'), 3) for m, c in zip(('mesh', 'geom'), cs)}
    best = min(costs, key=costs.get)
    log('bodyfit: hair mode %s' % costs)
    if best != shape.get('mode'):
        spec = copy.deepcopy(spec); spec['hair']['shape']['mode'] = best
    return spec, {'costs': costs, 'mode': best}


PIECE_GROUP = {'skirt': 'skirt', 'overskirt panel': 'skirt', 'shorts': 'skirt', 'boot': 'boots', 'boot cuff': 'boots',
               'waistband': 'details', 'collar': 'details', 'bow': 'details', 'sleeve': 'details', 'sleeve cuff': 'details',
               'cuff': 'details'}
PIECE_TOL = 0.10                # L: a piece's extent edge against the outfit graph's
PIECE_MIN_PX = 150              # a view where the piece shows fewer pixels (either side) is left out, and one where one
PIECE_PX_RATIO = 2.5            # side shows it this many times more: its extent is then what hides it, not its own


def piece_terms(extents, graph):
    """per-piece extent terms (bodymeasure.piece_checks' names): each mapped piece's four bbox edges in every view it
    shows in comparably on both sides (PIECE_MIN_PX, PIECE_PX_RATIO), against the outfit graph (the authority for the
    outfit's pieces), the piece's views sharing one view's weight. The arms' pieces (sleeves, cuffs) are also terms of the body (its rest pose moves them). The top is left out
    (ours carries its bodice panel, the graph draws them apart)."""
    from .bodymeasure import EDGES
    types = {p['id']: p['type'] for p in graph['pieces']}
    T = []
    for pid, vs in extents.items():
        g = PIECE_GROUP.get(types.get(pid))
        if g is None:
            continue
        vs = {v: r for v, r in vs.items() if min(r['px']) >= PIECE_MIN_PX and max(r['px']) <= PIECE_PX_RATIO * min(r['px'])}
        for v in vs:
            for e in EDGES:
                name = 'piece_%s_%s_%s' % (pid, v, e)
                T.append(Term(name, None, 'abs', PIECE_TOL, 'outfit_pieces', 'outfit_graph', v, g, weight=1.0 / len(vs)))
                if types[pid] in ('sleeve', 'sleeve cuff', 'cuff') and e in ('left', 'right'):
                    T.append(Term(name, None, 'abs', PIECE_TOL, 'outfit_pieces', 'outfit_graph', v, 'body', weight=0.5 / len(vs)))
    return T


def outfit_start(spec, graph, log=print):
    """the outfit graph's draft as the fit's start: the pieces the spec's list lacks added (the stepped-hem back panels),
    and the draft's measured first guesses for the knobs the fit owns (the skirt's back hem, the bow's size, the cuffs'
    widths, ...). -> (spec, {path: [hand value, draft value]})."""
    import copy as _c
    from .bodyeval import get_knob, set_knob
    S = _c.deepcopy(spec)
    T = graph.get('templates') or {}
    draft = {g['name']: g for g in T.get('garments', [])}
    marks = T.get('knobs') or {}
    C = graph.get('comparison') or {}
    changed = {}
    names = {g['name'] for g in S.get('garments') or []}
    for m in C.get('missed_by_hand', []):
        g = draft.get(m['draft'])
        if g is not None and g['name'] not in names:
            S.setdefault('garments', []).append(_c.deepcopy(g))
            changed['garments.' + g['name']] = [None, 'added']
    owned = {p for k in knobs(S) for p in k.paths}
    for m in C.get('matched', []):
        g = draft.get(m['draft'])
        if g is None or m['hand'] not in names:
            continue
        for k, v in g.items():
            path = 'garments.%s.%s' % (m['hand'], k)
            if path in owned and str(marks.get(m['draft'], {}).get(k, '')).startswith('measured') and \
                    isinstance(v, (int, float)) and get_knob(S, path) != v:
                changed[path] = [get_knob(S, path), v]
                set_knob(S, path, v)
    log('outfit graph: start from its draft: %s' % ', '.join('%s %s -> %s' % (k, a, b) for k, (a, b) in changed.items()))
    return S, changed


def choose_draft(pool, spec, before, drafted_spec, drafted, graph, hold=HOLD_HEAD, authority=None, log=print):
    """the outfit graph's draft is a start, not a change: the pieces the spec lacks are added, and each piece's measured
    first guesses are kept only where they beat the spec's own values on the fit's objective (fitkit.cost over the fit's
    terms, the piece extents' included, and the regulariser). A hand-written spec takes the draft where it helps; a
    fitted one keeps its fit, where drafting it again would make the fit re-derive it (and its result then couldn't match
    the start it's judged against). One round of evaluations: each piece's draft on its own.
    -> (start, the draft's changes kept {path: [spec value, draft value]}, gain: the kept pieces' summed cost drop over
    the spec's cost, each measured alone)."""
    from .bodyeval import set_knob
    added = {p: v for p, v in drafted.items() if v[1] == 'added'}
    moved = {p: v for p, v in drafted.items() if v[1] != 'added'}
    base = copy.deepcopy(spec)
    for p in added:
        name = p.split('.', 1)[1]
        base.setdefault('garments', []).append(copy.deepcopy(next(g for g in drafted_spec['garments'] if g['name'] == name)))
    pieces = sorted({p.split('.')[1] for p in moved})
    if not pieces:
        return base, added, 0.0
    trials = []
    for pc in pieces:
        S = copy.deepcopy(base)
        for p, (a, b) in moved.items():
            if p.split('.')[1] == pc:
                set_knob(S, p, b)
        trials.append(S)
    cs = pool.map(([(base, 'all', True)] if added else []) + [(S, 'all', True) for S in trials], phase='draft')
    at_base = before if not added else cs.pop(0)
    K = knobs(base, hold)
    T = terms(base) + (piece_terms({k[6:]: v for k, v in _extents(at_base).items()}, graph) if graph is not None else [])

    def cost(checks, S):
        return fitkit.cost(fitkit.residuals(checks, T, authority), [k.get(S) for k in K], K)
    c0 = cost(at_base, base)
    cp = {pc: cost(c, S) for pc, c, S in zip(pieces, cs, trials)}
    keep = [pc for pc in pieces if cp[pc] < c0]
    start = copy.deepcopy(base)
    for p, (a, b) in moved.items():
        if p.split('.')[1] in keep:
            set_knob(start, p, b)
    kept = dict(added, **{p: v for p, v in moved.items() if p.split('.')[1] in keep})
    log('outfit graph: the draft against the spec\'s own values (cost %.2f): %s' % (c0, ', '.join(
        '%s %.2f %s' % (pc, cp[pc], 'kept' if pc in keep else 'not kept') for pc in pieces)))
    gain = sum(c0 - cp[pc] for pc in keep) / max(1e-9, c0)
    if not keep:
        return (base if added else spec), added, 0.0     # the spec itself: prepare then reuses its measurement
    return start, kept, gain


class BodyChecks:
    """the fit's evaluator (fitkit's protocol): checks(spec, group, fine) -> {check name: check} as qa.json names them:
    shape_* and ref_iou (qa3d's silhouettes; fine: the render's subdivision, else the viewport's), body_* (the model
    sheet's), for group 'palette' or 'all' palette_*, and for the figure, the details or 'all' the face's sheet_* (held,
    not fitted: the neck and the collar move them).
    Group 'all' (the before, after, repair and guard checks) cuts geom mode's hair for each body; a group's own
    optimisation carries the start's cut with the head (bodyeval.Evaluator.exact_geom)."""

    def __init__(self, spec, graph=None):
        from . import bodyeval
        self.E = bodyeval.Evaluator(spec)
        self.graph = graph

    def checks(self, spec, group='all', fine=False):
        from .qa3d import LIMITS
        self.timing, t = {}, time.time()

        def lap(stage):
            nonlocal t
            now = time.time(); self.timing[stage] = now - t; t = now
        self.E.exact_geom = group == 'all'      # what the fit is judged by: geom's hair cut for this body, not carried
        G = self.E.geometry(spec=spec)
        lap('geometry')
        Q = self.E.qa(G, levels='render' if fine else 'viewport')
        lap('silhouettes')
        out = {}
        for k, v in Q['checks'].items():
            if k in LIMITS:
                p, w = LIMITS[k]
                out[k] = {'value': v, 'status': 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'}
            else:
                out[k] = {'value': v, 'status': 'INFO'}
        out.update(self.E.sheet_checks(G, palette=group in ('all', 'palette')))
        lap('sheet')
        if group in ('all', 'figure', 'details'):
            out.update(self.E.face_checks(G))
            lap('face')
        if self.graph is not None and self.E.sheet() is not None and group != 'palette':
            from . import bodymeasure
            out.update(bodymeasure.piece_checks(G.bundle('viewport'), self.E.sheet(), self.graph, spec))
            lap('pieces')
        from . import checks as checklib                    # graded only against each measure's authority, as the QA
        ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
        return checklib.authorize(out, ref.get('authority') or {})


# ------------------------------------------------------------------------------------------------------------ the fit
def declare(spec=None):
    """what the body fit owns and answers to (facefit.declare's shape): {'knobs': {name: {paths, default, step, bounds,
    group, piece}}, 'terms': [...]} (for a spec: its garments' pieces and the outfit graph's ties and extents)."""
    from . import bodymeasure
    spec = spec or {}
    graph = bodymeasure.load_graph(spec) if spec.get('ref') else None
    K = _grouped(tie(knobs(spec), spec, graph))
    return {'knobs': {k.name: k.declare() for k in K}, 'terms': [t.declare() for t in _grouped(terms(spec))]}


def _grouped(items):
    """knobs or terms moved from their piece to its fit group (FIT_GROUP), the piece kept."""
    for x in items:
        x.piece = getattr(x, 'piece', x.group)
        x.group = FIT_GROUP.get(x.group, x.group)
    return items


def prepare(pool, spec, graph, baseline=None, draft=True, hold=HOLD_HEAD, authority=None, log=print):
    """the fit's start (see fit): the spec measured as it is, the outfit graph's draft where it beats the spec's own
    values (choose_draft), the knobs (tied, the head held) and the terms (the piece extents at the start, the holds of
    what already passes) -> dict(before, protected, start, drafted, K, T, hold)."""
    before = pool.map([(spec, 'all', True)], phase='start')[0]      # the spec as it is: what the fit is judged against
    protected = dict(before); protected.update({k: v for k, v in (baseline or {}).items() if k in before})
    start, drafted = outfit_start(spec, graph, log) if graph is not None and draft else (spec, {})
    gain = 0.0
    if drafted:
        start, drafted, gain = choose_draft(pool, spec, before, start, drafted, graph, hold, authority, log)
    K, T = _grouped(tie(knobs(start, hold), start, graph)), terms(start)
    held = None
    if hold:
        held = head_hold(start)
        for k in K:
            k.hold = held if k.derived else None
    at_start = pool.map([(start, 'all', True)], phase='start')[0] if start is not spec else before
    if graph is not None:
        T += piece_terms({k[6:]: v for k, v in _extents(at_start).items()}, graph)
    T = _grouped([t for t in T if (at_start.get(t.check) or {}).get('status') not in (None, 'SKIPPED')] +
                 hold_terms(protected))
    return dict(before=before, protected=protected, start=start, drafted=drafted, draft_gain=gain, K=K, T=T, hold=held)


def probe(spec, out, base=None, workers=None, outfit=True, draft=True, hold=HOLD_HEAD, log=print):
    """the tune's look before a full fit (charkit.fitters.BodyFitter.probe): the fit's own start (prepare), its
    sensitivity table, and how far the fit's objective drops at the best single knob step (fitters.probe_headroom).
    -> out/sensitivity.json, out/probe.json {cost, best, headroom, score_headroom, score_steps, evaluations, drafted (the
    outfit graph's draft kept at the start: a change of its own), draft_gain (its cost drop), seconds, timing}."""
    from . import bodyeval, bodymeasure, fitters
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    spec = bodyeval.resolve(spec, base) if isinstance(spec, str) else copy.deepcopy(spec)
    graph = bodymeasure.load_graph(spec) if outfit else None
    authority = dict(AUTHORITY); authority.update((spec.get('ref') or {}).get('authority') or {})
    pool = fitkit.Pool('charkit.bodyfit:BodyChecks', (spec, graph), workers or WORKERS)
    try:
        P = prepare(pool, spec, graph, None, draft, hold, authority, log)
        table = fitkit.sensitivity(pool, P['start'], P['K'])
        timing = pool.report()
    finally:
        pool.close()
    json.dump(table, open(os.path.join(out, 'sensitivity.json'), 'w'), indent=1)
    r = fitters.probe_headroom(table, P['start'], P['T'], P['K'], authority)
    r.update(drafted=P['drafted'], draft_gain=round(P['draft_gain'], 4), seconds=round(time.time() - t0, 1), timing=timing)
    json.dump(r, open(os.path.join(out, 'probe.json'), 'w'), indent=1, default=str)
    log('bodyfit probe: objective %.3f, best step %s %s -> %.3f (%.1f%%); QA score headroom %.2f; %d evaluations, %.0f s' % (
        r['cost'], r['best'][0], r['best'][1], r['best'][2], 100 * r['headroom'], r['score_headroom'], r['evaluations'],
        r['seconds']))
    return r


def fit(spec, out, budget=None, base=None, workers=None, groups=SCHEDULE, baseline=None, palette=False, outfit=True,
        draft=True, hold=HOLD_HEAD, log=print):
    """fit a spec's body, garments and hair (see the module) and write the fitted spec and the reports into out; the
    interface of charkit.facefit.fit. spec: a path (resolved as `build` resolves it) or a resolved dict. budget: the
    most evaluations per group (None: fitkit's). baseline: a QA (qa.json path or its checks) whose statuses the fit
    mustn't worsen (default: the start's). hold: the head held as the spec builds it (hold_head; False: the head count
    is a knob and the face may move a little with the body). -> (fitted spec, report)."""
    from . import bodyeval, bodymeasure
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    spec = bodyeval.resolve(spec, base) if isinstance(spec, str) else copy.deepcopy(spec)
    graph = bodymeasure.load_graph(spec) if outfit else None
    authority = dict(AUTHORITY); authority.update((spec.get('ref') or {}).get('authority') or {})
    workers = workers or WORKERS
    if isinstance(baseline, str):
        baseline = json.load(open(baseline))['checks']
    pool = fitkit.Pool('charkit.bodyfit:BodyChecks', (spec, graph), workers)
    rep = {'spec': spec.get('name'), 'authority': authority, 'groups': {}}
    try:
        P = prepare(pool, spec, graph, baseline, draft, hold, authority, log)
        before, protected, start, K, T = P['before'], P['protected'], P['start'], P['K'], P['T']
        if hold:
            rep['hold'] = P['hold']
        rep.update(declare={'knobs': {k.name: k.declare() for k in K}, 'terms': [t.declare() for t in T]},
                   outfit_start=P['drafted'])
        log('bodyfit: start measured (%d checks, %d terms, %d knobs)' % (len(before), len(T), len(K)))
        table = fitkit.sensitivity(pool, start, K)
        json.dump(table, open(os.path.join(out, 'sensitivity.json'), 'w'), indent=1)
        log('bodyfit: sensitivity table (%d knobs)' % len(table['knobs']))
        fitted = start
        for g in groups:
            if not any(k.group == g for k in K):
                continue
            if g == 'hair':
                fitted, rep['hair_mode'] = hair_mode(pool, fitted, T, authority, log)
                if ((fitted.get('hair') or {}).get('shape') or {}).get('mode') == 'geom':
                    # geom's hair is cut from the generated solid by its own rules (charkit.geom.parts.hair): the mesh
                    # mode's selection knobs re-run a 30-60 s extraction each and barely move it; left as they are
                    log('bodyfit: hair knobs left (geom mode)')
                    continue
            fitted, info = fitkit.optimise(pool, fitted, K, T, g, authority, budget=budget, baseline=protected, log=log)
            rep['groups'][g] = {k: v for k, v in info.items() if k != 'history'}
            rep['groups'][g]['cost_history'] = [h['cost'] for h in info['history']]
            log('bodyfit: %s %s' % (g, info['fitted']))
        # the repair: a check that reads worse than at the start (or in the baseline) has its terms weighed REPAIR
        # times and their groups fitted again from where they are (fitkit's protection is soft: many terms can outvote
        # one)
        rep['repair'] = {}
        for rnd in range(REPAIR_ROUNDS):
            now = pool.map([(fitted, 'all', True)], phase='check')[0]
            reg = fitkit.regressions(protected, now, lambda c: not c.startswith('piece_'))
            if not reg:
                break
            log('bodyfit: repair %d: %s' % (rnd + 1, reg))
            for g in [g for g in groups if any(t.group == g and t.check in reg for t in T)]:
                Tr = [copy.copy(t) for t in T]
                for t in Tr:
                    if t.check in reg:
                        t.weight = REPAIR * (t.weight if t.weight is not None else 1.0)
                fitted, info = fitkit.optimise(pool, fitted, K, Tr, g, authority, budget=REPAIR_BUDGET,
                                               baseline=protected, log=log)
                rep['repair']['%s_%d' % (g, rnd + 1)] = {k: v for k, v in info.items() if k != 'history'}
                log('bodyfit: repaired %s %s' % (g, info['fitted']))
        fitted, rep['line_repair'] = line_repair(pool, fitted, K, T, protected, table, log)
        # the checks the fit doesn't aim at (the face's, the expressions, folds, scalp, ...) mustn't read worse: each
        # group's change is scaled back while one does
        aimed = {t.check for t in T if t.kind != 'hold'}
        rep['guard'] = {}
        for g in [g for g in groups if any(k.group == g for k in K)]:
            ks = [k for k in K if k.group == g]
            fitted, gi = fitkit.guard(pool, fitkit.with_knobs(fitted, [k.get(start) for k in ks], ks), fitted, ks, protected,
                                      lambda c: c not in aimed and not c.startswith('piece_'), log=log)
            rep['guard'][g] = {'kept': gi['kept'], 'regressions_at_full': gi['regressions_at_full']}
        after = pool.map([(fitted, 'all', True)], phase='check')[0]
        rep['timing'] = pool.report()
    finally:
        pool.close()
    if palette:
        ev = BodyChecks(spec, graph)
        fitted, rep['palette'] = fit_palette(ev, fitted, log=log)
        after = ev.checks(fitted, 'all', fine=True)
    rep['regressions'] = fitkit.regressions(protected, after, lambda c: not c.startswith('piece_'))
    rb, ra = fitkit.residuals(before, T, authority), fitkit.residuals(after, T, authority)
    rep.update(before={k: [v.get('value'), v.get('status')] for k, v in before.items()},
               after={k: [v.get('value'), v.get('status')] for k, v in after.items()},
               residuals={'before': rb, 'after': ra},
               knobs={k.name: {'start': k.get(start), 'fitted': k.get(fitted), 'default': k.default,
                               'bounds': list(k.bounds), 'at_bound': k.at_bound(k.get(fitted))} for k in K},
               triage=fitkit.triage(ra, table, K, fitted), sensitivity=os.path.join(out, 'sensitivity.json'),
               seconds=round(time.time() - t0, 1), evaluations=sum(g['evaluations'] for g in rep['groups'].values()))
    fitted = copy.deepcopy(fitted)
    fitted['bodyfit'] = {'by': 'charkit.bodyfit', 'knobs': {k.name: k.get(fitted) for k in K if k.group in groups}}
    name = spec.get('name', 'char')
    p = os.path.join(out, name + '.bodyfit.json')
    json.dump(fitted, open(p, 'w'), indent=1)
    rep['fitted_spec'] = p
    json.dump(rep, open(os.path.join(out, 'bodyfit_report.json'), 'w'), indent=1, default=str)
    open(os.path.join(out, 'bodyfit_report.md'), 'w').write(report_md(rep))
    log('bodyfit: wrote %s (%.0f s)' % (p, rep['seconds']))
    return fitted, rep


LINE_STEPS = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)      # the line repair's trial steps along a knob, in knob steps


def line_repair(pool, spec, K, T, protected, table, log=print):
    """what the repair left: for each check still reading worse than in the baseline, a line search along the knobs
    that move it most (the sensitivity table's per-step change, the helpful direction), taking the smallest step that
    brings it back into its band without any other graded check reading worse than it does now.
    -> (spec, {check: {knob, steps, value} or 'unrepaired'})."""
    names = lambda c: not c.startswith('piece_')
    now = pool.map([(spec, 'all', True)], phase='line repair')[0]
    reg = fitkit.regressions(protected, now, names)
    out = {}
    for chk in list(reg):
        t = next((t for t in T if t.check == chk and t.kind != 'hold'), None)
        movers = []
        for k in K:
            m = ((table.get('knobs') or {}).get(k.name) or {}).get('measures', {}).get(chk) or {}
            if m.get('per_step'):
                movers.append((abs(m['per_step']), k, m['per_step']))
        movers.sort(key=lambda x: -x[0])
        v = (now.get(chk) or {}).get('value')
        done = None
        for _, k, ps in movers[:3]:
            if t is None or v is None:
                break
            target = 1.0 if t.kind in ('ratio', 'floor') and (t.kind == 'ratio' or t.floor == 1.0) else 0.0
            sgn = 1.0 if (target - v) * ps > 0 else -1.0
            x0 = k.get(spec)
            xs = [min(k.bounds[1], max(k.bounds[0], x0 + sgn * st * k.step)) for st in LINE_STEPS]
            specs = [fitkit.with_knobs(spec, [x], [k]) for x in xs]
            cs = pool.map([(s_, 'all', True) for s_ in specs], phase='line repair')
            for st, x, s_, c in zip(LINE_STEPS, xs, specs, cs):
                r2 = fitkit.regressions(protected, c, names)
                if chk not in r2 and set(r2) <= set(reg) - {chk}:
                    done = (k, st, x, s_, c)
                    break
            if done:
                break
        if done:
            k, st, x, spec, now = done
            reg = fitkit.regressions(protected, now, names)
            out[chk] = {'knob': k.name, 'steps': st, 'value': round(x, 5), 'check': (now.get(chk) or {}).get('value')}
            log('bodyfit: line repair %s: %s %+g steps -> %s' % (chk, k.name, st, out[chk]['check']))
        else:
            out[chk] = 'unrepaired'
            log('bodyfit: line repair %s: none of its knobs brings it back alone' % chk)
    return spec, out


WORKERS = 2                     # evaluator processes (each holds an evaluator: about 1.5 GB; the machine is shared)
REPAIR = 16.0                   # a regressed check's terms weigh this many times more in the repair
REPAIR_ROUNDS = 2
REPAIR_BUDGET = 120


def _extents(checks):
    """piece_checks' values back into piece_extents' shape: {piece: {view: dict(d, px)}} (px unknown: taken as enough;
    the checks exist only where both sides showed min_px)."""
    from .bodymeasure import EDGES
    out = {}
    for k, c in checks.items():
        if not k.startswith('piece_'):
            continue
        for e in EDGES:
            if k.endswith('_' + e):
                head = k[:-len(e) - 1]
                view = next(v for v in ('three_quarter', 'front', 'profile', 'back') if head.endswith('_' + v))
                pid = head[len('piece_'):-len(view) - 1]
                out.setdefault('piece_' + pid, {}).setdefault(view, {'d': [None] * 4, 'px': c.get('px', [PIECE_MIN_PX] * 2)})
                out['piece_' + pid][view]['d'][EDGES.index(e)] = c['value']
    return out


# ------------------------------------------------------------------------------------------------------------ palette
def palette_members(spec):
    """the colour knobs behind each palette class: {class: [(path, kind)]}. kind 'garment': a garment toon (lit = the
    colour, shade = the colour * garments' fixed shade multiplier); 'toon3': a lit / shade / deep triple set on its own
    (the skin, the hair). A garment colour belongs to the class its colour family is (charkit.bodyqa.family)."""
    from .bodyqa import CLASS, family
    from .scene import SKIN
    names = {v: k for k, v in CLASS.items()}
    M = {'skin': [('skin', 'toon3')]}
    if spec.get('hair') is not None:
        M['hair'] = [('hair_colors', 'toon3')]
    for g in spec.get('garments') or []:
        for k in ('color', 'panel_color', 'hem_color', 'stripe_color', 'sole_color'):
            if k in g:
                c = names.get(int(family(np.asarray(g[k], float)[None])[0]))
                M.setdefault(c, []).append(('garments.%s.%s' % (g['name'], k), 'garment'))
        if isinstance(g.get('panel'), dict) and 'color' in g['panel']:
            c = names.get(int(family(np.asarray(g['panel']['color'], float)[None])[0]))
            M.setdefault(c, []).append(('garments.%s.panel.color' % g['name'], 'garment'))
    M['_skin_default'] = SKIN
    return M


def fit_palette(ev, spec, log=print):
    """the colour knobs set to the sheet's palette, class by class (charkit.paletteqa's tones, CIEDE2000): a toon3 class
    (the skin, the hair) takes the design's lit and shade tones (its deep tone keeps its ratio to the shade); a class of
    garment colours moves by one shift, the one that minimises the lit tone's dE00, held inside the class's colour family
    so no piece changes class; then one shade
    multiplier for every garment (their 'shade', in garments.SHADE_MUL's place) is fitted to the garment classes' shade
    tones. The iris is painted by its texture and left to the eye fit. A step that doesn't read better with the whole
    character re-measured is not kept. -> (spec, info {class: {before, after, paths}, garment_shade})."""
    from scipy.optimize import minimize
    from .bodyeval import get_knob, set_knob
    from .bodyqa import CLASS, family
    from .paletteqa import LIMITS as PL, ciede2000, srgb_to_lab
    LIT_PASS, SHADE_PASS = PL['lit'][0], PL['shade'][0]
    from .garments import SHADE_MUL as MUL
    S = ev.E.sheet()
    if S is None:
        return spec, {'status': 'SKIPPED', 'why': 'no model sheet'}
    D = S.palette
    M = palette_members(spec)
    sk_default = M.pop('_skin_default')
    info = {'paths': []}
    dE = lambda a, b: ciede2000(srgb_to_lab(np.clip(a, 0, 1)), srgb_to_lab(np.clip(b, 0, 1)))

    def measured(sp):
        return {k[len('palette_'):]: v for k, v in ev.checks(sp, 'palette').items() if k.startswith('palette_')}
    cur = measured(spec)
    fitted = copy.deepcopy(spec)
    from . import bodymeasure, paletteqa
    G = ev.E.geometry(spec=spec)
    O = paletteqa.ours(bodymeasure.colours(G.bundle('viewport')))
    for cls, members in M.items():
        if cls not in D or D[cls] is None or cls not in O or cls == 'iris':
            continue
        dl, ds = D[cls].get('lit'), D[cls].get('shade')
        trial = copy.deepcopy(fitted)
        paths = []
        if members[0][1] == 'toon3':
            path = members[0][0]
            tri = {k: np.asarray(v, float) for k, v in (get_knob(fitted, path) or {}).items()}
            if not tri and path == 'skin':
                tri = {k: np.asarray(v, float) for k, v in sk_default.items()}
            new = dict(tri)
            if dl is not None:
                new['lit'] = np.clip(dl, 0, 1)
            if ds is not None:
                ratio = tri['deep'] / np.maximum(tri['shade'], 1e-3) if 'deep' in tri and 'shade' in tri else 0.8
                new['shade'] = np.clip(ds, 0, 1); new['deep'] = np.clip(ds * ratio, 0, 1)
            for k, v in new.items():
                set_knob(trial, '%s.%s' % (path, k), [round(float(x), 4) for x in v])
                paths.append('%s.%s' % (path, k))
        else:
            ol = np.asarray(O[cls]['lit'])
            cols = {p: np.asarray(get_knob(fitted, p), float) for p, _ in members}
            code = CLASS[cls]

            def f(dv):
                if any(int(family(np.clip(c + dv, 0, 1)[None])[0]) != code for c in cols.values()):
                    return 1e3
                # the lit tone (the shade is the garments' shared multiplier's, fitted next), in its PASS limits
                return (dE(ol + dv, dl) / LIT_PASS) ** 2 if dl is not None else 0.0
            r = minimize(f, np.zeros(3), method='Nelder-Mead', options=dict(xatol=1e-4, fatol=1e-3, maxiter=600,
                                                                            initial_simplex=np.vstack([np.zeros(3), 0.05 * np.eye(3)])))
            dv = r.x if r.fun < f(np.zeros(3)) else np.zeros(3)
            for p, c in cols.items():
                set_knob(trial, p, [round(float(x), 4) for x in np.clip(c + dv, 0, 1)])
                paths.append(p)
        after = measured(trial)
        lim = {'lit': LIT_PASS, 'shade': SHADE_PASS}
        before_c = sum(((cur.get('%s_%s' % (cls, t)) or {}).get('value') or 0) ** 2 / lim[t] ** 2 for t in lim)
        after_c = sum(((after.get('%s_%s' % (cls, t)) or {}).get('value') or 0) ** 2 / lim[t] ** 2 for t in lim)
        keep = after_c < before_c - 1e-6
        info[cls] = {'before': {t: (cur.get('%s_%s' % (cls, t)) or {}).get('value') for t in ('lit', 'shade')},
                     'after': {t: (after.get('%s_%s' % (cls, t)) or {}).get('value') for t in ('lit', 'shade')},
                     'kept': keep, 'paths': paths}
        log('palette: %-6s %s -> %s%s' % (cls, info[cls]['before'], info[cls]['after'], '' if keep else ' (not kept)'))
        if keep:
            fitted, cur = trial, after
            info['paths'] += paths
    # the garments' shade: one multiplier for every garment (garments.SHADE_MUL's place), fitted to the shade tones of
    # the garment classes at their lit tones as they now are
    G = ev.E.geometry(spec=fitted)
    O = paletteqa.ours(bodymeasure.colours(G.bundle('viewport')))
    gcls = [c for c, ms in M.items() if ms and ms[0][1] == 'garment' and c in O and c in D and D[c] and
            D[c].get('shade') is not None]
    if gcls:
        def g(m):
            return sum((dE(np.asarray(O[c]['lit']) * m, D[c]['shade']) / SHADE_PASS) ** 2 for c in gcls)
        m0 = np.asarray(MUL, float)
        r = minimize(g, m0, method='Nelder-Mead', options=dict(xatol=1e-4, fatol=1e-4, maxiter=800))
        m = np.clip(r.x, 0.3, 1.0)
        trial = copy.deepcopy(fitted)
        paths = []
        for gm in trial.get('garments') or []:
            gm['shade'] = [round(float(x), 4) for x in m]
            paths.append('garments.%s.shade' % gm['name'])
        after = measured(trial)
        tot = lambda C_: sum(((C_.get('%s_shade' % c) or {}).get('value') or 0) ** 2 for c in gcls)
        keep = tot(after) < tot(cur) - 1e-6
        info['garment_shade'] = {'mul': m.round(4).tolist(), 'classes': gcls, 'kept': keep,
                                 'before': {c: (cur.get('%s_shade' % c) or {}).get('value') for c in gcls},
                                 'after': {c: (after.get('%s_shade' % c) or {}).get('value') for c in gcls}}
        log('palette: garment shade %s: %s -> %s%s' % (m.round(3).tolist(), info['garment_shade']['before'],
                                                      info['garment_shade']['after'], '' if keep else ' (not kept)'))
        if keep:
            fitted, cur = trial, after
            info['paths'] += paths
    return fitted, info


# ------------------------------------------------------------------------------------------------------------ report
def report_md(rep):
    L = ['# Body fit: %s' % rep['spec'], '', 'Seconds: %s, evaluations: %s. Authority: %s.' % (
        rep['seconds'], rep.get('evaluations'), rep['authority']), '']
    if rep.get('outfit_start'):
        L += ['The outfit graph\'s draft as the start: ' + ', '.join('%s %s -> %s' % (k, a, b) for k, (a, b) in
                                                                    rep['outfit_start'].items()) + '.', '']
    L += ['## Checks before and after', '', '| check | before | after |', '| --- | --- | --- |']
    for k in sorted(rep['after']):
        b, a = rep['before'].get(k, [None, None]), rep['after'][k]
        if b != a and a[1] in ('PASS', 'WARN', 'FAIL', 'INFO') and not k.startswith('piece_'):
            L.append('| %s | %s %s | %s %s |' % (k, _f(b[0]), b[1], _f(a[0]), a[1]))
    L += ['', '## Groups', '']
    for g, info in rep['groups'].items():
        L.append('- **%s** (%d evaluations%s): %s%s' % (
            g, info['evaluations'], ', %s' % info['stopped'] if info.get('stopped') else '',
            ', '.join('%s %s -> %s' % (k, info['start'][k], v) for k, v in info['fitted'].items()),
            ('; at a bound: %s' % info['at_bound']) if info['at_bound'] else ''))
    if rep.get('hair_mode'):
        L.append('- hair mode: %s (costs %s)' % (rep['hair_mode']['mode'], rep['hair_mode']['costs']))
    if rep.get('guard'):
        L.append('- guard: %s' % rep['guard'])
    if rep.get('palette'):
        pal = rep['palette']
        L.append('- palette: ' + '; '.join('%s %s -> %s%s' % (c, v['before'], v['after'], '' if v.get('kept') else ' (not kept)')
                                           for c, v in pal.items() if isinstance(v, dict) and 'before' in v))
    if rep.get('timing'):
        L += ['', '## Where the time went', '', 'Evaluations by what asked for them; wall seconds; the workers\' summed '
              'seconds per evaluation; parallelism (summed over wall: at most %d, the workers). Worker peak memory %s MB '
              '(all %s MB).' % (rep['timing']['workers'], rep['timing']['peak_mb'], rep['timing']['peak_mb_total']), '',
              '| phase | evaluations | wall s | s per evaluation | parallelism | per evaluation by stage |',
              '| --- | --- | --- | --- | --- | --- |']
        for ph, v in rep['timing']['phases'].items():
            L.append('| %s | %d | %.0f | %.2f | %.1f | %s |' % (ph, v['evaluations'], v['seconds'], v['per_eval'],
                     v['parallelism'], ', '.join('%s %.2f' % kv for kv in v['stages'].items())))
    if rep.get('regressions'):
        L += ['', '## Read worse than at the start', ''] + ['- %s: %s -> %s' % (k, a, b) for k, (a, b) in rep['regressions'].items()]
    L += ['', '## Still outside tolerance (fitkit.triage)', '', '| term | residual (tolerances) | why | knobs |',
          '| --- | --- | --- | --- |']
    for t in rep['triage']:
        L.append('| %s | %+.2f | %s | %s |' % (t['term'], t['r'], t['why'], ', '.join(
            '%s %+.2f%s' % (k['knob'], k['per_step_tol'], ' (blocked)' if k.get('blocked') else '') for k in t['knobs'][:3])))
    return '\n'.join(L) + '\n'


def _f(v):
    return ('%.3f' % v) if isinstance(v, float) else str(v)


def write_spec(src, fitted, names, added=()):
    """the fitted knobs written back into a spec file (only the knobs the fit owns, and the garment pieces it added;
    the rest of the file as it was)."""
    from .bodyeval import get_knob, set_knob
    S = json.load(open(src))
    have = {g['name'] for g in S.get('garments') or []}
    for name in added:
        g = next((g for g in fitted.get('garments') or [] if g['name'] == name), None)
        if g is not None and name not in have:
            S.setdefault('garments', []).append(copy.deepcopy(g))
    for p in names:
        v = get_knob(fitted, p)
        if v is not None:
            set_knob(S, p, v)
    json.dump(S, open(src, 'w'), indent=1)
    return src


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    from . import bodyeval
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec_path = args[0]
    name = json.load(open(bodyeval._abs(spec_path)))['name']
    out = bodyeval._abs(opt('--out', 'charkit/out/bodyfit/%s' % name))
    if '--probe' in args:
        probe(spec_path, out, base=opt('--base'), workers=int(opt('--workers')) if opt('--workers') else None,
              outfit='--no-outfit' not in args, draft='--no-draft' not in args, hold='--free-head' not in args,
              log=lambda *a: print(*a, flush=True))
        return
    pieces = [p for p in opt('--pieces', ','.join(SCHEDULE)).split(',') if p]
    fitted, rep = fit(spec_path, out, budget=int(opt('--budget')) if opt('--budget') else None, base=opt('--base'),
                      workers=int(opt('--workers')) if opt('--workers') else None, groups=pieces,
                      baseline=opt('--baseline'), palette='--palette' in args, outfit='--no-outfit' not in args,
                      draft='--no-draft' not in args, hold='--free-head' not in args,
                      log=lambda *a: print(*a, flush=True))
    if '--write-spec' in args:
        write_fitted(spec_path, fitted, rep, pieces)
        print('wrote the fitted knobs into', spec_path)


def write_fitted(spec_path, fitted, rep, pieces=SCHEDULE):
    """a fit's result into its spec file: the knobs of the fitted pieces, the palette's colours, the pieces the outfit
    graph added."""
    from . import bodyeval
    from . import bodymeasure
    graph = bodymeasure.load_graph(fitted)
    paths = [p for k in _grouped(tie(knobs(fitted), fitted, graph)) if k.group in pieces for p in k.paths + k.derived]
    paths += (rep.get('palette') or {}).get('paths', [])
    if rep.get('hair_mode'):
        paths.append('hair.shape.mode')
    added = [k.split('.', 1)[1] for k, v in (rep.get('outfit_start') or {}).items() if v[1] == 'added']
    return write_spec(bodyeval._abs(spec_path), fitted, paths, added)
