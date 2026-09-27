"""Write rig/fable_room/preview/index.html: a copy of the film's index.html (re-run when it changes) with src/fableroom.js loaded,
and finale's room figure swapped to FABLEROOM.room on this page only. engine/render.mjs always opens <project>/index.html, so the
copy lives in its own folder with <base href> pointing back at the project (every relative URL resolves as in index.html):
    .venv/bin/python projects/tsuzuku/rig/fable_room/preview.py
    node engine/render.mjs projects/tsuzuku/rig/fable_room/preview --loop=fableroom --strip=178.1:181 --audio=projects/tsuzuku/assets/mix.wav --out=...
"""
import os
D = os.path.dirname(os.path.abspath(__file__)); P = os.path.abspath(os.path.join(D, '..', '..'))
s = open(os.path.join(P, 'index.html')).read()
s = s.replace('<head>', '<head>\n<base href="/projects/tsuzuku/">', 1)
if 'src/fableroom.js' not in s:                                        # (index.html loads it now; FABLESTAGE.load loads its drawings)
    s = s.replace('<script src="src/finale.js"></script>', '<script src="src/finale.js"></script>\n<script src="src/fableroom.js"></script>', 1)
# preview only: the finale's room figure routed to FABLEROOM.ending when finale.js passes Clawd's channels (o.P), as it will be
hook = "    if (typeof FABLESTAGE !== 'undefined') await FABLESTAGE.load();"
assert hook in s, 'index.html changed shape: update preview.py'
s = s.replace(hook, hook + "\n    if (typeof FABLEROOM !== 'undefined' && !FABLEROOM.E.meta) await FABLEROOM.load();"
              "\n    if (typeof FABLEROOM !== 'undefined' && !location.search.includes('v1')) { const r0 = FABLESTAGE.room; FABLESTAGE.room = (X, t, T, o = {}) => o.P ? FABLEROOM.ending(X, t, T, o) : r0(X, t, T, o); }", 1)
os.makedirs(os.path.join(D, 'preview'), exist_ok=True)
os.makedirs(os.path.join(D, 'preview'), exist_ok=True)                  # (generated, gitignored: re-run this after index.html changes)
open(os.path.join(D, 'preview', 'index.html'), 'w').write(s)
print('wrote', os.path.join(D, 'preview', 'index.html'))
