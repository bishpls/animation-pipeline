"""Blender entry for `python -m charkit build` (charkit/cli.py): build a resolved spec's scene, render its boards, save it.
    blender -b --factory-startup --python charkit/build_blender.py -- SPEC.json OUT_DIR BOARDS [--blend]
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from charkit import scene

a = sys.argv[sys.argv.index('--') + 1:]
spec = scene.load(a[0])
out = a[1]
which = [w for w in a[2].split(',') if w] if len(a) > 2 and not a[2].startswith('--') else []
S = scene.build(spec)
if which:
    scene.boards(S, os.path.join(out, 'boards'), which)
if '--blend' in a:
    scene.save(os.path.join(out, spec['name'] + '.blend'))
print('CHARKIT_BUILD_DONE', out)
