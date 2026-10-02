"""the neck's chin shadow on two builds (coordinator, 2026-10-01: verify art_terminator_neck before working on it): per
view the artifact detector's neck window (its area and shade share, the terminator's length) beside the dedicated
chin-shadow checks (face_shadow_chin, face_shadow_neck_3q), and the two builds' chin-shadow and artifact pictures.
    python tools/garments8/neckcheck.py BEFORE AFTER OUT_DIR"""
import json, os, sys
from PIL import Image

a, b, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
rows = []
for name, d in (('before', a), ('after', b)):
    q = json.load(open(os.path.join(d, 'qa', 'qa.json')))
    A = q['artifacts']['ours']['head']
    for v in ('front', 'three_quarter', 'profile', 'back'):
        n = (A.get(v) or {}).get('neck')
        if not n:
            rows.append((name, v, None)); continue
        t = n['terminator']
        rows.append((name, v, dict(area=t.get('area'), shade=t.get('shade'), term_len=t.get('len'),
                                   outline_len=n['outline']['len'])))
    c = q['checks']
    print(name, 'art_terminator_neck', json.dumps(c.get('art_terminator_neck'))[:300])
    print(name, 'face_shadow_chin', (c.get('face_shadow_chin') or {}).get('value'),
          (c.get('face_shadow_chin') or {}).get('per_view'))
    f = c.get('face_shadow_neck_3q') or {}
    print(name, 'face_shadow_neck_3q', f.get('value'), {k: v for k, v in (f.get('per_view') or {}).items()})
for r in rows:
    print('%-7s %-14s %s' % r)
for pic in ('qa_chin_shadow.png', 'qa_artifacts.png'):
    ims = [Image.open(os.path.join(d, 'qa', pic)).convert('RGB') for d in (a, b)]
    W = max(i.width for i in ims)
    o = Image.new('RGB', (W, sum(i.height for i in ims) + 10), 'white')
    y = 0
    for i in ims:
        o.paste(i, (0, y)); y += i.height + 10
    o.save(os.path.join(out, 'both_' + pic))
    print(os.path.join(out, 'both_' + pic), o.size)
