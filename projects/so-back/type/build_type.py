"""SO BACK's type from Melee's own disc (the game's word graphics, its menu font, the HUD digits and tags, the character
name textures) for the engine's meleetype.js. A wrapper over tools/machinima/melee/type/build_type.py with SO BACK's paths:
reads ~/games/melee/work/soback/type/dump/ and writes ~/games/melee/plates/soback_type/ (game-derived: never in the repo).
    .venv/bin/python projects/so-back/type/dumpall.py IfAll.usd GmGover.dat GmRegClr.dat IfComSn.usd GmPause.usd GmRst.usd
    .venv/bin/python projects/so-back/type/sisfont.py
    .venv/bin/python projects/so-back/type/build_type.py"""
import importlib.util, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_s = importlib.util.spec_from_file_location('mt_build_type', os.path.join(ROOT, 'tools/machinima/melee/type/build_type.py'))
tool = importlib.util.module_from_spec(_s); _s.loader.exec_module(tool)

if __name__ == '__main__':
    tool.main('~/games/melee/work/soback/type/dump', '~/games/melee/plates/soback_type')
