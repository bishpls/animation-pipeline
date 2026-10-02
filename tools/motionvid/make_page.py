"""The sample's review page: rom video's own page (romvideo.page, with the ROM suite's grades) plus this round's
measurements: the renderer's parity with the ROM boards (tools/motionvid/parity.py) and the node constraints on
motion1's m1_s2 export (evaluated with tool/motion1's rom.Rig, not without).

    python tools/motionvid/make_page.py      (light: reads charkit/out/motionvid/{sample,base_rom,parity,m1s2_*})
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from PIL import Image, ImageDraw
from charkit import romvideo as RV, reviewpage

O = os.path.join(ROOT, 'charkit', 'out', 'motionvid')
S = os.path.join(O, 'sample')
rep = json.load(open(os.path.join(S, 'video.json')))
rep['out'] = S
pj, _ = RV.page(rep, os.path.join(O, 'base_rom', 'rom.json'))
spec = json.load(open(pj))

# the parity: boards | ours, the rest head light | ours, the posed head light (the face crops)
par = json.load(open(os.path.join(O, 'parity', 'parity.json')))
font = RV._font(16)
figs = []
for pose, az, box in (('squat', 0, (230, 140, 410, 330)), ('head_nod', 0, (230, 120, 410, 310)),
                      ('head_turn', 0, (230, 140, 410, 330)), ('head_turn', 35, (230, 140, 410, 330))):
    im = Image.open(os.path.join(O, 'parity', '%s_%03d.png' % (pose, az)))
    W = im.width // 3
    out = Image.new('RGB', (3 * 300, 320 + 26), (24, 24, 28))
    d = ImageDraw.Draw(out)
    for k, lab in enumerate(('ROM boards', 'ours, rest head light', 'ours, posed head light')):
        c = im.crop((k * W + box[0], box[1], k * W + box[2], box[3])).resize((300, 320), Image.LANCZOS)
        out.paste(c, (k * 300, 26))
        d.text((k * 300 + 6, 4), lab, fill=(240, 240, 240), font=font)
    p = os.path.join(O, 'parity', 'face_%s_%03d.png' % (pose, az))
    out.save(p)
    figs.append(dict(path=p, caption='%s, %s %d deg: the face (crop, x1.7): the boards | ours with the boards\' light | '
                     'ours as shipped' % (pose, RV.VIEW_NAMES[az], az)))
rows = []
for pose, r in par.items():
    for j, az in enumerate((0, 35, 90)):
        a, b = r['boards_vs_ours_rest_light'][j], r['rest_light_vs_head_light'][j]
        rows.append([pose, '%s %d' % (RV.VIEW_NAMES[az], az), '%.1e' % r['deform_max'], a['max'],
                     '%.4f%%' % (100 * a['share_gt8']), r['head_turn_deg'], b['max'], '%.4f%%' % (100 * b['share_gt8'])])
spec['tables'].insert(0, dict(
    title='Parity with the ROM boards (tools/motionvid/parity.py, render2, the sample build)',
    text='Each pose at its hold drawn three ways: the ROM boards\' path (rom.Rig.model_posed and a fresh renderer), ours '
         'with the boards\' head light (the rest head\'s frame), ours as shipped (the posed head\'s frame, as look.js). '
         'deform: the slerped and composed key against the pose\'s solve (max matrix entry). Pixel differences: the max '
         'over RGB (0-255) and the share of pixels differing by more than 8.',
    columns=['pose', 'view', 'deform', 'boards vs ours: max', 'share > 8', 'head turned (deg)',
             'rest vs posed head light: max', 'share > 8'], rows=rows))
spec['figures'].insert(0, dict(
    title='The face under a turned or bowed head', height=346, images=figs,
    text='Ours with the boards\' light matches the boards to 1-2 levels. With the runtime\'s head-space light (look.js '
         'applies the head\'s whole rotation to the face\'s light) a bowed head side-lights the face: the face SDF '
         'reads the light\'s azimuth in the head\'s frame (atan2(x, z)), and a 35 deg nod moves the front view\'s key light '
         'from 30 to 65 deg off the face\'s front (head-frame z 0.66 -> 0.18; the elevation turns into azimuth). The blob '
         'by the nose in the squat and head_nod is that shading, not the rig.'))
spec['figures'].append(dict(
    title='Node constraints (motion1\'s m1_s2 export: 40 constrained nodes, rotation 36, roll 4)', height=None,
    images=[dict(path=os.path.join(O, 'm1s2_compare.png'), caption='top: tool/motionvid alone (each helper moves as its '
                 'humanoid ancestor; the features table says "not evaluated"); bottom: with tool/motion1 merged '
                 '(rom.Rig.nodes.deform each frame, and motion1\'s clavicle rhythm in pose.solve): honoured')],
    text='The constraint path tested on a throwaway merge of tool/motion1 (not in this branch): once motion1 lands, '
         'rom video evaluates the export\'s VRMC_node_constraint nodes every frame with no change here.'))
S_ = spec['summary']
S_['recommended'] = ('Use the video as the day\'s motion check: the shipped rig (%s) posed as a runtime poses it, %d clips '
                     'rest -> pose -> rest, %.0f s at %d fps, %.2f s a frame on the L4 (%.2f s a render; identical poses '
                     'drawn once). Its pictures match the ROM boards\' to 1-2 levels; the one difference is the face\'s '
                     'head-space light, which look.js applies too. For that, B below (yaw only) is the usual practice '
                     'and would remove the bowed-head blob.' % (rep['export'], len(rep['clips']), rep['duration_s'],
                                                              rep['fps'], rep['per_frame_s'], rep['per_render_s']))
S_['asked'] = ['Face light on a bowed head: A) keep the runtime\'s full head-space light (look.js today: a nod or squat '
               'side-lights the face, a shadow blob by the nose), or B) take only the head\'s yaw for the face SDF (the '
               'face lit as at rest under a nod; a small change in toon.wgsl and look.js, a later round)?']
json.dump(spec, open(pj, 'w'), indent=1)
print(reviewpage.make(spec, os.path.join(S, 'page')))
