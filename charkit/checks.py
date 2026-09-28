"""What each graded QA check means, in one table, so the tune loop, the triage and the review read a check the same way:

  rule        how the check grades: its kind and (pass, warn) limits, taken from the QA modules' own LIMITS (qa3d, eyeqa,
              sheetqa, faceqa), so a limit changed there is changed here
                hi     higher is better: PASS at >= pass, WARN at >= warn
                lo     lower is better: PASS at <= pass, WARN at <= warn
                ratio  |value - 1| against the limits (ours over the reference)
                abs    |value| against the limits (a signed gap)
                count  0 passes, anything else warns
                status only the status is known (a check this table doesn't name yet, or one with a non-numeric value)
  severity    how far a value is from passing, in warn bands: 0 at the pass limit or better, 1 at the fail limit, and on
              linearly past it (a FAIL is > 1; a warn-only check never fails, but its severity still grows, so getting
              worse shows). A check graded by status alone: WARN 0.5, FAIL 1.5
  weight      a check measured against a reference that isn't the manifest's authority for its measure (the TRELLIS face,
              where the sheet is the face's authority) counts a quarter in a score, as charkit.fitkit weighs its terms
  region      where the check looks (face, eyes, silhouette, hair, outfit, expressions, palette, internal) and how visible
              that is (1 = the face and silhouette a viewer reads first, down to ~0.1 for topology nobody sees)
  measure     the manifest's authority key the check measures (face_front, chin, eyes, hair_shape...) and the reference it
              is measured against (sheet, rig, trellis, key3d, or none for self-consistency checks); the manifest names
              which reference is the authority for the measure
  overlays    the QA pictures that show it (paths relative to the build's output folder)

    from charkit import checks
    checks.severity('sheet_width', 0.825)      # -> 1.36 (FAIL: 1.36 warn bands past the pass limit)
    checks.score(qa, authority=A)               # the sum of severities over the graded checks (capped, weighted)
"""
import fnmatch

GRADED = ('PASS', 'WARN', 'FAIL')
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}
CAP = 5.0                       # one check's severity counts at most this much in a score (one wild check can't drown the rest)
NOISE = 0.02                    # a severity change smaller than this is no change (warn bands)

_RULES = None


def _limits():
    """(pattern, kind, pass, warn, warn_only) from the QA modules' LIMITS; first match wins."""
    from . import eyeqa, faceqa, qa3d, sheetqa
    Q, E, S, F = qa3d.LIMITS, eyeqa.LIMITS, sheetqa.LIMITS, faceqa.LIMITS
    try:                                   # the whole model sheet (tool/sheet): body per view, palette
        from . import bodyqa, paletteqa
        B, P = bodyqa.LIMITS, paletteqa.LIMITS
    except ImportError:
        B, P = {'iou': (0.85, 0.70), 'iou_part': (0.70, 0.50), 'length': (0.08, 0.16), 'width': (0.08, 0.15)}, \
            {'lit': (5.0, 10.0), 'shade': (7.0, 14.0)}
    R = [
        ('shape_iou', 'hi', *Q['shape_iou'], False), ('shape_iou_hair', 'hi', *Q['shape_iou_hair'], False),
        ('ref_iou', 'hi', *Q['ref_iou'], False),
        ('scalp_px', 'lo', *Q['scalp_px'], False), ('poke_share', 'lo', *Q['poke_share'], False),
        ('hair_noise', 'lo', *Q['hair_noise'], False), ('face_folds', 'lo', *Q['face_folds'], False),
        ('face_blink_open', 'lo', *Q['blink_open'], False), ('face_blink_iris', 'lo', *Q['blink_iris'], False),
        ('face_eye_asym', 'lo', *Q['eye_asym'], False), ('face_mouth_asym', 'lo', *Q['mouth_asym'], False),
        ('face_viseme_gap', 'hi', *Q['viseme_gap'], False), ('face_expr_range', 'count', 0, 2, True),
        ('eye_lid_gap', 'lo', *eyeqa.LID_GAP, False), ('eye_highlight_side', 'status', 0, 0, True),
    ]
    R += [('eye_' + k, 'ratio', p, w, False) for k, (p, w) in E.items()]
    R += [
        ('sheet_width', 'ratio', *S['width'], False), ('sheet_neck_to_jaw', 'ratio', *S['width'], False),
        ('sheet_profile', 'lo', *S['profile'], False), ('sheet_cheek', 'lo', *S['cheek'], False),
        ('sheet_*_chin', 'abs', *S['chin'], False), ('sheet_*_reach', 'abs', *S['reach'], False),
        ('sheet_shown_*', 'ratio', 0.2, 0.4, True),
        ('face_shape_width', 'ratio', *F['width'], False), ('face_shape_chin', 'abs', *F['chin'], False),
        ('face_shape_profile', 'lo', *F['profile'], False), ('face_shape_cheek', 'lo', *F['cheek'], False),
        ('face_shape_depth', 'lo', *F['depth'], False), ('face_shape_coverage_*', 'ratio', *F['coverage'], True),
        # body per view (front, three_quarter, profile, back): silhouette and part IoUs, heights (L), widths (ratios)
        ('body_*_iou', 'hi', *B['iou'], False), ('body_*_iou_*', 'hi', *B['iou_part'], False),
        ('body_*_hair_width', 'ratio', *B['width'], False), ('body_*_skirt_width', 'ratio', *B['width'], False),
        ('body_*_sleeves', 'ratio', *B['width'], False),
        ('body_*_feet', 'abs', *B['length'], False), ('body_*_top', 'abs', *B['length'], False),
        ('body_*_hair_length', 'abs', *B['length'], False), ('body_*_hem', 'abs', *B['length'], False),
        ('body_*_hem_mid', 'abs', *B['length'], False), ('body_*_leg', 'abs', *B['length'], False),
        ('body_*_boot', 'abs', *B['length'], False),
        ('palette_*_lit', 'lo', *P['lit'], False), ('palette_*_shade', 'lo', *P['shade'], False),
        # an expression head's part: its value is the match distance, graded by its features' worst status
        ('expr_*', 'status', 0, 0, False), ('figures_*', 'status', 0, 0, True),
    ]
    return R


def rules():
    global _RULES
    if _RULES is None:
        try:
            _RULES = _limits()
        except Exception:                  # a QA module that can't import: every check grades by status
            _RULES = []
    return _RULES


def rule(name):
    """a check's (kind, pass, warn, warn_only); a sub-measure ('sheet_width.d75') grades as its check."""
    base = name.split('.')[0]
    for pat, kind, p, w, wo in rules():
        if fnmatch.fnmatchcase(base, pat):
            return kind, p, w, wo
    return 'status', 0, 0, False


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def severity(name, value, status=None):
    """how far `value` is from passing, in warn bands (0 = passes; 1 = at the fail limit; > 1 fails). None when neither
    the value nor the status says."""
    kind, p, w, wo = rule(name)
    if kind == 'status' or not _num(value):
        return {'PASS': 0.0, 'WARN': 0.5, 'FAIL': 1.5}.get(status)
    v = float(value)
    band = abs(w - p) or 1.0
    if kind == 'hi':
        s = (p - v) / band
    elif kind == 'lo':
        s = (v - p) / band
    elif kind == 'ratio':
        s = (abs(v - 1) - p) / band
    elif kind == 'abs':
        s = (abs(v) - p) / band
    else:                                  # count
        s = 0.5 * v
    return max(0.0, s)


def graded(qa):
    """{name: check} for the checks with a graded status."""
    return {k: c for k, c in (qa.get('checks') or {}).items() if isinstance(c, dict) and c.get('status') in GRADED}


def sev_of(name, c):
    s = severity(name, c.get('value'), c.get('status'))
    return 0.0 if s is None else s


def weight(name, authority=None):
    """1, or 0.25 for a check measured against a reference that isn't its measure's authority (manifest `authority`)."""
    m, src = measure(name)
    if not authority or not m or not src or m not in authority:
        return 1.0
    return 1.0 if authority[m] == src else 0.25


def score(qa, only=None, authority=None):
    """the QA's distance from passing: the sum of every graded check's severity (each capped at CAP), weighted by
    authority when the manifest's map is given. `only`: the check names to count (the checks two builds share)."""
    return round(sum(weight(k, authority) * min(CAP, sev_of(k, c)) for k, c in graded(qa).items()
                     if only is None or k in only), 4)


# ------------------------------------------------------------------------------------------------------------ regions
# (pattern, region, visibility): first match wins
REGIONS = [
    ('eye_highlight_side', 'eyes', 0.5),
    ('eye_*', 'eyes', 1.0),
    ('sheet_width', 'face', 1.0), ('sheet_neck_to_jaw', 'face', 0.95), ('face_shape_width', 'face', 0.9),
    ('sheet_*_chin', 'face', 0.9), ('face_shape_chin', 'face', 0.85),
    ('sheet_profile', 'face', 0.85), ('sheet_*_reach', 'face', 0.85), ('sheet_cheek', 'face', 0.85),
    ('face_shape_profile', 'face', 0.75), ('face_shape_cheek', 'face', 0.75),
    ('sheet_shown_*', 'hair', 0.7), ('face_shape_coverage_*', 'hair', 0.6),
    ('shape_iou', 'silhouette', 0.9), ('ref_iou', 'silhouette', 0.9), ('shape_iou_hair', 'silhouette', 0.9),
    ('hair_noise', 'hair', 0.6), ('scalp_px', 'hair', 0.7), ('poke_share', 'outfit', 0.5),
    ('body_*_iou', 'silhouette', 0.9), ('body_*_iou_hair', 'hair', 0.8), ('body_*_hair_*', 'hair', 0.8),
    ('body_*_iou_skin', 'silhouette', 0.75), ('body_*_iou_outfit', 'outfit', 0.8),
    ('body_*_skirt_width', 'outfit', 0.8), ('body_*_hem*', 'outfit', 0.75), ('body_*_sleeves', 'outfit', 0.7),
    ('body_*_boot', 'outfit', 0.6), ('body_*', 'silhouette', 0.85), ('figures_*', 'internal', 0.2), ('hair_*', 'hair', 0.75),
    ('expr_*', 'expressions', 0.75), ('face_expr_range', 'expressions', 0.7), ('face_blink_*', 'expressions', 0.7),
    ('face_*_asym', 'expressions', 0.7), ('face_viseme_gap', 'expressions', 0.6),
    ('palette*', 'palette', 0.8),
    ('face_shape_depth', 'internal', 0.4), ('face_folds', 'internal', 0.3), ('mesh', 'internal', 0.1),
]


def region(name):
    """-> (region, visibility)."""
    base = name.split('.')[0]
    for pat, r, v in REGIONS:
        if fnmatch.fnmatchcase(base, pat):
            return r, v
    return 'other', 0.5


# (pattern, the manifest's authority key, the reference it is measured against)
MEASURES = [
    ('sheet_width', 'face_front', 'sheet'), ('sheet_neck_to_jaw', 'face_front', 'sheet'),
    ('sheet_cheek', 'face_three_quarter', 'sheet'), ('sheet_profile', 'face_profile', 'sheet'),
    ('sheet_*_reach', 'face_profile', 'sheet'), ('sheet_*_chin', 'chin', 'sheet'),
    ('sheet_shown_*', 'hair_silhouette', 'sheet'),
    ('face_shape_width', 'face_front', 'trellis'), ('face_shape_cheek', 'face_three_quarter', 'trellis'),
    ('face_shape_profile', 'face_profile', 'trellis'), ('face_shape_chin', 'chin', 'trellis'),
    ('face_shape_depth', 'face_depth', 'trellis'), ('face_shape_coverage_*', 'hair_silhouette', 'trellis'),
    ('face_shape_features', 'feature_heights', 'rig'),
    ('eye_*', 'eyes', 'sheet'),
    ('shape_iou_hair', 'hair_shape', 'trellis'), ('shape_iou*', 'body_silhouette', 'trellis'),
    ('ref_iou', 'body_silhouette', 'key3d'), ('scalp_px', 'hair_shape', None), ('hair_noise', 'hair_shape', None),
    ('body_*_iou_hair', 'hair_silhouette', 'sheet'), ('body_*_hair_*', 'hair_silhouette', 'sheet'),
    ('body_*', 'body_silhouette', 'sheet'), ('hair_*', 'hair_silhouette', 'sheet'), ('expr_*', 'expressions', 'sheet'),
    ('figures_*', None, 'sheet'),
    ('palette*', 'palette', 'sheet'),
    ('poke_share', None, None), ('face_folds', None, None), ('face_*', 'expressions', None),
]


def authorize(checks, authority):
    """each check graded only against its measure's authority (the manifest's): a graded check measured against a
    reference that isn't its measure's authority, or whose measure has none (the expressions: the template library's),
    reads INFO, its value kept and its grade as 'graded_as'. Mixed references pulled the fits in different directions
    (Michael's review, 2026-09-28). In place and returned."""
    for k, c in list(checks.items()):
        if not isinstance(c, dict) or c.get('status') not in ('PASS', 'WARN', 'FAIL'):
            continue
        m, src = measure(k)
        if m is None or src is None or m not in authority or authority[m] == src:
            continue
        checks[k] = dict(c, status='INFO', graded_as=c['status'],
                         why='measured against %s; %s is the authority for %s' % (src, authority[m] or 'no reference', m))
    return checks


def measure(name):
    """-> (the manifest's authority key or None, the reference it is measured against or None)."""
    base = name.split('.')[0]
    for pat, m, src in MEASURES:
        if fnmatch.fnmatchcase(base, pat):
            return m, src
    return None, None


OVERLAYS = [
    ('sheet_*', ['qa/qa_sheet.png', 'sheet_views.png']), ('eye_*', ['qa/qa_eyes.png']),
    ('face_shape_*', ['qa/qa_face_contours.png', 'qa/qa_face_shape.png']),
    ('shape_iou*', ['qa/qa_shape_overlay.png', 'sheet_body.png']), ('ref_iou', ['qa/qa_ref_overlay.png', 'sheet_body.png']),
    ('scalp_px', ['qa/qa_scalp_front.png']), ('hair_noise', ['sheet_views.png']), ('poke_share', ['sheet_body.png']),
    ('face_folds', ['sheet_face.png']), ('face_*', ['sheet_face.png']), ('body_*', ['qa/qa_sheet_body.png', 'sheet_body.png']),
    ('expr_*', ['qa/qa_sheet_expr.png', 'sheet_face.png']), ('palette*', ['qa/qa_sheet_palette.png']),
    ('figures_*', ['qa/qa_sheet_figures.png']),
]


def overlays(name):
    base = name.split('.')[0]
    for pat, paths in OVERLAYS:
        if fnmatch.fnmatchcase(base, pat):
            return list(paths)
    return []


# what the check measures that no knob expresses: a template or geometry change (for the triage's "needs a capability")
CAPABILITY = {
    'face_folds': "the skin's lid and lip rings fold under the keys: the base mesh's topology round the openings "
                  "(charkit/base_anime.py re-lays them; `--base anime`), and MakeHuman's mouth cavity doesn't follow "
                  "tall openings (the laugh, yawn and wavy mouth keys fold)",
    'expr_*': "the expression library's shapes (charkit/eyes.py, mouth.py, brows.py; scene.PRESETS): a shape the "
              "sheet draws that the template doesn't have, or has only roughly, is a template addition",
    'figures_*': "the model sheet's figure detection (charkit/sheetqa.py detect_figures) against the typed head boxes",
    'hair_noise': "the generated hair's normals: the hair surface itself (charkit/geom's closed shell, `--hair geom`)",
    'scalp_px': "hair coverage: the hair volume's shape over the cranium (charkit/hair.py, charkit/geom)",
    'poke_share': "garments fitted as offsets of the body: collision-aware fitting of each piece (charkit/garments.py)",
    'eye_highlight_side': "the eye texture's highlight placement (charkit/eyetex.py has no side knob)",
    'face_expr_range': "the expression shape keys' design (charkit/eyes.py expressions)",
    'face_blink_*': "the lid shape keys (charkit/eyes.py)",
    'face_viseme_gap': "the mouth shape library (charkit/mouth.py SHAPES)",
    'face_*_asym': "the face's left/right construction (charkit/eyes.py, charkit/mouth.py)",
    'mesh': "mesh health (open edges, loose parts)",
}


def capability(name):
    base = name.split('.')[0]
    for pat, what in CAPABILITY.items():
        if fnmatch.fnmatchcase(base, pat):
            return what
    return None


# the spec sections whose knobs can move a check (the knob inventory's map; used when no fitter measures it)
SECTIONS = [
    ('sheet_*', ['head', 'body.proportions.neck_w', 'body.proportions.neck_len']),
    ('face_shape_*', ['head', 'body.proportions.neck_w']),
    ('eye_*', ['eyes', 'iris']),
    ('shape_iou_hair', ['hair', 'accessories']), ('shape_iou*', ['body', 'hair', 'garments', 'outfit', 'accessories']),
    ('ref_iou', ['body', 'hair', 'garments', 'outfit', 'accessories']),
    ('scalp_px', ['hair']), ('hair_noise', ['hair.shape']), ('poke_share', ['garments', 'outfit']),
    ('face_folds', ['base']), ('face_*', ['eyes', 'mouth', 'brows']),
    ('body_*_iou_hair', ['hair']), ('body_*_hair_*', ['hair']), ('body_*_skirt_width', ['garments', 'outfit']),
    ('body_*_hem*', ['garments', 'outfit']), ('body_*_sleeves', ['garments', 'outfit']), ('body_*_boot', ['garments', 'outfit']),
    ('body_*', ['body', 'garments', 'outfit']), ('hair_*', ['hair']), ('expr_*', ['eyes', 'mouth', 'brows']),
    ('palette_skin_*', ['skin']), ('palette_hair_*', ['hair_colors']), ('palette_iris_*', ['iris']),
    ('palette_orange_*', ['garments', 'outfit']), ('palette_cream_*', ['garments', 'outfit']),
    ('palette_dark_*', ['garments', 'outfit']), ('palette_white_*', ['garments', 'outfit']),
    ('palette*', ['garments', 'outfit', 'accessories', 'skin', 'hair_colors', 'iris']),
]


def sections(name):
    base = name.split('.')[0]
    for pat, secs in SECTIONS:
        if fnmatch.fnmatchcase(base, pat):
            return list(secs)
    return []
