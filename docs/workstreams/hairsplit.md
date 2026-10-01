# Hair methodology overhaul, step 1: the lock splitter (tool/hairsplit)

State: in progress. Worktree `~/animation-pipeline-hairsplit`, branch `tool/hairsplit` from tool/hair5 `83f503c`.
tool/hair5 round 2 is finishing in `~/animation-pipeline-hair4` (read only); until it merges, the hair builder files it
touches (`charkit/geom/hairpieces.py`, `hairlayers.py`, the spec's hair parts) aren't edited here: new modules only.

## The brief (Michael, 2026-09-30)

Hair is the weakest part of the model: its bulk is one visual-hull shell with locks painted on as regions, scoring
0.331 against the 52-lock hand truth (a random split 0.392). Michael favours option B: each drawn lock its own thick,
tapered, layered shell fitted per view. B needs locks as closed regions with cross-view identity; the sheets draw lock
strokes open (10-22 closed regions per view) and hand truth doesn't scale. Step 1: an algorithmic lock splitter,
measured against the hand truth. Step 2 (if room): the B pilot on the side locks and one group of back flicks.

## The splitter (`charkit/hairsplit.py`, `python -m charkit hairsplit`)

Per view on the design grids: ink (a black top-hat, threshold a share of the sheet's own line contrast) -> strokes
(skeleton, spurs pruned, free ends with tangents) -> flow (stroke tangents in doubled angles, normalised convolution at
0.04 and 0.12 L, a radial prior from the crown; downstream away from the crown; refined with the tips' protrusions) ->
tips (local maxima of the outline's distance from the crown, prominence 0.02 L, plus acute convex corners) -> closing
(each upstream free end extended along the flow until ink, an extension or the outline; trapped balls close the rest)
-> axes (from each tip upstream) -> locks (regions cut by the lock walls; tips' seeds split a region along the flow;
tipless walled regions are own locks if they flow out of the hair, else merge whole along the flow) -> layers
(T-junctions) -> head coordinates and cross-view matching.

Every length is in L or in the sheet's measured line width; thresholds are shares of the sheet's own contrast.

## Log

### Merges

- pipeline-3d 961037c (tool/hair5 merged: the hair builder files are free; per-lock shells are the direction) -> 9b014b5.
- pipeline-3d de477dd (deterministic tooling: `charkit sweep`, `sweep swap`, declared checks, `charkit review page`,
  docs/CODEMAP.md) -> 7571fde. Use `charkit sweep` for the B pilot's variant runs.

### Michael's calls (2026-09-30, via the coordinator)

Back seams A; the one-tone ahoge stays (revisit when the ahoge is a lock shell); the lock truth's calls F, G and H are
all yes (side flick tips scored as flyaways; the outer side masses unscored; the front's and back's side flicks are the
same flicks). The truth file already encodes them (its recommended defaults): the scores below are against it.

## Results (round 1)

Run: `python -m charkit hairsplit --out charkit/out/hairsplit/final --score` (77 s on the laptop, the inputs
included). Numbers: `tools/hairsplit/ablation.py charkit/out/hairsplit/final` (ablation.json, stages.npz),
`crossview.py charkit/out/hairsplit/final/crossview.json`, `layercheck.py charkit/out/hairsplit/final/layers.json`,
`linecheck.py`, `oracle.py`. Review page: `charkit/out/hairsplit/final/review/index.html`
(`tools/hairsplit/review.py charkit/out/hairsplit/final charkit/out/hairsplit/final/summary.json`).

**Lock IoU against the 52-lock truth (all views; unmatched locks 0):**

| source | all | bangs | side locks | lower back | flyaways | ahoge |
|---|---|---|---|---|---|---|
| random split of the truth | 0.392 | 0.398 | 0.429 | 0.294 | 0.375 | 0.609 |
| random split within each family | 0.547 | 0.470 | 0.445 | 0.619 | 0.504 | 1.000 |
| today's build h5_base (hull shell's locks) | 0.331 | 0.435 | 0.382 | 0.316 | 0.211 | 0.379 |
| structure labeller (hairlayers.lock_regions: lines, two tones, necks) | 0.548 | 0.552 | 0.446 | 0.742 | 0.426 | 0.719 |
| splitter: ink cells (trapped balls on the drawn ink only) | 0.355 | 0.130 | 0.558 | 0.129 | 0.494 | 0.622 |
| splitter: closing (+ upstream extensions, hem notch lines) | 0.521 | 0.579 | 0.439 | 0.481 | 0.534 | 0.610 |
| splitter: + tips and flow (each pixel to its tip along the flow) | 0.407 | 0.270 | 0.509 | 0.476 | 0.347 | 0.594 |
| **splitter: + merge / split (the regions; default)** | **0.583** | 0.571 | 0.612 | 0.465 | 0.661 | 0.589 |

Per view (splitter / random / within family / h5_base): front 0.653 / 0.297 / 0.522 / 0.335; three-quarter 0.467 /
0.460 / 0.552 / 0.363; profile 0.634 / 0.363 / 0.661 / 0.302; back 0.541 / 0.486 / 0.495 / 0.323.

Readings:
- The splitter beats the random split in every view and family but the ahoge (0.589 against a random cell's 0.609:
  the three-quarter's ahoge, 0.217, merges with the crown strip its base opens into) and beats the within-family floor
  overall (0.583 against 0.547) without knowing the families.
- The ablation: the extensions are the closing (ink cells 0.355 -> 0.521); the tips alone, pixel-wise, are worse than
  the cells (0.407: one tip claims whole drawn locks); the region logic on top is the splitter (0.583).
- The labeller is level overall (0.548) and far ahead on the hem (lower back 0.742): its two-tone split reads the back's
  hem layer (drawn in the shadow tone) as separate flick regions at their necks. Reading the cel tones as walls in the
  splitter cost the bangs more than it gained (0.580 -> 0.556); a hem-only tone rule is the open item.
- Ceilings (tools/hairsplit/oracle.py, a probe): an oracle merge of our regions reaches 0.707 (front 0.72,
  three-quarter 0.87, profile 0.80, back 0.50). The merge rule is the limit outside the back; in the back the regions
  themselves join neighbouring hem flicks. The drawn ink already covers 92% of the truth's lock lines within 3 px
  (linecheck); 69% of the ink inside a lock is strand texture, not lock lines.
- Pair analysis (tools/hairsplit/pairs.py, 394 adjacent region pairs): size predicts a correct merge best (AUC 0.78:
  90% of pairs with a region under 0.002 L^2 belong together); ink share and the boundary's direction barely do
  (0.54). Rules built on it (fragments first, short strokes not walls) scored lower: recorded, off.

**What was tried** (locks stage, all views; tuning pair front + back / check pair three-quarter + profile): extend
both ends 0.425 -> upstream ends only 0.550 (kept: lock lines are drawn up from a tip and fade toward the root); tips
own every region 0.523; no tip owns a region 0.579 (the back falls to 0.377); only multi-tip regions split 0.601 (kept);
no tips on a clip's edge 0.580 (kept on principle: the star's points made false tips; the three-quarter loses 0.11
through the Voronoi merge); cel-tone walls 0.556 (off); protrusion bases 0.542-0.564 (off); tipless regions merged by
exits 0.480 / into the nearest decided lock 0.511 (off: the tips' Voronoi kept); fragments first 0.531-0.536, short
strokes not walls 0.544-0.561 (off); notch lines from every notch 0.563 / the hem's only 0.583 (kept); buns removed
from the split 0.532 (off: it cut the under-bun strands; their edges still bar tips only when occ_tips='pieces').

**Cross-view identity** (tools/hairsplit/crossview.py): the shell (an ellipse per height from the front's and
profile's hair silhouettes; each view's calibrated camera from charkit.geom.hull) predicts the back's silhouette within
0.021 / 0.009 L and the three-quarter's within 0.054 / 0.043 L (median, either side). Tips matched by assignment on
azimuth intervals (a silhouette tip may lie up to 30 deg past the limb) and height, the hem's order kept.
- **Call H, reproduced independently:** each of the six side flicks (L1, L2, L3, R1, R2, R3) has a detected tip in
  front and in back, and the matcher, blind to names, links each front tip to its back tip and to nothing else, at
  heights within 0.03 L (L1 0.113 / 0.114, R1 0.118 / 0.118, L2 -0.288 / -0.292, R3 -0.453 / -0.454). The
  three-quarter sees L2 at the same height (-0.300) about 20 deg in front of her side (azimuth 68-74), also matched to
  the front's. under_bun_R links front to back; under_bun_L's front tip links to a neighbouring back tip.
- **Lock-level links** are weaker: against the truth's names, precision 0.40, recall 0.14 (match_by 'locks'); a flick's
  tip often sits in a different lock of ours than the flick's body (a curled tip cut from its lock), so the per-view
  lock regions, not the tips, limit lock identity. match_by 'tips' (every tip's lock linked) is worse at the lock level.

**Layering:** T-junctions (skeleton junction clusters, a straight bar and a stem) front 11, three-quarter 10, profile
7, back 5, near-T 1; 42 votes, ranks by least squares (each lock's `layer`). No vote falls between locks matched to two
truth families, so the truth can't grade them: unverified.

**Tests:** `charkit/tests/test_hairsplit.py` (a bob with three locks drawn with open lock lines from its hem notches:
three locks found, tips at the drawn tips, the locks never below the cells; the shell's azimuths; the interval and
rank helpers). The design-level score is a measurement (the inputs need the produced outfit masks), not a test.

**Files:** `charkit/hairsplit.py` (the module and CLI), `charkit/cli.py` (the `hairsplit` command),
`charkit/tests/test_hairsplit.py`, `tools/hairsplit/` (dev, sweep, cmp, ablation, oracle, pairs, perlock, linecheck,
tipcheck, crossview, layercheck, zoom, pics, review). Outputs (untracked): `charkit/out/hairsplit/` (final/, abl*/,
dev/, inputs.pkl, ctx5.pkl, ref/h5_base.npz and the hair5truth scores copied from tool/hair5's out).

## Gate

Pregate at 7022c7e: PASS, 0 moved, 0 blocking (`charkit/out/pregate/pregate_tool-hairsplit_7022c7e3_into_de477ddc.md`).
**Box gate running** (`python -m charkit remote gate tool/hairsplit --into pipeline-3d`, log
`charkit/out/hairsplit/gate.log`). The branch adds a measurement and tooling only (no QA part, check or builder change):
expected no moves.

## Step 2: the B pilot (not started; the next round's plan)

1. Read the locks per view from `python -m charkit hairsplit --out DIR` (hairsplit.npz: VIEW lock images on the
   design grids; hairsplit.json: per lock its cells, tip, root, axis (crop px; box gives the offset), width profile
   (L), layer rank, xid; tips_head and tip_matches for the tips' cross-view links).
2. Pilot pieces: the side locks (front L_front / L_jaw / R_front / R_jaw, three-quarter, profile) and the back's left
   flick group (back L1-L3 with the front's and three-quarter's matched tips). Each matched lock as a tapered shell:
   its axis a 3D curve fitted to the per-view axes (each view's camera: u = x cos az + y sin az, z up; the shell's
   azimuths as the initial depth), its width per station from the drawn widths (width_L), thickness from the layer
   order and a share of the width; fitted per view to the lock's cells (IoU in every view); opt-in behind a spec
   setting in hairpieces (`lock_model: 'shells'`, default unchanged). Templates first: the hull gives the initial
   depth and measurement only.
3. Measure with `python -m charkit sweep` (per-view guard IoUs built in): lock IoU (hairlocks score), hair_lock_lines_*,
   builder folds, art_terminator_hair (< 2.5), every hair piece's IoU per view (the guard), art_peeks_hair; against
   today's hull shell.
4. Fix the splitter's two weak spots first if the pilot needs them: the curled flick tips cut from their locks (the
   lock identity) and the hem flicks (a hem-only tone rule; the labeller reaches 0.74 there).
5. The buns' fit ambiguity (`~/animation-pipeline-bunorient/docs/workstreams/bunorient.md`): watch, don't take on.
