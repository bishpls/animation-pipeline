"""Blender entry for `python -m charkit build` (charkit/cli.py): build a resolved spec's scene, render its boards, save it.
    blender -b --factory-startup --python charkit/build_blender.py -- SPEC.json OUT_DIR BOARDS [--blend] [--qa] [--vrm]
                                                                      [--cache on|off|refresh|verify]
The stages go through the build cache (charkit/cache.py), and so do the boards, the QA and the VRM, keyed on the whole
scene; --cache off builds without it. A restore that doesn't reproduce its stage starts the build over with every step
run and stored anew. The persistent worker (charkit/worker.py) calls main() once per job in a live Blender.
"""
import os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main(a, worker=False):
    import json
    from charkit import cache, scene, trace
    spec = scene.load(a[0])
    out = a[1]
    which = [w for w in a[2].split(',') if w] if len(a) > 2 and not a[2].startswith('--') else []
    mode = a[a.index('--cache') + 1] if '--cache' in a else 'on'
    for attempt in range(2):
        C = None if mode == 'off' else cache.Cache(mode, spec['name'], out)
        trace.begin(os.path.join(out, 'trace.jsonl'), spec={k: v for k, v in spec.items() if k != '_dir'}, spec_path=a[0],
                    boards=which, cache=mode, worker=worker)
        try:
            S = scene.build(spec, cache=C)
            break
        except cache.RestoreError as e:
            print('CHARKIT_CACHE_RESTORE_FAILED', e)
            if getattr(e, 'entry', None):
                shutil.rmtree(e.entry, ignore_errors=True)
            if attempt:
                raise
            scene.reset()
            spec, mode = scene.load(a[0]), 'refresh'

    def product(name, run, fns, opts=None):
        if C is None:
            run()
        else:
            C.product(name, run, fns, opts, modules=('charkit.build_blender',))
    if C is not None:
        C.spec = S.spec
    if which:
        product('boards', lambda: scene.boards(S, os.path.join(out, 'boards'), which), [scene.boards], opts=which)
    if '--qa' in a:
        from charkit import qa3d
        ref = spec.get('ref', {}).get('image') if isinstance(spec.get('ref'), dict) else None
        if ref and not os.path.isabs(ref):
            ref = os.path.join(ROOT, ref)

        def qa():
            with trace.span('qa'):
                R = qa3d.run(S, os.path.join(out, 'qa'), ref)
            trace.event('qa', checks={k: (v.get('value'), v['status']) for k, v in R['checks'].items() if k != 'mesh'},
                        summary=R['summary'])
            print('CHARKIT_QA', json.dumps({k: (v.get('value'), v['status']) for k, v in R['checks'].items() if k != 'mesh'}))
            print('CHARKIT_QA_SUMMARY', R['summary'])
        product('qa', qa, [qa3d.run], opts=[os.path.relpath(ref, ROOT) if ref else None])
    if '--vrm' in a:
        from charkit import gltf
        path = os.path.join(out, spec['name'] + '.vrm')

        def vrm():
            with trace.span('export', path=os.path.basename(path)) as sp:
                gltf.export_scene(S, path, meta={'name': spec['name'].capitalize()})
                c = gltf.check(path)
                sp.update({k: c.get(k) for k in ('bytes', 'triangles', 'errors')})
            print('CHARKIT_GLTF', json.dumps({k: c.get(k) for k in ('bytes', 'triangles', 'errors', 'look_kinds')},
                                             default=str))
        product('vrm', vrm, [gltf.export_scene, gltf.check], opts=[os.path.basename(path)])
    if '--blend' in a:
        with trace.span('save'):
            scene.save(os.path.join(out, spec['name'] + '.blend'))
    if C is not None:
        C.finish()
        print('CHARKIT_CACHE', trace.cache_summary(trace.read(os.path.join(out, 'trace.jsonl'))))
        for name, bad in C.stale:
            print('CHARKIT_CACHE_STALE_SUMMARY', name, '; '.join(bad[:4]))
    trace.end()
    print('CHARKIT_BUILD_DONE', out)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1:])
