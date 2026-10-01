"""python -m charkit.sim rest BUILD [--out DIR] [--pieces a,b] [--variants v,w] [--seconds S]
python -m charkit.sim motion BUILD [--out DIR] [--poses kick,...]
python -m charkit.sim tune BUILD [--out DIR] [--poses kick,squat] [--root hips|skin] [--stiffness 4,8,16,..]
python -m charkit.sim review BUILD REST_DIR|- MOTION_DIR|- OUT_DIR [INTRO.html]
python -m charkit.sim bake BUILD --clip kick [--out DIR] [--method M] [--pc2] [--replay [--blender PATH]]
python -m charkit.sim waist BUILD [--out DIR]        the waistband's weights at motion QA's poses (charkit.sim.waist)
python -m charkit.sim qa BUILD [--method M]           motion QA (charkit.sim.motionqa) on a build, printed"""
import sys


def main(a):
    if not a or a[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[0] == 'rest':
        from . import drape
        vs = opt('--variants')
        V = {k: drape.REST_VARIANTS[k] for k in vs.split(',')} if vs else None
        drape.pilot_rest(a[1], opt('--out', a[1] + '/sim_rest'), pieces=tuple(opt('--pieces', 'overskirt_panel_L,'
                         'overskirt_panel_R').split(',')), variants=V, seconds=float(opt('--seconds', 5.0)))
        return 0
    if a[0] == 'motion':
        from . import motion
        return motion.main(a[1:])
    if a[0] == 'tune':
        from . import motion
        g = None
        if opt('--stiffness'):
            g = dict(stiffness=tuple(float(x) for x in opt('--stiffness').split(',')), gravity=(0.0, 0.05, 0.15, 0.3),
                     drag=(0.3, 0.5, 0.7, 0.9))
        motion.tune_springs(a[1], opt('--out', a[1] + '/sim_tune'), poses=tuple(opt('--poses', 'kick,squat').split(',')),
                            grid=g, root=opt('--root', 'hips'))
        return 0
    if a[0] == 'bake':
        from . import bake
        return bake.main(a[1:])
    if a[0] == 'waist':
        from . import waist
        waist.run(a[1], opt('--out', a[1] + '/sim_waist'))
        return 0
    if a[0] == 'qa':
        import json as _j
        from .. import bundle as bl
        from . import motionqa
        B = bl.load(a[1] + '/bundle')
        gm = motionqa.settings(B)
        if opt('--method'):
            gm['method'] = opt('--method')
        T, C = motionqa.measure(B, gm, log=print)
        print(_j.dumps(dict(table=T, checks=C), indent=1))
        return 0
    if a[0] == 'review':
        from . import review
        return review.main(a[1:])
    print(__doc__); return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
