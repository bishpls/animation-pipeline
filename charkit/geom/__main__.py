"""charkit.geom's command line (the venv's python):

    python -m charkit.geom report MESH [--no-selfx]                       health as JSON (the trace's field names)
    python -m charkit.geom repair IN OUT [--weld TOL] [--holes N] [--min-part FACES] [--keep-largest K]
    python -m charkit.geom remesh IN OUT --edge L [--iters 4]             isotropic remesh (target edge length, metres)
    python -m charkit.geom decimate IN OUT --faces N
    python -m charkit.geom smooth IN OUT [--taubin N] [--bilateral N]
    python -m charkit.geom voxel IN OUT --h H [--close R] [--open R] [--dilate R] [--erode R] [--blur S] [--solid]
                                                                          remesh through a volume (closed output)
    python -m charkit.geom thicken IN OUT --r R [--h H]                  a sheet to a closed solid R either side
    python -m charkit.geom boolean A B OUT --op union|difference|intersection [--h H] [--volume]
    python -m charkit.geom render IN OUT.png [--az 0,45,90,180] [--res 480] [--normals envelope|geometric]
    python -m charkit.geom extract SPEC.json [--part hair,skirt] [--glb PATH] [--out DIR] [--h H]
                                                                          cut parts from the spec's generated character

Meshes: .glb/.gltf (base-colour texture -> vertex colours; y-up turned z-up), .ply, .obj, .npz. extract writes, per part,
OUT/PART.npz and .ply (V, F, vn = envelope normals, vn_geom), OUT/PART.json (numbers), OUT/PART_sheet.png (renders) and
OUT/PART_silhouettes.png (overlays against the generated part).
"""
import json
import os
import sys

import numpy as np


def _opt(args, k, d=None, cast=str):
    return cast(args[args.index(k) + 1]) if k in args else d


def _load(p):
    from . import io
    return io.load(p)


def _save(m, p):
    from . import io
    io.save(m, p)
    print('wrote', p, m)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] in ('-h', '--help'):
        print(__doc__)
        return
    cmd, r = a[0], a[1:]
    if cmd == 'report':
        from . import repair
        rep = repair.report(_load(r[0]), self_intersections='--no-selfx' not in r)
        print(json.dumps(rep, indent=1))
    elif cmd == 'repair':
        from . import repair
        m = _load(r[0])
        lo, hi = m.bounds()
        m = repair.merge_close(m, _opt(r, '--weld', 1e-6 * float(np.linalg.norm(hi - lo)), float))
        if '--min-part' in r or '--keep-largest' in r:
            m = repair.remove_small_parts(m, min_faces=_opt(r, '--min-part', None, int),
                                          keep_largest=_opt(r, '--keep-largest', None, int))
        m = repair.orient(m)
        m = repair.fill_holes(m, _opt(r, '--holes', 64, int))
        _save(m, r[1])
    elif cmd == 'remesh':
        from . import remesh
        _save(remesh.isotropic(_load(r[0]), _opt(r, '--edge', None, float), iters=_opt(r, '--iters', 4, int)), r[1])
    elif cmd == 'decimate':
        from . import remesh
        _save(remesh.decimate(_load(r[0]), _opt(r, '--faces', None, int)), r[1])
    elif cmd == 'smooth':
        from . import smooth
        m = _load(r[0])
        if '--taubin' in r:
            m = smooth.taubin(m, iters=_opt(r, '--taubin', 10, int))
        if '--bilateral' in r:
            m = smooth.bilateral_normals(m, iters=_opt(r, '--bilateral', 5, int))
        _save(m, r[1])
    elif cmd == 'voxel':
        from . import volume
        m = _load(r[0])
        h = _opt(r, '--h', None, float)
        G = volume.solid(m, h=h, pad=8) if '--solid' in r else volume.occupancy(m, h=h, pad=8)
        S = volume.sdf(m, grid=G, occ=G)
        if '--close' in r:
            S = volume.closing(S, _opt(r, '--close', 0, float))
        if '--open' in r:
            S = volume.opening(S, _opt(r, '--open', 0, float))
        if '--dilate' in r:
            S = volume.dilate(S, _opt(r, '--dilate', 0, float))
        if '--erode' in r:
            S = volume.erode(S, _opt(r, '--erode', 0, float))
        if '--blur' in r:
            S = volume.blur(S, _opt(r, '--blur', 0, float))
        _save(volume.to_mesh(S), r[1])
    elif cmd == 'thicken':
        from . import volume
        m = _load(r[0])
        rad = _opt(r, '--r', None, float)
        _save(volume.to_mesh(volume.thicken(m, rad, h=_opt(r, '--h', rad / 2, float))), r[1])
    elif cmd == 'boolean':
        from . import boolean
        m, how = boolean.boolean(_load(r[0]), _load(r[1]), _opt(r, '--op', 'difference'), h=_opt(r, '--h', None, float),
                                 exact='--volume' not in r)
        print('path', how)
        _save(m, r[2])
    elif cmd == 'render':
        from . import raster, io
        m = _load(r[0])
        az = [float(x) for x in _opt(r, '--az', '0,45,90,180').split(',')]
        fr = raster.Frame.around([m], res=_opt(r, '--res', 480, int), aspect=1.0)
        N = m.vn
        if _opt(r, '--normals') == 'geometric' or N is None:
            from .mesh import vertex_normals
            N = vertex_normals(m.V, m.F)
        col = m.vc if m.vc is not None and '--no-color' not in r else (0.93, 0.55, 0.40)
        ims = [raster.render([(m, dict(color=col, normals=N, shade=_opt(r, '--shade', 'toon')))], x, fr) for x in az]
        print('wrote', raster.save_png(raster.sheet(ims, cols=len(ims)), r[1]))
    elif cmd == 'hull':
        from . import hull
        hull.main(r)
    elif cmd == 'extract':
        extract(r)
    else:
        raise SystemExit(f'unknown command {cmd!r}\n{__doc__}')


def extract(r):
    from . import parts
    spec = r[0]
    which = _opt(r, '--part', 'hair,skirt').split(',')
    name = json.load(open(spec))['name']
    out = _opt(r, '--out', os.path.join(parts.ROOT, 'charkit', 'out', 'geom', name))
    os.makedirs(out, exist_ok=True)
    C = parts.Case.load(spec, glb=_opt(r, '--glb'))
    h = _opt(r, '--h', None, float)
    for p in which:
        if p == 'hair':
            R = parts.hair(C, h=h)
            reg, cc, zmin = parts.hair_region(C), parts.hair_color(C), C.chin_z
        elif p == 'skirt':
            R = parts.skirt(C, h=h, bottom=_opt(r, '--skirt-bottom', None, float))
            reg = cc = zmin = None
        else:
            raise SystemExit(f'unknown part {p!r} (hair, skirt)')
        st = parts.measure(C, R, reg, cc, zmin=zmin, out_dir=out, name=p, ref=R.get('sheet'))
        npz, ply = parts.save_part(R, os.path.join(out, p + '.npz'), meta=dict(align=C.align, measure=st, part=p))
        sheet = parts.render_sheet(C, R, os.path.join(out, p + '_sheet.png'))
        rec = dict(part=p, npz=npz, ply=ply, sheet=sheet, measure=st, stats=R['stats'])
        json.dump(rec, open(os.path.join(out, p + '.json'), 'w'), indent=1, default=parts._jsonable)
        print(json.dumps({k: st[k] for k in ('faces', 'parts', 'open_edges', 'nonmanifold_edges', 'self_intersecting_faces',
                                             'genus', 'silhouette_iou_mean')} | {'part': p}))
        print('wrote', npz, ply, sheet)


if __name__ == '__main__':
    main()
