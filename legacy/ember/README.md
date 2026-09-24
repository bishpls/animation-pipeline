# From EMBER (github.com/bishpls/ember, ~/opus-anim-test)

The reusable parts of the three EMBER action shorts, kept for future films.

| file | what's worth reusing |
|---|---|
| `audio.py` | a numpy synth: piano, formant choir, amp-simulated guitars, drums, bass, lead, convolution reverb, sidechain, mastering, and procedural SFX (`make_sfx`: whoosh, slash, impact, click and more). Useful when a film needs an original score or frame-exact sound design. |
| `ep3b/engine.js` | skia-canvas era helpers: a keyframe `Track`, `lagged()` (follow-through without simulation: a damped response over motion history), 2-bone IK, `taper`/`capsule` shape tools, and two-tone cel shading. |
| `ep3b/fx.js` | sakuga FX: triangle fire, ink bursts, smears, speed lines, shockwaves, cel puffs, cracks, muzzle blasts, impact frames. |
| `ep3b/eye.js` | an extreme close-up anime eye: lids, layered iris, striations, highlights, lashes. |
| `ep3b/STORYBOARD.md` | a beat-map storyboard format that worked well: a shot table with beats, the read, and the technique. |

The lessons from those projects are folded into `docs/CRAFT.md`.
