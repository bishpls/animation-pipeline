"""charkit.geom's tests (charkit/tests/geom), run as one script, so the merge gate's `python charkit/tests/test_*.py` pass
covers the kernel too. Under pytest the tests are collected from charkit/tests/geom directly; this file holds none."""
import glob, importlib.util, os, sys, traceback

if __name__ == '__main__':
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geom')
    sys.path.insert(0, here)
    failed = 0
    for path in sorted(glob.glob(os.path.join(here, 'test_geom_*.py'))):
        spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in sorted(n for n in dir(mod) if n.startswith('test_')):
            try:
                getattr(mod, name)()
                print('ok', os.path.basename(path), name)
            except Exception:
                failed += 1
                print('FAILED', os.path.basename(path), name)
                traceback.print_exc()
    sys.exit(1 if failed else 0)
