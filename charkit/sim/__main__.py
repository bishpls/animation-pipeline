"""python -m charkit.sim rest BUILD [--out DIR] [--pieces a,b] [--variants v,w] [--seconds S]
python -m charkit.sim motion BUILD [--out DIR] [--poses kick,...]"""
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
    print(__doc__); return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
