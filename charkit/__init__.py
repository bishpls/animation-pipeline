"""charkit: a parametric anime character kit (docs/CHARKIT.md). Import inside Blender with the repo root on sys.path."""
import os as _os

if _os.environ.get('CHARKIT_CLOSURE'):          # the merge gate records what its builds read (charkit/closure.py)
    from . import closure as _closure
    _closure.start()

# a box copy hard-links its synced files read-only from the blob cache: a write to one gets a file of its own first
# (charkit/cow.py; only where this package itself is such a link, CHARKIT_COW=0 off)
from . import cow as _cow
_cow.install()
