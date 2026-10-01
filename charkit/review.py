"""The review checkpoint: a person looks at the build beside the design, writes down what the numbers missed, and each
note becomes a ticket, either a measurement to add or a work item (docs/CHARKIT.md §4). Every check is a proxy; the face
checks exist because someone saw a problem the metrics didn't, so review feeds the metrics.

    python -m charkit review board BUILD [--spec SPEC]         # BUILD/review/: board.png, index.html, notes.json
    python -m charkit review serve BUILD [--port 8765]         # the board page, saving notes and tickets (127.0.0.1 only)
    python -m charkit review note BUILD "the face reads long" [--view front] [--region face] [--severity 1-3] [--checks a,b]
                                   [--author NAME]
    python -m charkit review ticket BUILD NOTE_ID [--measure | --work] [--check NAME]
    python -m charkit review tickets NAME [--build BUILD] [--sync]   # the character's tickets; --sync marks landed ones
    python -m charkit review page PAGE.json [--out DIR] [--open]   # the standard review page (charkit/reviewpage.py)

  board    the design's model sheet beside our views, body and face sheets and the QA overlays, with the ranked work items
           (BUILD/review/board.png, and index.html to click through)
  notes    BUILD/review/notes.json (and notes.md): {id, text, view, region, severity, checks, camera?, status, ticket}
           written from the page (the review server), the inspector's review panel (projects/charkit-look, served by the
           review server) or the command line
  tickets  charkit/refs/NAME/tickets.json (tracked: tickets outlive builds). A note is matched against CONCERNS, what a
           reviewer's words usually mean ("long" + face -> the face's length over its width; "flat" + bangs -> the hair's
           shape, not its shading), giving the checks that measure it: the ones the note names, else its first
           concern's. If any of them is WARN or FAIL in the build, the note is a `work` ticket: it joins those checks'
           work items as evidence and ranks them higher. If they all pass (the metrics missed it), it is a `measure`
           ticket: a proposed check (name, what to measure, views, the reference that is the authority), the passing
           checks that should have caught it, and, where the QA's own tables already hold the numbers, the proposed
           measure's value now (a prototype, e.g. the face's length over its width against the design's, from
           sheetqa's chin and widths). The triage lists every open measure ticket as `needs a measurement` until a check
           of that name appears in a build's QA (`tickets --sync` then marks it landed), and measures its prototype
           again on every build it triages: the reviewer's note is a tracked (provisional) number from then on.
"""
import html, json, os, re, time

from . import checks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _rel(p):
    return os.path.relpath(p, ROOT) if p and os.path.isabs(p) and p.startswith(ROOT) else p


# ------------------------------------------------------------------------------------------------------------ prototypes
# a proposed measure computed from what the QA already records (qa.json's tables), so a ticket carries a number
def _proto_face_length(qa):
    S = (qa.get('sheet') or {})
    o, d = (S.get('ours') or {}).get('front') or {}, (S.get('design') or {}).get('front') or {}
    wo, wd = (o.get('widths') or {}).get('d55'), (d.get('widths') or {}).get('d55')
    if not (o.get('chin') and d.get('chin') and wo and wd):
        return None
    ro, rd = abs(o['chin']) / wo, abs(d['chin']) / wd
    return {'value': round(ro / rd, 3), 'ours': round(ro, 3), 'design': round(rd, 3), 'kind': 'ratio', 'limits': [0.04, 0.08],
            'how': "front view: the chin's depth under the eye line over the half-width at 55% of the way to the chin (sheetqa's "
                   "chin and widths.d55), ours over the design's"}


def _proto_jaw_taper(qa):
    S = (qa.get('sheet') or {})
    o, d = ((S.get('ours') or {}).get('front') or {}).get('widths') or {}, ((S.get('design') or {}).get('front') or {}).get('widths') or {}
    if not all(x.get(k) for x in (o, d) for k in ('d55', 'd75')):
        return None
    ro, rd = o['d75'] / o['d55'], d['d75'] / d['d55']
    return {'value': round(ro / rd, 3), 'ours': round(ro, 3), 'design': round(rd, 3), 'kind': 'ratio', 'limits': [0.05, 0.10],
            'how': 'front view: the half-width at 75% over the half-width at 55% (how fast the jaw narrows), ours over the design\'s'}


def _proto_eye_to_face(qa):
    E = qa.get('eyes') or {}
    S = (qa.get('sheet') or {})
    wo = (((S.get('ours') or {}).get('front') or {}).get('widths') or {}).get('d55')
    wd = (((S.get('design') or {}).get('front') or {}).get('widths') or {}).get('d55')
    eo = [E[s]['ours'].get('open_w') for s in ('L', 'R') if s in E and E[s].get('ours')]
    ed = [E[s]['design'].get('open_w') for s in ('L', 'R') if s in E and E[s].get('design')]
    if not (wo and wd and eo and ed and all(eo) and all(ed)):
        return None
    ro, rd = (sum(eo) / len(eo)) / wo, (sum(ed) / len(ed)) / wd
    return {'value': round(ro / rd, 3), 'ours': round(ro, 3), 'design': round(rd, 3), 'kind': 'ratio', 'limits': [0.08, 0.15],
            'how': "the eye opening's width (eyeqa) over the face's half-width at 55% (sheetqa), ours over the design's"}


def _proto_feature(key):
    def f(qa):
        F = ((qa.get('face_shape') or {}).get('features') or {}).get(key) or {}
        if F.get('ours') is None or F.get('design') is None:
            return None
        return {'value': round(F['ours'] - F['design'], 4), 'ours': F['ours'], 'design': F['design'], 'kind': 'abs',
                'limits': [0.02, 0.04], 'how': '%s under the eye line (faceqa features, informational today), ours minus the '
                                               'design rig\'s, in head lengths' % key}
    return f


def prototype(name, qa):
    """a proposed measure's value on a build's QA, graded against its own proposed limits -> {value, ours, design,
    kind, limits, how, status} or None (no prototype by that name, or the tables lack its numbers)."""
    fn = PROTOS.get(name or '')
    v = fn(qa) if fn else None
    if v:
        x = abs(v['value'] - 1) if v['kind'] == 'ratio' else abs(v['value'])
        v['status'] = 'PASS' if x <= v['limits'][0] else 'WARN' if x <= v['limits'][1] else 'FAIL'
    return v


PROTOS = {'face_length': _proto_face_length, 'jaw_taper': _proto_jaw_taper, 'eye_to_face': _proto_eye_to_face,
          'nose_height': _proto_feature('nose_z'), 'mouth_height': _proto_feature('mouth_z'),
          'brow_height': _proto_feature('brow_z')}

# what a reviewer's words usually mean: (id, words, region, the checks that measure it, the measurement to add)
CONCERNS = [
    {'id': 'face_length', 'words': r'\b(long|tall|elongat\w*|length|short|squat|stubby)\b', 'with': r'\b(face|head|chin|jaw)\b',
     'region': 'face', 'checks': ['sheet_*_chin', 'face_shape_chin', 'sheet_width'],
     'propose': {'check': 'sheet_face_length', 'views': ['front'], 'measure': 'face_front', 'proto': 'face_length',
                 'what': "the face's length over its width against the design's (a face can pass the chin's height and "
                         "each width alone and still read long)"}},
    {'id': 'jaw', 'words': r'\b(jaw\w*|pointed|pointy|sharp|v[- ]?shape\w*|taper\w*)\b', 'with': None,
     'region': 'face', 'checks': ['sheet_neck_to_jaw', 'sheet_width', 'sheet_*_chin'],
     'propose': {'check': 'sheet_jaw_taper', 'views': ['front'], 'measure': 'face_front', 'proto': 'jaw_taper',
                 'what': 'how fast the lower face narrows to the chin, against the design'}},
    {'id': 'face_width', 'words': r'\b(wide|narrow|round|chubby|puffy|fat|thin|gaunt|broad)\b', 'with': r'\b(face|cheek\w*|head)\b',
     'region': 'face', 'checks': ['sheet_width', 'face_shape_width', 'sheet_cheek', 'face_shape_cheek'],
     'propose': {'check': 'sheet_width_d35', 'views': ['front', 'three_quarter'], 'measure': 'face_front', 'proto': None,
                 'what': 'the upper cheeks\' half-width (35% of the way to the chin), which the widths at 55/75% miss'}},
    {'id': 'eyes', 'words': r'\b(eyes?|iris|pupils?|lids?|lash\w*)\b', 'with': None,
     'region': 'eyes', 'checks': ['eye_*'],
     'propose': {'check': 'eye_face_share', 'views': ['front'], 'measure': 'eyes', 'proto': 'eye_to_face',
                 'what': "the eyes' size in the face: the opening's width over the face's width, against the design"}},
    {'id': 'nose', 'words': r'\bnose\b', 'with': None, 'region': 'face', 'checks': ['sheet_nose_reach'],
     'propose': {'check': 'face_nose_height', 'views': ['front', 'profile'], 'measure': 'feature_heights', 'proto': 'nose_height',
                 'what': "the nose tip's height under the eye line against the design's"}},
    {'id': 'mouth', 'words': r'\b(mouth|lips?|smile|teeth)\b', 'with': None, 'region': 'face',
     'checks': ['face_mouth_asym', 'face_viseme_gap', 'expr_mouth*'],
     'propose': {'check': 'face_mouth_height', 'views': ['front'], 'measure': 'feature_heights', 'proto': 'mouth_height',
                 'what': "the mouth line's height under the eye line against the design's"}},
    {'id': 'brows', 'words': r'\b(brows?|eyebrows?)\b', 'with': None, 'region': 'face', 'checks': ['expr_brow*'],
     'propose': {'check': 'face_brow_height', 'views': ['front'], 'measure': 'feature_heights', 'proto': 'brow_height',
                 'what': "the brows' height over the eye line against the design's"}},
    {'id': 'neck', 'words': r'\bneck\b', 'with': None, 'region': 'face', 'checks': ['sheet_neck_to_jaw'],
     'propose': {'check': 'sheet_neck_length', 'views': ['front', 'profile'], 'measure': 'body_silhouette', 'proto': None,
                 'what': "the neck's length from the chin to the collar against the design's"}},
    {'id': 'hair_shading', 'words': r'\b(nois\w*|shading|shadows?|strands?|texture|messy|blotch\w*|speckl\w*)\b',
     'with': r'\b(hair|bangs?|fringe|buns?)\b', 'region': 'hair', 'checks': ['hair_noise'],
     'propose': {'check': 'hair_tone_regions', 'views': ['front', 'three_quarter'], 'measure': 'hair_shape', 'proto': None,
                 'what': "the hair's shadow shapes: how many tone regions and how ragged their edges, against the design's"}},
    {'id': 'hair_framing', 'words': r'\b(cover\w*|hid\w*|shows?|showing|framing|frames?)\b',
     'with': r'\b(hair|bangs?|fringe)\b', 'region': 'hair', 'checks': ['sheet_shown_*', 'face_shape_coverage_*'],
     'propose': {'check': 'sheet_fringe_line', 'views': ['front'], 'measure': 'hair_silhouette', 'proto': None,
                 'what': "the fringe's lower edge across the face against the design's"}},
    {'id': 'hair_shape', 'words': r'\b(hair|bangs?|fringe|buns?|ahoge|helmet|volume|flat|puffy|outline|silhouette)\b',
     'with': None, 'region': 'hair', 'checks': ['shape_iou_hair', 'body_*_iou_hair', 'body_*_hair_*', 'hair_*', '!hair_noise',
                                                'scalp_px'],
     'propose': {'check': 'hair_front_outline', 'views': ['front', 'three_quarter', 'back'], 'measure': 'hair_silhouette',
                 'proto': None, 'what': "the hair's outline per view against the design's figures (its volume and where "
                                        "the bangs stand off the forehead)"}},
    {'id': 'body', 'words': r'\b(legs?|torso|arms?|shoulders?|hips?|proportion\w*|heads? tall|height|body|chest)\b', 'with': None,
     'region': 'silhouette', 'checks': ['shape_iou', 'ref_iou', 'body_*_iou', 'body_*_iou_skin', 'body_*_feet', 'body_*_top',
                                        'body_*_leg'],
     'propose': {'check': 'body_proportions', 'views': ['front', 'profile'], 'measure': 'body_silhouette', 'proto': None,
                 'what': "the figure's segment lengths (head, torso, legs) against the design's"}},
    {'id': 'outfit', 'words': r'\b(skirt|dress|sleeves?|collar|bow|cuffs?|boots?|shoes?|shorts|outfit|clothes|hem|pleat\w*)\b', 'with': None,
     'region': 'outfit', 'checks': ['body_*_skirt_width', 'body_*_hem*', 'body_*_iou_outfit', 'body_*_sleeves', 'body_*_boot',
                                    'poke_share'],
     'propose': {'check': 'body_outfit_outline', 'views': ['front', 'three_quarter'], 'measure': 'body_silhouette', 'proto': None,
                 'what': "the named garment's outline against the design's"}},
    {'id': 'colour', 'words': r'\b(colou?rs?|tones?|palette|pale|saturat\w*|hue|dull|bright)\b', 'with': None, 'region': 'palette',
     'checks': ['palette*'],
     'propose': {'check': 'palette_region', 'views': ['front'], 'measure': 'palette', 'proto': None,
                 'what': "the named region's lit and shade colours against the design's"}},
    {'id': 'expression', 'words': r'\b(expression\w*|blink\w*|happy|angry|sad|surprised|wink)\b', 'with': None,
     'region': 'expressions', 'checks': ['face_expr_range', 'face_blink_*', 'expr_*'],
     'propose': {'check': 'expr_shape', 'views': ['front'], 'measure': 'expressions', 'proto': None,
                 'what': "the named expression's eye and mouth shapes against the sheet's expression heads"}},
]


def concerns(text):
    """the CONCERNS a note's words match, the most specific first: a concern matched on two parts (its words and its
    subject: "hide" + "bangs") before one matched on a word alone ("eyes")."""
    t = text.lower()
    out = []
    for c in CONCERNS:
        if re.search(c['words'], t) and (not c['with'] or re.search(c['with'], t)):
            out.append(c)
    return sorted(out, key=lambda c: 0 if c['with'] else 1)


# ------------------------------------------------------------------------------------------------------------ notes
def _notes_path(build):
    return os.path.join(_path(build), 'review', 'notes.json')


def load_notes(build):
    p = _notes_path(build)
    return json.load(open(p)) if os.path.exists(p) else {'build': _rel(_path(build)), 'notes': []}


def save_notes(build, N):
    p = _notes_path(build)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(N, open(p, 'w'), indent=1)
    L = ['# Review notes: %s' % N['build'], '']
    for n in N['notes']:
        L.append('- **%s** [%s/%s, severity %s] %s%s' % (n['id'], n.get('view') or '-', n.get('region') or '-', n.get('severity', 2),
                                                          n['text'], ' -> ticket %s' % n['ticket'] if n.get('ticket') else ''))
    open(os.path.join(os.path.dirname(p), 'notes.md'), 'w').write('\n'.join(L) + '\n')
    return p


def add_note(build, text, view=None, region=None, severity=2, checks_=None, camera=None, author=None):
    N = load_notes(build)
    n = {'id': 'N%03d' % (len(N['notes']) + 1), 't': time.strftime('%Y-%m-%dT%H:%M:%S'), 'text': text.strip(), 'view': view,
         'region': region or (concerns(text)[0]['region'] if concerns(text) else None), 'severity': int(severity or 2),
         'checks': [c for c in (checks_ or []) if c], 'status': 'open'}
    if camera:
        n['camera'] = camera
    if author:
        n['author'] = author
    N['notes'].append(n)
    save_notes(build, N)
    return n


# ------------------------------------------------------------------------------------------------------------ tickets
def _spec_of(build):
    """the build's resolved spec (BUILD/NAME.spec.json)."""
    b = _path(build)
    for f in sorted(os.listdir(b)):
        if f.endswith('.spec.json'):
            return json.load(open(os.path.join(b, f)))
    raise SystemExit('no resolved spec in %s' % build)


def tickets_file(spec):
    from .triage import tickets_path
    return tickets_path(spec)


def load_tickets(spec):
    p = tickets_file(spec)
    return json.load(open(p)) if os.path.exists(p) else {'character': spec['name'], 'tickets': []}


def ticket(build, note_id, kind=None, check=None):
    """turn a note into a ticket (see the module docstring) -> the ticket; written to charkit/refs/NAME/tickets.json."""
    import fnmatch
    b = _path(build)
    N = load_notes(b)
    note = next((n for n in N['notes'] if n['id'] == note_id), None)
    if note is None:
        raise SystemExit('no note %s in %s' % (note_id, _notes_path(b)))
    spec = _spec_of(b)
    qa = json.load(open(os.path.join(b, 'qa', 'qa.json')))
    C = qa.get('checks') or {}
    found = concerns(note['text'])
    def graded(pats):                                  # glob patterns; '!pattern' leaves matches out
        inc, exc = [p for p in pats if not p.startswith('!')], [p[1:] for p in pats if p.startswith('!')]
        return sorted({k for k in C for p in inc if fnmatch.fnmatchcase(k, p) and not any(fnmatch.fnmatchcase(k, x) for x in exc)
                       and C[k].get('status') in checks.GRADED})
    # the checks that measure what the note says: the ones it names, else its first (most specific) concern's; the
    # other concerns' checks are listed as related
    direct = graded(list(note.get('checks') or []) or (found[0]['checks'] if found else []))
    related = graded(list(note.get('checks') or []) + [p for c in found for p in c['checks']])
    bad = [k for k in direct if C[k]['status'] != 'PASS']
    ok = [k for k in direct if C[k]['status'] == 'PASS']
    kind = kind or ('work' if bad else 'measure')
    T = load_tickets(spec)
    t = {'id': 'T%03d' % (len(T['tickets']) + 1), 'kind': kind, 'status': 'open', 'created': time.strftime('%Y-%m-%dT%H:%M:%S'),
         'text': note['text'], 'note': note_id, 'build': _rel(b), 'view': note.get('view'),
         'region': note.get('region') or (found[0]['region'] if found else None), 'severity': note.get('severity', 2),
         'concerns': [c['id'] for c in found], 'direct': direct,
         'related': {k: [C[k].get('value'), C[k]['status']] for k in related}}
    for k in ('camera', 'author'):
        if note.get(k):
            t[k] = note[k]
    t['board'] = os.path.join(_rel(b), 'review', 'board.png')
    if kind == 'work':
        t['checks'] = [check] if check else (bad or direct or related)
    else:
        prop = dict(found[0]['propose']) if found else {
            'check': check or 'review_' + re.sub(r'[^a-z0-9]+', '_', note['text'].lower()).strip('_')[:32],
            'views': [note.get('view')] if note.get('view') else [], 'measure': None, 'proto': None,
            'what': note['text']}
        if check:
            prop['check'] = check
        v = prototype(prop.get('proto'), qa)
        if v:
            prop['prototype'] = v
            prop['value'] = v['value']
        else:
            prop.pop('proto', None)
        t['proposed'] = prop
        t['missed_by'] = ok
        ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
        if prop.get('measure'):
            t['reference'] = {'measure': prop['measure'], 'authority': (ref.get('authority') or {}).get(prop['measure'])}
    T['tickets'].append(t)
    p = tickets_file(spec)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(T, open(p, 'w'), indent=1)
    note['status'], note['ticket'] = 'ticketed', t['id']
    save_notes(b, N)
    return t


def sync(spec, build=None):
    """mark measure tickets landed where a check of their proposed name exists (in `build`'s QA, or the latest history
    row) -> the tickets that changed."""
    from . import history
    T = load_tickets(spec)
    if build:
        names = set((json.load(open(os.path.join(_path(build), 'qa', 'qa.json'))).get('checks') or {}).keys())
    else:
        rows = history.read(spec['name'])
        names = set(rows[-1]['checks']) if rows else set()
    changed = []
    for t in T['tickets']:
        n = (t.get('proposed') or {}).get('check')
        if t['kind'] == 'measure' and t['status'] == 'open' and n in names:
            t['status'] = 'landed'; t['landed'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            changed.append(t)
    if changed:
        json.dump(T, open(tickets_file(spec), 'w'), indent=1)
    return changed


# ------------------------------------------------------------------------------------------------------------ board
BOARD_OVERLAYS = ['qa/qa_sheet.png', 'qa/qa_eyes.png', 'qa/qa_face_contours.png', 'qa/qa_face_shape.png',
                  'qa/qa_sheet_body.png', 'qa/qa_sheet_expr.png', 'qa/qa_sheet_palette.png', 'qa/qa_shape_overlay.png',
                  'qa/qa_ref_overlay.png', 'qa/qa_scalp_front.png', 'qa/qa_sheet_figures.png']
BOARD_SHEETS = ['sheet_views.png', 'sheet_body.png', 'sheet_face.png']


def _font(size):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                                 # Pillow < 10.1: the bitmap font
        return ImageFont.load_default()


def _row(named, W, max_h, pad=10, lab=26):
    """images side by side at one height, scaled to fill the width W (at most max_h tall), each labelled."""
    from PIL import Image, ImageDraw
    h = min(max_h, (W - pad * (len(named) - 1)) / sum(im.width / im.height for _, im in named))
    R = Image.new('RGB', (W, int(h) + lab), 'white')
    d = ImageDraw.Draw(R)
    x = 0
    for n, im in named:
        w = max(1, int(im.width * h / im.height))
        R.paste(im.resize((w, int(h))), (x, lab))
        d.text((x + 4, 3), n, fill=(20, 20, 20), font=_font(18))
        x += w + pad
    return R


def board(build, spec, items=None, W=2400):
    """the review board: the design's model sheet beside our full-body sheet, our head views and face sheet, the QA
    overlays under them, the top work items as text -> BUILD/review/board.png."""
    from PIL import Image, ImageDraw
    b = _path(build)
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    design = (ref.get('sheet') or {}).get('image')
    img = lambda p: Image.open(p).convert('RGB')
    have = {s: img(os.path.join(b, s)) for s in BOARD_SHEETS + BOARD_OVERLAYS if os.path.exists(os.path.join(b, s))}
    rows = []
    first = []
    if design and os.path.exists(_path(design)):
        first.append(('the design: %s' % os.path.basename(design), img(_path(design))))
    if 'sheet_body.png' in have:
        first.append(('ours: sheet_body.png (0 35 90 180)', have['sheet_body.png']))
    if first:
        rows.append(_row(first, W, 900))
    for s, h in (('sheet_views.png', 520), ('sheet_face.png', 420)):
        if s in have:
            rows.append(_row([('ours: ' + s, have[s])], W, h))
    ovs = [(o, have[o]) for o in BOARD_OVERLAYS if o in have]
    for i in range(0, len(ovs), 4):
        rows.append(_row(ovs[i:i + 4], W, 520))
    if items:
        f = _font(19)
        cols = (8, 50, 390, 460, 560, 800)                     # rank, check, status, value, class, why
        R = Image.new('RGB', (W, 26 * min(20, len(items)) + 44), (248, 248, 244))
        d = ImageDraw.Draw(R)
        d.text((8, 8), 'work items (charkit/triage.py): rank, check, status, value, class, why', fill=(0, 0, 0), font=_font(20))
        for i, it in enumerate(items[:20]):
            v = it['value']
            vals = ['%d.' % it['rank'], it['check'][:30], it['status'],
                    ('%.4g' % v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)[:9], it['class'],
                    it['detail'][:140]]
            for x, t in zip(cols, vals):
                d.text((x, 38 + 26 * i), t, fill=(30, 30, 30), font=f)
        rows.append(R)
    if not rows:
        return None
    pad = 12
    B = Image.new('RGB', (W, sum(r.height for r in rows) + pad * (len(rows) - 1)), (225, 225, 228))
    y = 0
    for r in rows:
        B.paste(r, (0, y)); y += r.height + pad
    out = os.path.join(b, 'review', 'board.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    B.save(out)
    return out


PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review: %(name)s</title>
<style>
:root{--bg:#f6f5f1;--fg:#1d1d1f;--mut:#6b6b70;--card:#fff;--line:#dedcd6;--pass:#2f7d4a;--warn:#a86b00;--fail:#b3261e}
@media (prefers-color-scheme: dark){:root:not([data-theme=light]){--bg:#17181a;--fg:#ececec;--mut:#9a9aa0;--card:#222326;--line:#34353a}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
main{max-width:1500px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:4px 0 2px} h2{font-size:16px;margin:22px 0 8px}
.mut{color:var(--mut)} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px}
figure img{width:100%%;height:auto;display:block;cursor:crosshair} figcaption{font-size:12px;color:var(--mut);margin-top:4px}
.wide{grid-column:1/-1}
table{border-collapse:collapse;width:100%%;background:var(--card);font-size:13px} td,th{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
.FAIL{color:var(--fail)} .WARN{color:var(--warn)} .PASS{color:var(--pass)}
form{display:grid;gap:6px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}
textarea{min-height:60px;font:inherit} input,select,textarea,button{font:inherit;padding:4px}
.row{display:flex;gap:8px;flex-wrap:wrap} .note{padding:6px 0;border-bottom:1px solid var(--line)} code{font-size:12px}
</style></head><body><main>
<h1>Review: %(name)s</h1>
<div class="mut">build <code>%(build)s</code> · QA %(summary)s · score %(score)s · %(n_items)d work items</div>
<h2>The design beside the build</h2>
<div class="grid">%(sheets)s</div>
<h2>QA overlays</h2>
<div class="grid">%(overlays)s</div>
<h2>Work items</h2>
<table><tr><th>#</th><th>check</th><th>status</th><th>value</th><th>class</th><th>why</th></tr>%(items)s</table>
<h2>Notes</h2>
<form id="f">
<textarea id="text" placeholder="what the numbers miss, in your words: 'the face reads long', 'the bangs sit too flat'"></textarea>
<div class="row"><label>view <select id="view"><option></option><option>front</option><option>three_quarter</option><option>profile</option><option>back</option><option>body</option><option>expressions</option></select></label>
<label>region <select id="region"><option></option><option>face</option><option>eyes</option><option>hair</option><option>silhouette</option><option>outfit</option><option>expressions</option><option>palette</option></select></label>
<label>severity <select id="sev"><option value="1">1 minor</option><option value="2" selected>2 visible</option><option value="3">3 reads wrong</option></select></label>
<label>checks <input id="checks" placeholder="optional: sheet_width,…"></label>
<button type="submit">save note</button></div>
<div id="msg" class="mut">Click a picture to pick its view. Saving needs the review server: <code>python -m charkit review serve %(build)s</code>.
Offline: <code>python -m charkit review note %(build)s "…"</code></div>
</form>
<div id="notes"></div>
</main>
<script>
const BUILD = %(build_js)s;
const $ = id => document.getElementById(id);
document.querySelectorAll('figure img').forEach(im => im.onclick = () => { const v = im.dataset.view; if (v) $('view').value = v; $('text').focus(); });
async function load() {
  try {
    const r = await fetch('notes.json', {cache: 'no-store'}); if (!r.ok) return;
    const N = await r.json(); const box = $('notes'); box.textContent = '';
    for (const n of N.notes.slice().reverse()) {
      const d = document.createElement('div'); d.className = 'note';
      d.textContent = `${n.id} [${n.view || '-'}/${n.region || '-'}, severity ${n.severity}] ${n.text}` + (n.ticket ? ` -> ticket ${n.ticket}` : '');
      if (!n.ticket) { for (const k of ['measure', 'work', 'auto']) { const b = document.createElement('button'); b.textContent = k === 'auto' ? 'ticket' : 'ticket: ' + k;
        b.onclick = async () => { const r = await fetch('/api/ticket', {method: 'POST', body: JSON.stringify({build: BUILD, note: n.id, kind: k === 'auto' ? null : k})});
          $('msg').textContent = r.ok ? 'ticket: ' + JSON.stringify((await r.json()).ticket).slice(0, 300) : 'ticket failed (' + r.status + ')'; load(); }; d.append(' ', b); } }
      box.append(d);
    }
  } catch (e) {}
}
$('f').onsubmit = async e => {
  e.preventDefault();
  const body = {build: BUILD, text: $('text').value, view: $('view').value || null, region: $('region').value || null,
                severity: +$('sev').value, checks: $('checks').value.split(',').map(s => s.trim()).filter(Boolean)};
  if (!body.text.trim()) return;
  try { const r = await fetch('/api/note', {method: 'POST', body: JSON.stringify(body)}); if (!r.ok) throw new Error(r.status);
    $('msg').textContent = 'saved ' + (await r.json()).note.id; $('text').value = ''; load();
  } catch (err) { $('msg').textContent = 'not saved (' + err.message + '): serve this page with python -m charkit review serve ' + BUILD; }
};
load();
</script></body></html>
"""


def page(build, spec, items=None, qa=None):
    """BUILD/review/index.html: the pictures, the work items and the notes form."""
    b = _path(build)
    rv = os.path.join(b, 'review')
    os.makedirs(rv, exist_ok=True)
    rel = lambda p: os.path.relpath(p, rv)
    views = {'sheet_views.png': 'front', 'sheet_body.png': 'body', 'sheet_face.png': 'expressions', 'qa/qa_sheet.png': 'profile',
             'qa/qa_eyes.png': 'front', 'qa/qa_face_contours.png': 'three_quarter', 'qa/qa_sheet_body.png': 'body',
             'qa/qa_sheet_expr.png': 'expressions'}
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    design = (ref.get('sheet') or {}).get('image')
    sh = []
    if design and os.path.exists(_path(design)):
        sh.append('<figure><img src="%s" data-view="front"><figcaption>the design: %s (authority for the face, body, expressions, '
                  'palette)</figcaption></figure>' % (html.escape(rel(_path(design))), html.escape(design)))
    for s in BOARD_SHEETS:
        if os.path.exists(os.path.join(b, s)):
            sh.append('<figure class="%s"><img src="%s" data-view="%s"><figcaption>%s</figcaption></figure>' % (
                'wide' if s != 'sheet_face.png' else '', html.escape(rel(os.path.join(b, s))), views.get(s, ''), s))
    ov = ['<figure><img src="%s" data-view="%s"><figcaption>%s</figcaption></figure>' % (
        html.escape(rel(os.path.join(b, o))), views.get(o, ''), o) for o in BOARD_OVERLAYS if os.path.exists(os.path.join(b, o))]
    if os.path.exists(os.path.join(rv, 'board.png')):
        ov.append('<figure class="wide"><img src="board.png"><figcaption>the whole board (board.png)</figcaption></figure>')
    it = []
    for x in items or []:
        v = x['value']
        vs = ('%.4g' % v) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)[:16]
        it.append('<tr><td>%d</td><td>%s</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            x['rank'], html.escape(x['check']), x['status'], x['status'], html.escape(vs), html.escape(x['class']), html.escape(x['detail'])))
    qa = qa or {}
    doc = PAGE % {'name': html.escape(spec['name']), 'build': html.escape(_rel(b)), 'build_js': json.dumps(_rel(b)),
                  'summary': qa.get('summary', '?'), 'score': checks.score(qa, authority=(spec.get('ref') or {}).get('authority') if isinstance(spec.get('ref'), dict) else None) if qa else '?', 'n_items': len(items or []),
                  'sheets': ''.join(sh), 'overlays': ''.join(ov), 'items': ''.join(it)}
    p = os.path.join(rv, 'index.html')
    open(p, 'w').write(doc)
    return p


def prepare(build, spec, T=None, run=None):
    """the review checkpoint's files for a build: board, page, notes (kept if present) -> paths."""
    b = _path(build)
    qa = json.load(open(os.path.join(b, 'qa', 'qa.json')))
    its = (T or {}).get('items')
    if its is None:
        wp = os.path.join(b, 'triage', 'work_items.json')
        its = json.load(open(wp))['items'] if os.path.exists(wp) else []
    bp = board(b, spec, its)
    pp = page(b, spec, its, qa)
    N = load_notes(b)
    if run:
        N.setdefault('tune', run)
    np_ = save_notes(b, N)
    return {'board': bp, 'page': pp, 'notes': np_}


# ------------------------------------------------------------------------------------------------------------ server
def serve(build, port=8765):
    """the review page over http on 127.0.0.1: GET serves the repo's files (read only, inside the repo); POST /api/note
    and /api/ticket write the notes and tickets."""
    import http.server, mimetypes, socketserver
    b = _path(build)
    root = os.path.realpath(ROOT)

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype='application/json'):
            data = body if isinstance(body, bytes) else body.encode()
            self.send_response(code); self.send_header('content-type', ctype); self.send_header('cache-control', 'no-store')
            self.send_header('content-length', str(len(data))); self.end_headers(); self.wfile.write(data)

        def do_GET(self):
            from urllib.parse import unquote
            p = os.path.realpath(os.path.join(root, unquote(self.path.split('?')[0]).lstrip('/')))
            if not p.startswith(root + os.sep) or not os.path.isfile(p):
                return self._send(404, b'')
            self._send(200, open(p, 'rb').read(), mimetypes.guess_type(p)[0] or 'application/octet-stream')

        def do_POST(self):
            try:
                n = int(self.headers.get('content-length') or 0)
                body = json.loads(self.rfile.read(n) or b'{}')
                bd = _path(body.get('build') or _rel(b))
                if not os.path.realpath(bd).startswith(root + os.sep):
                    return self._send(403, json.dumps({'error': 'outside the repo'}))
                if self.path == '/api/note':
                    note = add_note(bd, body['text'], body.get('view'), body.get('region'), body.get('severity', 2),
                                    body.get('checks'), body.get('camera'), body.get('author'))
                    return self._send(200, json.dumps({'note': note}))
                if self.path == '/api/ticket':
                    t = ticket(bd, body['note'], body.get('kind'), body.get('check'))
                    return self._send(200, json.dumps({'ticket': t}, default=str))
                return self._send(404, b'{}')
            except (SystemExit, KeyError, ValueError) as e:
                return self._send(400, json.dumps({'error': str(e)}))

    class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True
    srv = S(('127.0.0.1', port), H)
    url = 'http://127.0.0.1:%d/%s' % (srv.server_address[1], os.path.relpath(os.path.join(b, 'review', 'index.html'), ROOT))
    print('review:', url)
    print('inspector with notes: http://127.0.0.1:%d/projects/charkit-look/index.html?vrm=%s' % (
        srv.server_address[1], next((os.path.relpath(os.path.join(b, f), ROOT) for f in os.listdir(b) if f.endswith('.vrm')), '...')))
    srv.serve_forever()


# ------------------------------------------------------------------------------------------------------------ CLI
def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    cmd, rest = args[0], args[1:]
    opt = lambda k, d=None: rest[rest.index(k) + 1] if k in rest else d
    if cmd == 'page':
        from . import reviewpage
        return reviewpage.main(rest)
    if cmd == 'board':
        from . import manifest
        b = _path(rest[0])
        spec = manifest.resolve(json.load(open(_path(opt('--spec'))))) if opt('--spec') else _spec_of(b)
        P = prepare(b, spec)
        for k, v in P.items():
            print(k, _rel(v))
    elif cmd == 'serve':
        serve(rest[0], int(opt('--port', 8765)))
    elif cmd == 'note':
        n = add_note(rest[0], rest[1], opt('--view'), opt('--region'), opt('--severity', 2),
                     (opt('--checks') or '').split(','), author=opt('--author'))
        print(json.dumps(n))
    elif cmd == 'ticket':
        kind = 'measure' if '--measure' in rest else 'work' if '--work' in rest else None
        t = ticket(rest[0], rest[1], kind, opt('--check'))
        print(json.dumps(t, indent=1, default=str))
        print('wrote', _rel(tickets_file(_spec_of(rest[0]))))
    elif cmd == 'tickets':
        from . import manifest
        name = rest[0]
        spec = manifest.resolve(json.load(open(_path('charkit/spec/%s.json' % name))))
        if '--sync' in rest:
            for t in sync(spec, opt('--build')):
                print('landed', t['id'], t['proposed']['check'])
        for t in load_tickets(spec)['tickets']:
            print('%s %-7s %-7s %-22s %s' % (t['id'], t['kind'], t['status'], (t.get('proposed') or {}).get('check') or
                                            ','.join(t.get('checks') or []), t['text']))
    else:
        raise SystemExit('unknown review command %r\n%s' % (cmd, __doc__))
