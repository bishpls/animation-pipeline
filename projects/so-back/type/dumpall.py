"""SO BACK: dump every model's textures from Melee files (datkit mdump) to find the game's own text. A wrapper over
tools/machinima/melee/type/dumpall.py with SO BACK's paths (dumps under ~/games/melee/work/soback/type/dump/, never in the repo).
    .venv/bin/python projects/so-back/type/dumpall.py FILE..."""
import importlib.util, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_s = importlib.util.spec_from_file_location('mt_dumpall', os.path.join(ROOT, 'tools/machinima/melee/type/dumpall.py'))
tool = importlib.util.module_from_spec(_s); _s.loader.exec_module(tool)
W = os.path.expanduser('~/games/melee/work/soback/type')

if __name__ == '__main__':
    tool.run(sys.argv[1:], os.path.join(W, 'dump'), '~/games/melee/disc-soback/files', os.path.join(W, 'dk'))
