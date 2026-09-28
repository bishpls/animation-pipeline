"""SO BACK's plates from raw capture folders: a thin wrapper over tools/machinima/prep_plates.py (its raw mode; the tool's
slate mode is what the capture lanes' delivery used). `one` is re-exported for director/drop_run.py.
    .venv/bin/python projects/so-back/prep_plates.py OUT_DIR --stage CAPTURE [--mode aspect]
    .venv/bin/python projects/so-back/prep_plates.py OUT_DIR --black CAP_B --grey CAP_G [--mode aspect]"""
import argparse, importlib.util, os, sys
from concurrent.futures import ProcessPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location('machinima_prep_plates', os.path.join(ROOT, 'tools', 'machinima', 'prep_plates.py'))
_tool = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_tool)
frames = _tool.frames


def one(job):                            # defined here (not aliased) so worker processes can unpickle it as prep_plates.one
    return _tool.one(job)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--stage'); ap.add_argument('--black'); ap.add_argument('--grey')
    ap.add_argument('--mode', default='aspect'); ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    if a.stage:
        fs = frames(a.stage); jobs = [(i + 1, a.out, a.mode, os.path.join(a.stage, f), None, None) for i, f in enumerate(fs)]
    else:
        fb, fg = frames(a.black), frames(a.grey)
        if len(fb) != len(fg): sys.exit(f'pass lengths differ: {len(fb)} vs {len(fg)}')
        jobs = [(i + 1, a.out, a.mode, None, os.path.join(a.black, x), os.path.join(a.grey, y)) for i, (x, y) in enumerate(zip(fb, fg))]
    with ProcessPoolExecutor(a.workers) as ex: list(ex.map(one, jobs, chunksize=4))
    print(f'{len(jobs)} frames -> {a.out}')
