"""Build a drawn head view of Clawd end to end from a few feature positions (read off a grid of the aligned view).

    ../../../../.venv/bin/python view.py NAME        (NAME in VIEWS below; the aligned image is views/NAME_aligned.png)

Runs: SAM masks (tools/segment.py) -> layers along the drawn lines (tools/layers.py) -> underpaint + export (tools/rigbuild.py)
-> drawn face variants (tools/variants.py, the same prompts as the front view). Output: views/NAME/ (+ variants.json).
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..', '..', '..')
PY, SAMPY = os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'vendor', 'seed-vc', '.venv', 'bin', 'python')
T = lambda n: os.path.join(ROOT, 'tools', n)

VIEWS = {
 # 3/4 views were built by hand before this script; the half turns (about 15 degrees) are in-betweens for snappy turns
 'hleft':  dict(face=[[960, 650], [900, 700], [1030, 620]], neck=[[1070, 810]], bangs=[950, 380], crown=[1070, 250], sideA=[750, 650], sideB=[1350, 650],
                bunL=[820, 200], bunR=[1350, 200], ahoge=[1020, 140], star=[1215, 410], crab=[1120, 410],
                eyeL=[865, 560, 55, 62], eyeR=[1040, 558, 82, 70], mouth=[947, 686, 70, 30], mouthV=[947, 690, 102, 56], faceE=[960, 640, 178, 215],
                split=960, front=[[760, 120], [1350, 120], [1350, 330], [1200, 470], [1150, 560], [840, 560], [780, 450], [740, 330]],
                neckP=[[860, 780], [950, 775], [1040, 740], [1120, 690], [1200, 690], [1200, 1000], [860, 1000]]),
 'hright': dict(face=[[1140, 650], [1210, 700], [1080, 620]], neck=[[1110, 810]], bangs=[1080, 380], crown=[1030, 250], sideA=[780, 650], sideB=[1380, 650],
                bunL=[800, 190], bunR=[1340, 190], ahoge=[1130, 140], star=[1380, 410], crab=[1310, 410],
                eyeL=[1065, 560, 82, 70], eyeR=[1255, 560, 55, 62], mouth=[1165, 686, 70, 30], mouthV=[1165, 690, 102, 56], faceE=[1140, 640, 178, 215],
                split=1150, front=[[800, 120], [1400, 120], [1420, 330], [1380, 450], [1300, 560], [1000, 560], [960, 470], [800, 330]],
                neckP=[[950, 700], [1010, 700], [1080, 740], [1160, 775], [1260, 780], [1260, 1000], [950, 1000]]),
}


def main(name):
    c = VIEWS[name]; os.chdir(HERE); V = f'views/{name}'
    parts = {'hair': {'pos': [c['bangs'], c['crown'], c['sideA'], c['sideB']], 'neg': [c['face'][0], c['bunL'], c['bunR'], c['star']]},
             'bun_L': {'pos': [c['bunL']]}, 'bun_R': {'pos': [c['bunR']]},
             'ahoge': {'pos': [c['ahoge']], 'box': [c['ahoge'][0] - 90, c['ahoge'][1] - 90, c['ahoge'][0] + 90, c['ahoge'][1] + 90]},
             'pin_star': {'pos': [c['star']]}, 'pin_crab': {'pos': [c['crab']]},
             'face': {'pos': c['face'], 'neg': [c['bangs'], c['neck'][0]]}, 'neck': {'pos': c['neck'], 'neg': [c['face'][0], [1065, 1000]]},
             'body': {'pos': [[1065, 1020], [900, 880], [1230, 880], [760, 1050], [1370, 1050], [1065, 1200]]}}
    json.dump(parts, open(f'views/parts_{name}.json', 'w'), indent=1)
    lay = {'order': ['pin_star', 'pin_crab', 'hair_front', 'hair_side_L', 'hair_side_R', 'eye_L', 'eye_R', 'mouth', 'face', 'ahoge', 'bun_L', 'bun_R', 'neck', 'yoke', 'body'],
           'split': {'hair': [['hair_front', c['front']], ['hair_side_L', [[0, 0], [c['split'], 0], [c['split'], 3840], [0, 3840]]],
                              ['hair_side_R', [[c['split'], 0], [2160, 0], [2160, 3840], [c['split'], 3840]]]]},
           'colour': {'pin_star': [[170, 130, 0], [255, 255, 170], 'hair_side_R']},
           'claim': {'face': {'grow': 14, 'from': ['neck', 'body']}, 'eye_L': {'ellipse': c['eyeL'], 'from': ['face']}, 'eye_R': {'ellipse': c['eyeR'], 'from': ['face']},
                     'mouth': {'ellipse': c['mouth'], 'from': ['face']}, 'neck': {'poly': c['neckP'], 'from': ['face']},
                     'yoke': {'poly': [[740, 650], [1400, 650], [1400, 965], [1180, 945], [1065, 935], [950, 945], [740, 965]], 'from': ['body', 'neck']}},
           'line_lum': 80, 'line_grow': 2, 'line_r': 9, 'force': {}}
    json.dump(lay, open(f'views/layers_{name}.json', 'w'), indent=1)
    f = c['faceE']
    build = {'under': {'face': {'hull': ['eye_L', 'eye_R', 'mouth'], 'ellipse': f, 'clip': [f[0] - 230, 380, f[0] + 230, 800],
                                'flat': [c['mouth'][0] - 50, c['mouth'][1] + 12, c['mouth'][0] + 50, c['mouth'][1] + 40], 'flat_zone': {'hull': ['eye_L', 'eye_R', 'mouth']}},
                       'hair_front': {'hull': ['pin_star', 'pin_crab'], 'clip': [c['crab'][0] - 120, 300, c['star'][0] + 140, 560]},
                       'hair_side_R': {'hull': ['pin_star', 'pin_crab'], 'clip': [c['crab'][0] - 120, 300, c['star'][0] + 140, 560]}},
             'plates': {'hair_back': {'from': ['hair_front', 'hair_side_L', 'hair_side_R', 'face'], 'grow': -14, 'colour': 'shadow', 'behind': 'yoke'}},
             'feather': {'eye_L': 10, 'eye_R': 10, 'mouth': 10, 'yoke': {'px': 30, 'from': ['body']}}, 'bleed': 3, 'aa': .8, 'drop': ['body']}
    json.dump(build, open(f'views/build_{name}.json', 'w'), indent=1)
    F = json.load(open('variants_F.json'))
    F.update(image=f'views/{name}_aligned.png', crop=[560, 0, 1056], out=V, patches={'eye_L': c['eyeL'], 'eye_R': c['eyeR'], 'mouth': c['mouthV']})
    json.dump(F, open(f'variants_{name}.json', 'w'), indent=1)
    run = lambda *a: subprocess.run(list(a), check=True)
    run(SAMPY, T('segment.py'), f'views/{name}_aligned.png', f'views/parts_{name}.json', f'views/seg_{name}')
    run(PY, T('layers.py'), f'views/{name}_aligned.png', f'views/layers_{name}.json', f'views/seg_{name}', f'views/layers_{name}')
    run(PY, T('rigbuild.py'), f'views/layers_{name}', f'views/build_{name}.json', V)
    run(PY, T('variants.py'), f'variants_{name}.json')


if __name__ == '__main__':
    main(sys.argv[1])
