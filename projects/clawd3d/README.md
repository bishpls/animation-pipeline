# clawd3d: TSUZUKU's Clawd as a 3D character (phase 1 of docs/PIPELINE_3D.md)

The first character and the first motion through the new 3D pipeline: Clawd, TSUZUKU's idol, built by script in headless
Blender 5.2, aimed at a HoYoverse-style cel look, driven by 3D mocap that GEM-X tracked from the film's own directed dance
references. The test shot is bars 58–66 of つづく: the lead-in and the hook.

## The character (`build/`)

| file | what |
|---|---|
| `clawd.py` | the build: measured off the 2D rig's base drawing (a front orthographic render sits on it: `--views` writes `overlay.png`), a VRM 1.0 humanoid armature (hips … head, arms, legs, 15 finger bones a hand), body, hands, clothes (pleated A-line skirt with the pixel-staircase hem, dark underskirt with stepped tails, puff sleeves, sailor collar, bow, cuffs), head, face and hair |
| `head.py` | the anime head: cross-sections from the drawn jaw contour, a flat superellipse face, a small nose; face shading by an SDF threshold map (the Genshin method: the light's angle to the head picks a designed shadow shape, with a nose shadow and a lit cheek triangle), blush |
| `faces.py` | the face is the drawing's: the rig's eye states (open, half, closed, happy) and 15 mouth shapes cut into decals, swapped like the 2D rig's variants |
| `hair.py` | a hair volume fitted to the drawn hair silhouette; thick lens-section clumps from the crown in two layers, in waves, the tips curling out; bangs; face-framing locks; shading with the volume's smooth normals (clean anime shadow shapes), a three-tone ramp and an angel-ring highlight |
| `kit.py` | the reusable kit: three-tone cel material (emission, art-directed light vector: no render noise), inverted-hull outlines in colour, rim tint, mesh and render helpers, a VRM armature from a joint table |
| `motion.py` | posing and retargeting in armature space: `solve`/`apply`, calibration in the source's rest pose (aim + a twist reference for the hands), `Sampler`, anchor time-warps, `bake`, `floor_lock` (planted feet on the floor from GEM-X's contacts) |
| `soma_map.py` | SOMA 77 (GEM-X, Kimodo, BONES-SEED) to VRM humanoid, fingers included |
| `stage.py`, `post.py` | a small idol stage (all emission) and the post (bloom, black lift, vignette) |
| `posetest.py`, `retarget_test.py`, `preview.py` | range-of-motion poses, a clip retargeted beside its source video, review boards |

## The motion (`refs/mocap/`, `tools/mocap3d/`)

TSUZUKU's 13 directed Seedance references (one dancer, locked camera, 5 s each) were tracked by NVIDIA GEM-X on the GPU box
(`infra/gcp/`) into canonical clips: SOMA 77 joints, a metric root, foot contacts (`tools/mocap3d/soma_clip.py` documents the
format; `gemx_remote.sh` runs a batch). The shot time-warps each phrase onto the song by the structural anchors the 2D film
used (`~/animation-pipeline/projects/tsuzuku/refs/mocap/phrases.json`), blends the seam, and locks planted feet to the floor.

## Render the test

```bash
~/animation-pipeline/.venv/bin/python projects/clawd3d/build/faces.py          # decals from the 2D rig
~/animation-pipeline/.venv/bin/python projects/clawd3d/build/head.py --maps    # the face's SDF shadow map and blush
blender -b --factory-startup --python projects/clawd3d/build/clawd.py -- --views projects/clawd3d/out/views   # model boards
blender -b --factory-startup --python projects/clawd3d/shots/dance_test.py -- projects/clawd3d/out/dance_test
zsh projects/clawd3d/shots/encode.sh projects/clawd3d/out/dance_test           # post, the song under it, mp4
```

## Not yet (the next passes toward the HoYoverse bar)

Clothing detail (skirt thickness and real pleats, the jacket as its own cloth, bow folds, boot soles), secondary motion (hair,
skirt, bow, buns on springs), coloured variable-width outlines and inner lines, keyed hand shapes and accents over the
mocap (MOTION.md's layers), the physics fixer, and the camera conte.
