"""SO BACK: Melee's menu font (the SIS text system) from main.dol. A wrapper over tools/machinima/melee/type/sisfont.py with
SO BACK's paths (the vanilla DOL of its decomp worktree; output ~/games/melee/plates/soback_type/sis/).
    .venv/bin/python projects/so-back/type/sisfont.py [DOL] [OUT_DIR]"""
import importlib.util, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_s = importlib.util.spec_from_file_location('mt_sisfont', os.path.join(ROOT, 'tools/machinima/melee/type/sisfont.py'))
tool = importlib.util.module_from_spec(_s); _s.loader.exec_module(tool)

if __name__ == '__main__':
    a = sys.argv[1:]
    tool.main(a[0] if len(a) > 0 else '~/games/melee/decomp-soback/orig/GALE01/sys/main.dol',
              a[1] if len(a) > 1 else '~/games/melee/plates/soback_type/sis')
