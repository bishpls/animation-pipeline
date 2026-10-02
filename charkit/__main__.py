import json, os

from .cli import main

# CHARKIT_RAN_OUT=FILE (a produced reference's producer, charkit.manifest): the code this command runs is recorded there
# (charkit.cache.ran), so the produced cache keeps it with the entry and a restore checks it
_ran_out = os.environ.pop('CHARKIT_RAN_OUT', None)
if not _ran_out:
    main()
else:
    from . import cache
    _rec = {'<unrecorded>': 'the command did not start'}
    try:
        with cache.ran() as _rec:                   # (its exit fills the record, on a return and a SystemExit alike)
            main()
    finally:
        with open(_ran_out, 'w') as f:
            json.dump(_rec, f)
