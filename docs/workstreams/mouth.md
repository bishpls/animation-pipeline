# Workstream: the mouth and the expressions (`tool/mouth`)

A quality and detail pass on the mouth keys, and more expressions (the template library is additive). Round 1 of the
eye and mouth engine is `docs/workstreams/eyes.md`; this round owns the mouth and the expression keys (`charkit/mouth.py`,
`brows.py`, the lid shapes in `eyes.expressions`, `scene.PRESETS`, `exprqa`), not the iris, pupil or sclera
(`tool/eyes2`) or the face's shape below the mouth (`tool/face`).

## State: PAUSED 2026-09-29 (coordinator: usage limit), mid goal 1. Resume from "Next steps" below.

No box jobs running. Local outputs (gitignored, in this worktree):
- `charkit/out/base_mh`: the MakeHuman baseline build (`clawd.json`, pipeline-3d code), bundle and QA.
- `charkit/out/mouthlab/head_mh.pkl.gz`, `head_bp.pkl.gz`: the placed heads (MakeHuman; authored, dumped on the box
  from `charkit/out/base_bp/clawd.spec.json`). The box copy is `/srv/work/animation-pipeline-mouth/charkit/out/`.
- `charkit/out/mouthlab/bp_before/`, `mh/`: the lab's "before" (pipeline-3d's mouth code) on each head; `bp_2b/`: the
  current state (new shapes, teeth, tongue, lower line).

- Worktree `~/animation-pipeline-mouth`, branch `tool/mouth` from `pipeline-3d` (`6ca18da`).
- Baselines on the build box: `charkit/out/base_mh` (`clawd.json`, the MakeHuman base) built; `charkit/out/base_bp`
  (`clawd_body_pieces.json`, the authored head and body) **fails at pipeline-3d's head** in `garments.sleeve_hull`
  (`loft.field`: "no row of the piece is measured on 15% of its circle") with a freshly built hull (hash `ef24bd48`,
  the same as `tool/default-spec`'s on the box, whose `eq_default` build stops at the same stage). Not this workstream's
  code: reported to the integrator. The authored head is measured through the lab's head dump instead (below).

## Measurement

**Where the design draws the expressions.** The model sheet `idol_D` (the source design) draws four expression heads
under its figures: a laugh (arched shut eyes, a wide open D mouth with upper teeth), an angry head (knit brows, a small
frown), a flustered one (shrunken irises, a blush, a wavy open mouth) and a yawn (shut eyes, a tall O). Its front figure
smiles with a closed mouth. No generated sheet draws expressions (Michael, 2026-09-28: standardise the mouths in the
template, no generated reference). The manifest's authority for `expressions` is null, and `idol_D` is the source
design, graded against nothing. So:
- the build's QA now measures the sheet's heads against the library again (`expr_*`), from `idol_D`
  (`qa3d.Design.expression_sheet`: the design sheet's heads when it draws any, else the source sheet's). The body sheet
  (`body_turnaround`) draws none, so since tool/refs these were one `expr` SKIPPED. They read INFO
  (`checks.authorize`: expressions have no authority), their grades kept as `graded_as`;
- the template's own intent grades the combined expressions: `exprqa.TARGETS` (below).

**The lab: `python -m charkit mouth`** (`charkit/mouthlab.py`). Per mouth key: folds (`qa3d.face_folds`), cover
(`qa3d.mouth_cover`), the drawn shape as `exprqa` measures a drawing (width, opening, area, fill, corner lift, wave,
skew) and what the opening shows: teeth and tongue (shares of it), the line along its top and bottom edges. Per combined
expression: its measures against `exprqa.TARGETS`. The sheet's heads matched to the library. A page with the contact
sheet: the build's face boards (the preset camera) beside the sheet's heads at one scale.
- `python -m charkit mouth BUILD [--boards DIR] [--against OTHER]`: on a build's bundle.
- `python -m charkit mouth --dump SPEC --out HEAD.pkl.gz` (on the box: `charkit remote run mouth --dump ...`): the
  placed head (`character.geometry`: the body, the head, the eyes' margins) pickled, about 30 s.
- `python -m charkit mouth --head HEAD.pkl.gz [--set JSON]`: the features re-keyed over it with this checkout's code
  (`character.features`) and measured, 3-4 s. The loop for every change below. Bit-identical to a build's bundle (same
  per-key numbers as `charkit/out/base_mh`'s).

`character.assemble` is now `features(geometry(spec))` (bit-identical: the assembly's hash is unchanged).

New measures in `exprqa.mouth`: `teeth`, `tongue` (a new class, 13: ours only; a drawing's tongue is its inside's red),
`line_top`, `line_bottom`, `line_closed`, `skew`; the brows' `z` over the given eye line (a closed or narrowed eye's
found centre moves; the line doesn't).

## Numbers so far

Before (pipeline-3d's mouth code; the lab on each head; folds, cover, shape against the drawn heads, INFO):

| key | MakeHuman folds / cover | authored folds / cover / chin drop (L) |
|---|---|---|
| laugh | 102 / 0.544 | 0 / 1.000 / 0.116 |
| yawn | 98 / 0.667 | 0 / 1.000 / 0.092 |
| wavy | 52 / 0.899 | 0 / 0.959 / 0.020 |
| aa, ee, ih, oh, ou, grin, surprised | 28-36 / 0.70-0.80 | 0 / 1.000 |
| frown, smile, pout (closed) | 28-42 / - | 0 / - |

MakeHuman rest folds 120; build `face_folds` 1318 FAIL, `face_mouth_cover` 0.544 FAIL. Both baselines: `expr` SKIPPED.
The authored head, before: the tongue never shows (0 in every key: behind the cavity's funnel), the teeth 0-0.2 of an
opening, no line along the lower lip (the drawn heads' outline runs all round: 0.47-0.82 of the bottom edge). Against
the drawn heads (`expr_*`, graded_as): laugh mouth FAIL (ours 0.26 L tall, the drawing 0.153: matched `wavy`, 0.824),
yawn mouth FAIL (0.942: 0.23 L tall, corners high, lift +0.27 against -0.04); on MakeHuman laugh 0.110 PASS (its lips
lap over half the opening, so it realised about 0.144 L of the asked 0.26). SHAPES had been tuned to MakeHuman's
shortfall.

Now (`bp_2b`, authored head): every key 0 folds, cover 1.0 (wavy 0.960, wobble 0.995); tongue 0.21-0.35 of open
shapes, teeth read (laugh 0.13, shout 0.15, clench 0.76), lower line 0.91-1.0; laugh 0.150 x 0.260 L (dist 0.324 WARN,
match laugh), yawn 0.170 x 0.170 (0.255 WARN), frown lift -0.077 (0.120 PASS), chin drop laugh 0.077, yawn 0.061,
shout 0.065.

## What changed so far (uncommitted work is in the pause commit)

- `mouth.py`: SHAPES at the drawn heads' sizes (laugh, wavy, yawn, frown); new mouths shout, clench, grimace, smirk,
  firm, wobble; shape params `skew`, `teeth`, `teeth_lo`, `tongue`; knobs `teeth` (now a share of the opening's
  tallest), `tongue`, `line_lo`; `teeth()` two bands (upper, lower), `tongue()` a pad in front of the funnel, `line()`
  adds the lower lip's line; `jaw_drop` and `_at` (the lower lip's jaw frame for what rides it); `harmonic()` factored
  once per mesh and free set (`_system`: the lab's re-key 40 s -> 22 s).
- The mouth block (`code_base.mouth_block`, tool/face's file, untouched) is sized by the library's extremes: the laugh's
  half-width (2.0 widths) and the yawn's upper lip (0.54 widths, `up=0.391304347826087` so it is the old value to the
  last bit). Checked bit-identical on all four Clawd specs. Keep it so, or decouple it (tool/face's call).
- `character.py`: `assemble = features(geometry(spec))`, bit-identical; teeth, tongue, line get `authored=`.
- `exprqa.py`: the tongue class, `contents()`, skew, brows' `z`, `TARGETS` / `grade_targets` for the presets.
- `qa3d.py`: `Design.expression_sheet` (the expressions measured against idol_D when the body sheet draws none; INFO
  by authority), tongue class in `expression_data`, `COVER` with the tongue.
- `mouthlab.py` (`python -m charkit mouth`): the lab, the chin drop, the 2D `proxy` and `fit_shape`.

## Next steps (in order)

1. Shapes against the drawn heads. The proxy fit (`mouthlab.fit_shape`, results at the pause) left the laugh's lift high
   (ours 0.22, the drawing 0.10: our D is a V, pointy at the bottom; the drawing's top edge is a smile curve and its
   bottom a round U) and the yawn's sides pointed (raise upper/lower_round to ~0.9 for an oval). Fit without 'wave'
   for the laugh and yawn (it dominated the laugh's cost: -3.9); then check on the head (`--head head_bp.pkl.gz`).
   Keep laugh width 2.0 and the yawn's reach (block).
2. Every shape without its own `smile` inherits the spec's (Clawd 0.22): clench, grimace and shout curve up like a
   grin (clench lift 0.18). Give them explicit smiles (clench -0.02, grimace -0.08, shout 0).
3. Chin drop: the drawn heads keep the face's outline; ours drops the chin 0.06-0.08 L on laugh, yawn, shout. Try
   `jaw_follow` 0.3 (a mouth knob, keys only) and watch folds and cover.
4. MakeHuman base (clawd.json, the default gate spec until tool/default-spec merges): its outer rings use `spread` and
   fold (28-102 per key). Try the harmonic solve there too (free: `outer` rings and the jaw's edge), or leave it
   (the base is being retired) and say so.
5. Expressions: add the lid shapes (`eyes.expressions`: focus, squeeze, wince, shy) with `qa3d.FACE_EXPECT` ranges that
   hold on both heads (face_expr_range must stay PASS), the brows (`brows.expressions`: focus, knit, pained), the
   PRESETS in `scene.py` (effort, shout, focus first; then surprise, angry with eye 'angry', pain, smug, embarrassed,
   sad), `scene.MOUTH` / `EXPR` lists and `boards/face_board.set_expr`'s brow map. Grade with `exprqa.TARGETS` as
   `face_preset_*` checks in `qa3d.face_part` (graded: `face_*` has no reference authority).
6. Tests: `charkit/tests/test_mouth.py` (the block held, teeth/tongue/line shapes, TARGETS grading, proxy vs head).
   `history.STEPS` entries: `expr_*` (measured against idol_D again), `face_folds` and `face_mouth_cover` (the library
   grew).
7. Boards on the render box: `python -m charkit remote --box render build charkit/spec/clawd_body_pieces.json --out
   charkit/out/mouth_boards --boards expressions,mouths` (plus views,body as briefed), then `python -m charkit mouth
   BUILD --boards BUILD/boards --against charkit/out/mouthlab/bp_before` for the contact sheet page. Note the
   authored spec's full build currently fails at garments (above): the boards need that fixed, or a build that skips
   garments.
8. Gates: `python -m charkit remote gate tool/mouth --into pipeline-3d` and with `--spec
   charkit/spec/clawd_body_pieces.json` (its baseline build fails today at garments, so that gate will FAIL on the
   baseline until the integrator fixes it).
