# char3: a new character end to end (tool/char3)

Worktree `~/animation-pipeline-char3`, branch `tool/char3` from pipeline-3d d44db780. The character is **c3**; it is
PRIVATE: its references, prompts, spec, manifest, builds, review pages and report live under `charkit/private/c3/`
(gitignored). This file is public: nothing about the character's identity goes here, only what the pipeline did.

**Goal (Michael, 2026-10-01):** a stress test of how much of charkit is overfit to Clawd. Reference images in, a
rigged model out, no per-character tuning. Steps: (1) a reference set (turnarounds and separated layers), refchecked
and registered; (2) a build from its own spec (base and body declared; no MakeHuman fallback); (3) a generality
report: per stage ran unchanged / generic fix / blocked by a Clawd-specific assumption / missing builder; the QA pass
share with applicable and Clawd-named checks separated; what reached the model; the remaining overfit points ranked.

## Generic fixes (shared code, under tests; with nothing declared, Clawd reads as before)

1. **Private folders sync to the boxes** (bucketsync, build.sh's rsync fallback): `charkit/private/` is gitignored
   but synced; `charkit/private/<name>/out/` stays on each side. test_bucketsync (+3; its `__main__` added: the gate
   ran none of it).
2. **The implausible-scale guard** (the 68 GB QA hazard): `sheetqa.detect_figures` raises when the eye-spacing scale
   makes the tallest figure under one head length; every measuring grid is capped at `faceqa.MAX_WINDOW_PX` (100 M px)
   where it is sized. test_sheetqa.
3. **The palette** (`charkit/palette.py`): a manifest's swatches with roles (found on the model sheet's swatch row)
   classify drawings by nearest colour in `sheetqa.classes` and `bodyqa.family`; shared colours read as hair and are
   split by place; ink-blend swatches (a dark iris) count only past an opening; dark eyes found by shape. Resolve
   activates it and fills the spec's colours (skin, hair, iris, brows, lashes) where the spec gives none (the code's
   defaults are Clawd's). test_palette.
4. **View naming and eye pairs** (`sheetqa`): the generated turnaround's order names four figures when the eyes can't
   (small dark eyes, a white-haired back); the eye-pair spacing bound relaxes where the band's rule finds none (a
   small head on a wide A-pose band: its 10% of the band is Clawd's proportion); slivers re-searched on the eye line.
5. **The body window** (`bodyqa.use_window`): declared per character (a figure 8 heads tall stands to -7.1 L; Clawd's
   window stops at -6.2 L and cut it at the shins in every body grid).
6. **refcheck without a 2D rig**: the common scale from the face sheet itself, the departures from the body sheet,
   head boxes found when none are typed (Clawd's flow needed her source sheet plus rig).
7. **layerref `--kind edit|alone`** (palette-driven, generic): a turnaround redrawn without a cover; a piece alone
   (mannequin, object, breakdown); tolerances declared before measuring; calibrated in test_palette.
8. **The outfit graph without a 2D rig** (`charkit/outfit_sheet.py`): pieces declared in the manifest (swatches, zone
   bones, side, motion), masks by palette within each piece's zone (rivals limited to what can be there), the skeleton
   measured from the base body's front silhouette. test_outfit_sheet.
9. **The body from the base body sheet**: `geom.hull --sheet base_body` and `manifest.body_hull` (the authored body
   fits the base body's hull where the manifest declares one).

## Step 1: references (done; review page handed over)

19 calls (gpt-image-2.5-sunburst, high, 2560x1440, n=2), all succeeded, in tools/ledger.jsonl with c3 paths. Model
sheet with an 18-swatch palette; head, body and base body turnarounds; separated layers for every cover (headwear,
facial hair, the drape and its pin, the belt, the footwear, the main garment), a registered hair breakdown (redrawn in
the head turnaround's exact layout: a fresh breakdown drawing disagreed with the turnaround, hair shape 0.28-0.56),
a drape close-up set (the shoulder it hangs over is never seen on the turnaround; the knot's structure), hands,
flat-lay. Refchecks: every separated layer passes (kept parts 0.95-0.99 IoU, outside < 0.03; pieces alone 0.65-0.85);
a headwear sheet's turned views 0.58-0.59 against 0.60 (not loosened: the turnaround stays the authority there);
straps and the knot structure-only. Michael's answers (2026-10-01): placements as read from the source; no glasses;
the hand sheet accepted by eye.

Findings from step 1: handref scales by Clawd's wrist cuffs (a bare wrist has no scale); refcheck's eye comparison is
anime-calibrated (a narrow drawn eye FAILs lid_gap).

## Step 2: build (in progress)

Venv stages run locally first (`charkit/private/c3/stages.py`: resolve, the produced references, code head, code body),
then a box build. More generic fixes found on the way (uncommitted until the stages pass):

10. **Head sheets** (`refcheck.detect_heads`): a blob within 0.06 head widths of the silhouette's edge is no eye (a
    bald construction head's ears read as a front pair at full size); a profile's ear as its second eye (the rear blob
    behind the axis, the front one 1.3x further ahead: fronts read 1.02-1.03 on both characters); the head sheets'
    layouts (4, 3, 2 heads) name the views when the eyes' names are inconsistent (a view twice or out of order).
    Clawd's head sheets read identically on every path the build uses.
11. **Hull hair** (`geom.parts`): the hair's colour from the palette's hair roles (it was fitted to the head's top,
    "all hair" on Clawd; a crown sits there); **facial hair** (`parts.facial_hair`, new): the hair-coloured hull over
    the lower face, which the hair's cover keeps clear (Clawd has none), built beside the hair (`hair.shape.facial`,
    `hair_facial`); a character with a hull and no hair in its spec gets the hull's hair by default.
12. **Accessories** (`accessories.crown`, `accessories.pin`, new kinds): a ring band with blades and jewels; a domed
    badge with a rim and its emblem's cells; placed from the eyes (`from_eyes`), a pin parented to its bone.
13. **Drafting** (`outfit_sheet.draft`, the build's `outfit_draft` step): a rig-free character's garments and
    accessories drafted from its own outfit graph, masks and hull when its spec lists none: a crown (size and depth
    from its masks, its point count from the tips the front shows), a pin (its depth and facing from the hull's
    labelled surface, its emblem from its own sheet), a tunic (a shell and a skirt: hem and flare from its mask), a
    belt, sandals as shoes; types with no template listed (a drape).
15. **The authored body's feet** (`code_body.foot`): read Clawd's `boot_L`/`boot_R` hull points (the body's
    fit raised with none); now any footwear piece, else the bare foot's hull points (Clawd's path first, unchanged).
16. **A sash garment** (`garments.sash`, new kind): a band round the torso in the plane through one shoulder's top and
    the opposite hip, its radius the body's plus an offset, weighted from the body under it; a drape is drafted as a
    sash (its shoulder from the front mask's diagonal) and its hanging end as a panel. A first template for the
    drape (its knot and folds are not built).
17. **The crown's point count** from its own shape sheet: the tips its front view draws, at x = R sin(phi): 360 degrees
    over the nearest pair's angle (counting visible tips confused the fleurs' lobes with tips).
14. **The generality tally** (`charkit.generality`): a build's QA pass share with checks named for Clawd's pieces apart
    from those any character has. A recent Clawd build: 708 checks, 396 named (share 0.69), 312 applicable (0.78).

Stage ledger so far (ran unchanged / generic fix / Clawd assumption / missing builder):
- reference generation: ran unchanged (prompts per character, as expected);
- refcheck (heads): Clawd assumption (a source sheet plus 2D rig for the scale; her palette) -> fixes 3, 6, 10;
- layerref: Clawd's kinds only -> fix 7; handref: Clawd's cuffs -> finding (scale by the wrist's own width);
- sheet detection: her palette, her proportions (eye spacing vs the band), eye-based view names -> fixes 3, 4, 10;
- produced outfit masks and graph: her 2D rig -> fix 8; the body window: her proportions -> fix 5;
- the hull: ran once detection ran (178 s, 305k faces);
- hull hair: "the head's top is all hair" -> fix 11; facial hair: missing builder -> fix 11;
- garments: hand-written lists, no drafting without a rig -> fix 13 (tunic, belt, sandals approximated with existing
  kinds; the skirt template always paints Clawd's stepped hem texture: harmless only with one colour); drape: missing;
- accessories: hair clips only -> fix 12.

## Step 3: the generality report (public summary; the full report is private: charkit/private/c3/report/)

(filled after the first build: the QA pass share with checks named for Clawd's pieces apart, what reached the model,
the remaining overfit points ranked)

## State

- Commits: fd078c77 (fixes 1-2), 35b169c5 (fixes 3-9).
- Not yet gated.
