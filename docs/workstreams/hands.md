# Workstream: hands (tool/hands)

Worktree `~/animation-pipeline-hands` (sparse charkit profile), branch `tool/hands` from pipeline-3d ccc9552.
Brief: coordinator, 2026-09-30 (round 1). Plan (Michael, 2026-09-30; skeletal, not shape keys), docs/ROADMAP.md item 7:
1. Measure first: the design's hands cut as pieces; calibrated checks (hand silhouette IoU per view, finger
   count/separation where drawn) that pass on the design jittered 1-2 px and fail on today's mitten; registered in
   charkit/steps/.
2. The hand breakdown reference (paid generation approved, n=2, few calls, tools/gptimage.py, ledger): relaxed, open,
   fist, point; front and side; refchecked against the turnaround's A-pose hands; manifest entry with sha256.
3. A hand template replacing the mitten (palm, finger lengths/widths, taper, thumb base; knuckle loops).
4. Weights on the VRM finger bones by construction.
5. A hand-pose library as a `hands` expression component (round 2 if it doesn't fit).
6. QA: silhouettes per pose; fist interpenetration and knuckle volume.

## State
- (starting) reading the codebase.

## Numbers

## Next steps
