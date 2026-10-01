# Hair strokes and tones (tool/hairstrokes)

Worktree `~/animation-pipeline-hairstrokes`, branch `tool/hairstrokes` from pipeline-3d 3168961. Rules:
`~/.claude/agents/charkit-worker.md` (policy K, the guard, the tools: `charkit sweep`, declared checks + `calibrate
--declared`, `charkit review page`, docs/CODEMAP.md). Harness scripts and outputs: `charkit/out/hairstrokes/`.

## Brief (Michael, 2026-10-01, via the coordinator)
Hair lacks "detail in the bulk of the mass": in anime hair that detail is mostly ink strokes inside the locks (strand
lines, partial separations), not 3D relief. Do for hair what garments4 did for the skirt's creases (traced from the
design, drawn as a line layer, scored by declared calibrated checks). The geometry track (tool/hairshell3, the lock
shells over the whole head) owns the shells' geometry; this track owns the strokes and the tones on top, on both the
hull shell and the lock shells. Don't touch shell geometry, garments, face, hands.

1. Measure first: trace the design's interior hair strokes per view (ink inside the hair silhouette that isn't a lock
   boundary the splitter uses); declared, calibrated checks per view for presence, position, direction (pass on the
   design jittered 1-2 px, fail on today's build).
2. The hair line layer: the traced strokes rendered on the hair surface, moving with it (garments.ink_strokes'
   mechanism), projected per lock where the splitter's locks exist; right in every view, on real render-box builds.
3. Cel tones: the drawn shadow and highlight shapes per lock, traced, measured, rendered in the hair's look layer;
   art_terminator_hair <= 2.064 (six-placement means as well as the placement).
4. Guard and review: every hair piece's IoU per view, art_peeks_hair, hair_noise, folds beside every change; review
   page (design | today | strokes | strokes + tones, per view, matching scale, close-ups).
5. Gate each milestone (strokes, then tones): `python -m charkit remote gate tool/hairstrokes --into pipeline-3d`.

Scope additions (coordinator, 2026-10-01; each checked against the design first, built only where drawn, each a
declared calibrated check):
- Strokes milestone: (a) line weight and taper (strokes taper at their ends, inner lines thinner than the silhouette
  outline); (b) thin strays beyond the silhouette at the sides (Michael's flag 4) as tapered strokes (the larger flicks
  are the geometry track's); (c) the buns' drawn wrap lines.
- Tones milestone: (d) custom shading normals per lock blended from a smooth head envelope (clean cel shadow shapes;
  should control art_terminator_hair); (e) the inner/underside tone (darker on lock undersides and the underlayer);
  (f) the highlight band (the drawn shine marks on the crown and bangs, view-aware, not fixed patches).

## State
- Setup done (2026-10-01): notes, `charkit/out/hairstrokes/`.

## Jobs
