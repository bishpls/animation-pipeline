"""One option of a face decision (Michael's taste calls: eye flatness, brow) as a picture and its numbers: the head sheet's
front, three-quarter and profile over the build's face boards (85 mm, 1 m, level at the eye line + 0.06 L), cut round
the eyes at one px per L, and a json of the numbers the call turns on (from the build's QA).

    python decision_views.py OUT_BASE BUILD --call eye_flatness --option a --settings '{"forward": null}' [--note TEXT]

writes OUT_BASE.png and OUT_BASE.json (charkit/out/decisions/face/<call>/<option>)."""
import json, os, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jaw_page  # noqa: E402

TOP, BOT, HALF = 0.3, 0.35, 0.5            # L over the eyes, under them, either side
NUMBERS = ('eye_width_three_quarter', 'eye_width_profile', 'eye_width', 'eye_aspect', 'sheet_width', 'sheet_cheek',
           'eye_hollow_L', 'eye_hollow_R', 'cheek_lead_L', 'cheek_lead_R', 'eye_bowl_L', 'eye_bowl_R', 'hair_fringe_low',
           'sheet_profile', 'face_folds')


def main(args):
    base, build = args[0], args[1]
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    from charkit import bundle as bl, manifest, refcheck
    spec = manifest.resolve(json.load(open(os.path.join(jaw_page.ROOT, 'charkit/spec/clawd_body.json'))))
    rgb0, _ = refcheck.without_guides(np.asarray(refcheck._load(spec['ref']['face_sheet']['image']), float))
    _, f, H = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * refcheck.FACE_PPL, -1)
    Bb = bl.load(os.path.join(build, 'bundle'))
    L = float(Bb.assembly['L'])
    w, h = int(2 * HALF * jaw_page.PPL), int((TOP + BOT) * jaw_page.PPL)
    S = Image.new('RGB', (3 * (w + 8), 2 * (h + 8) + 44), (255, 255, 255))
    d = ImageDraw.Draw(S)
    title = '%s  option %s  %s' % (opt('--call'), opt('--option'), opt('--settings', ''))
    d.text((6, 4), title, fill=(0, 0, 0))
    d.text((6, 20), 'top: the head sheet; bottom: the build (%s), face boards, %d px per L, red: the eye line and every 0.1 L'
           % (os.path.basename(build.rstrip('/')), jaw_page.PPL), fill=(80, 80, 80))
    for i, (view, fn) in enumerate(jaw_page.VIEWS):
        for j, im in enumerate((jaw_page.design_crop(rgb0, f, H, view, TOP, BOT, HALF),
                                jaw_page.board_crop(build, fn, L, jaw_page.AZ[view], jaw_page.eye_point(Bb, view), TOP, BOT,
                                                    HALF, float(Bb.assembly['eye_z'])))):
            S.paste(jaw_page.ticks(im, TOP), (i * (w + 8), 40 + j * (h + 8)))
    os.makedirs(os.path.dirname(base), exist_ok=True)
    S.save(base + '.png')
    q = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    q = q.get('checks', q)
    nums = {}
    for k in NUMBERS:
        v = q.get(k)
        if isinstance(v, dict):
            nums[k] = {kk: vv for kk, vv in v.items() if kk in ('value', 'status', 'ours', 'design', 'at')}
        elif v is not None:
            nums[k] = v
    json.dump(dict(call=opt('--call'), option=opt('--option'), settings=json.loads(opt('--settings', 'null')),
                   note=opt('--note'), build=os.path.abspath(build), image=os.path.abspath(base + '.png'), numbers=nums),
              open(base + '.json', 'w'), indent=1)
    print(base + '.png')


if __name__ == '__main__':
    main(sys.argv[1:])
