# Rigging characters: the method

How characters are built and made to move in this repo. `docs/CRAFT.md` §11–13 hold the short rules and the lessons;
`projects/tsuzuku/RIGGING.md` is the worked example (Clawd's mesh rig and Fable's finale rig, with their interfaces and numbers).
Tools are indexed in `docs/TOOLS.md`.

## 1. Pick the kind of character by register
| kind | reads as | runtime | build | example |
|---|---|---|---|---|
| code puppet | bold, simple, beat-locked | shapes drawn per frame (`engine/pop.js` `shp`) | none: code against a style-target sheet | HELLO, WORLD!'s chibi and troupe (`projects/hello-world/src/chars.js`) |
| strip-warped illustration | a still that breathes | `rig()` in `engine/pop.js` | `tools/chroma.py` | HELLO, WORLD!'s sakuga keys (sway 0 on close-ups: strip seams show) |
| cut-paper puppet | shadow theatre, snap and hold | `engine/puppet.js` (parts at rivets) | a trace-and-cut builder (`projects/tsuzuku/rig/fable/cut.py`) | TSUZUKU's paper world |
| drawn pose set | acting on twos, clean poses, no tweens | whole drawings (or base + patches) swapped on twos | pose edits registered and cut (`tools/rigkit.py`) | TSUZUKU's seated and room Fable (`src/fableseat.js`, `src/fableroom.js`) |
| mesh rig | continuous motion: dance | `engine/rig.js` (WebGL2 meshes) + `engine/moves.js` | `segment.py` → `layers.py` → `rigbuild.py` → `variants.py` | TSUZUKU's Clawd |

A mesh rig costs days; a pose set costs hours per scene. Choose the cheapest kind that can carry the performance the scene needs, and
let each character keep its own timing (Clawd moves on ones with springs; Fable on twos with none).

## 2. The base drawing (every illustrated kind)
- **GPT Image** (`tools/gptimage.py`; it beat Gemini on an A/B for rig art): ONE full figure on flat `#00FF00`, "NOTHING else in the
  frame", no green on the character, at the size you'll rig from (Clawd: 2160×3840). Arms slightly away from the body: a rig can close
  a gap, never open one it can't see.
- Key it at full canvas (`tools/chroma.py --full`, or `from chroma import key`). Everything later registers to this canvas.
- Never pass a whole model sheet as the only reference (half the results come back as model sheets): crop one figure.

## 3. Edits of the base: companions, poses, variants
Every other drawing is a GPT Image **edit of the base** that changes one thing (an arm raised, the hair tied back, a hand shape).
```python
sys.path.insert(0, 'tools'); from chroma import key; from rigkit import register, residual, colour_match, feather, blend
base = key('src/base.png'); fit = (base[..., 3] > 200) & ~changed_zone_dilated      # fit only on what the edit must not change
al, warp = register(key('src/poses/wave.png'), base, fit)                            # ECC, coarse to fine
print(residual(al, base, fit))                                                       # high = the edit moved something: redo it
al = colour_match(al, base, fit & (al[..., 3] > 200))
patch = blend(base, al, feather(changed_mask, 9))                                    # the pose: base with the changed region laid in
```
- **The residual is the check.** Register on structure, never on hatching (ECC locked a false 640 px offset once); for a new pose,
  align on hand-measured landmarks.
- **Cut the patch from the difference** (thresholded, opened, hole-filled, largest components, dilated, feathered), inside a zone
  polygon per pose. Paste masks cover the union of old and new shapes, outlines included, or the old one ghosts.
- **A new pose is a new drawing, not a warp** (sliding a region to fake a raise left a hole). Edit once and paste many where the
  object doesn't move; for small drawn detail, edit a crop and register it back (`tools/variants.py`).
- Props drawn once, underneath, never jitter between drawings; take each drawing's own copy of the prop out.
- Keep every source drawing and edit (`src/`, `_edits/`): they are the rig's record and let a build be re-run exactly.

## 4. The mesh rig (Clawd), in order
1. **Part masks vote, the lines decide.** `segment.py` (SAM) gives rough masks; `layers.py` cuts along the drawing's own lines into
   flat-colour cells, each cell whole to the part whose mask covers most of it. `order`, `split` and `force` fix it; review
   `_labels.png` every time.
2. **Hidden areas get real drawing.** `rigbuild.py` underpaints what motion can reveal: companion drawings first (registered with
   `register.py`, cut by the same cells), then cross-fills from other views and plates, and invented fills last, each invented pixel
   exported (`<layer>.inv.png`) so tests see it. `outer_margin` keeps invented paint off the silhouette ("paint outside the lines").
3. **The rest pose reproduces the illustration exactly** (`restcheck.py`).
4. **Drawn views, not warped faces:** each head view is a whole upper-body drawing swapped as a unit; joins only where drawings agree.
5. **Variants** (`variants.py`): mouths, eyes and hands per view, registered crops; check each at 100% beside its siblings.
6. **Articulation** (`engine/rig.js`): measured coupling (Live2D's samples, `docs/research/README.md` §4): head controls never move
   the collar; the neck follows a fraction of the head; the body follows the head through `RIG.perform`; rigid facial features (the
   "bent paper face" came from warping them); an elbow that hinges past 120°; per-frame arm depth order; a heel pivot for weight
   shifts; springs stepped from a fixed pre-roll so every frame is a pure function of t.

## 5. The drawn pose set (Fable), in order
1. Draw the set as edits of one base (§3); build with a script per scene (`projects/tsuzuku/rig/fable_seated/build.py`: `zones.json`
   polygons per pose, `meta.json` with sizes, pivots, pose files and book quads).
2. The runtime samples a cue sheet on twos, snaps between drawings, and adds only what paper allows: a nod or tilt warped in strips,
   a seated weight shift. A layer that must move on its own (a ribbon) is cut to its own file.
3. Feet that walk are planted: find each drawing's pivot point on the sole (`rig/fable_room/feet.py`) and place the next drawing on it.
4. Anything printed onto the drawing (her book mirrors the screen) gets a mask and quad per pose from the build, drawn before the warps.

## 6. Test the whole range, every frame
- `src/rom.js`: a matrix of every control alone and combined, whips, tilts inside every view, every view switch both ways.
  `tools/romrun.py projects/<film>` renders its ID pass, checks each frame for holes and exposed invented pixels, and sheets the
  worst; `romheat.py` maps where. About 3 minutes for 4,500 frames.
- Magenta test loops (`LOOPS.<name>mag`) with `holes.py`; `drawings.py` for every drawing of every move.
- Stills lie about motion: strips of every frame of a move and 100% crops before a clip. Fix at the root (the build or the runtime),
  never with a per-frame patch.

## 7. Porting motion between characters
Channel units belong to the source rig: translations in its base px, angles from its rest pose. Scale translations by leg length
and hip height, offset arm angles by the new rig's rest, and let costume carry what legs can't (the hakama's hem carried Fable's
steps). Check the height relation against the character docs before framing them together.
