"""charkit: a parametric anime character kit (docs/CHARKIT.md). Import inside Blender with the repo root on sys.path."""
import os as _os

if _os.environ.get('CHARKIT_CLOSURE'):          # the merge gate records what its builds read (charkit/closure.py)
    from . import closure as _closure
    _closure.start()
