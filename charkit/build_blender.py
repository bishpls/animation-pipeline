"""Blender entry for `python -m charkit build` (charkit/cli.py): build a resolved spec's scene, render its boards, save it.
    blender -b --factory-startup --python charkit/build_blender.py -- SPEC.json OUT_DIR BOARDS [--blend] [--qa] [--vrm]
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from charkit import scene, trace

a = sys.argv[sys.argv.index('--') + 1:]
spec = scene.load(a[0])
out = a[1]
which = [w for w in a[2].split(',') if w] if len(a) > 2 and not a[2].startswith('--') else []
trace.begin(os.path.join(out, 'trace.jsonl'), spec={k: v for k, v in spec.items() if k != '_dir'}, spec_path=a[0],
            boards=which)
S = scene.build(spec)
if which:
    scene.boards(S, os.path.join(out, 'boards'), which)
if '--qa' in a:
    import json
    from charkit import qa3d
    ref = spec.get('ref', {}).get('image') if isinstance(spec.get('ref'), dict) else None
    if ref and not os.path.isabs(ref):
        ref = os.path.join(ROOT, ref)
    with trace.span('qa'):
        R = qa3d.run(S, os.path.join(out, 'qa'), ref)
    trace.event('qa', checks={k: (v.get('value'), v['status']) for k, v in R['checks'].items() if k != 'mesh'},
                summary=R['summary'])
    print('CHARKIT_QA', json.dumps({k: (v.get('value'), v['status']) for k, v in R['checks'].items() if k != 'mesh'}))
    print('CHARKIT_QA_SUMMARY', R['summary'])
if '--vrm' in a:
    import json
    from charkit import gltf
    path = os.path.join(out, spec['name'] + '.vrm')
    with trace.span('export', path=os.path.basename(path)) as sp:
        gltf.export_scene(S, path, meta={'name': spec['name'].capitalize()})
        c = gltf.check(path)
        sp.update({k: c.get(k) for k in ('bytes', 'triangles', 'errors')})
    print('CHARKIT_GLTF', json.dumps({k: c.get(k) for k in ('bytes', 'triangles', 'errors', 'look_kinds')}, default=str))
if '--blend' in a:
    scene.save(os.path.join(out, spec['name'] + '.blend'))
trace.end()
print('CHARKIT_BUILD_DONE', out)
