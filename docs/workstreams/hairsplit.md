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

