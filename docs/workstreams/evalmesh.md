# evalmesh: subdivision and Solidify in the venv (tool/evalmesh)

Worktree `~/animation-pipeline-evalmesh`, branch `tool/evalmesh` (fast-forwarded to pipeline-3d ae7fd45). Michael's
call J: Subdivision Surface and Solidify leave Blender. They are computed at rest in the venv and then skinned (the
game-engine way; the VRM export needs the final meshes anyway). Motion QA checks the bends at extreme poses against
Blender's per-frame modifiers. The outline's inverted hull stays render-time (call I). This is docs/GEOM_TRUTH.md
rollout step 7, with 7b decided: "own it".

## Milestones (each lands separately, gated)
- **M1 (7a): the winding decided venv-side.** Exit: evaldrift shows the sleeves' evaluated shell within GEOM_TOL, and
  no other piece moves.
- **M2: subdivision exact.** `bodyeval.subdivide` matches Blender's Subdivision Surface (OpenSubdiv) on the skin (level
  1 viewport, 2 render) and the garments (level 1), per piece: max and mean vertex error, face counts. Exit: within
  1e-4 L everywhere, or each residual explained.
- **M3: Solidify venv-side.** Exit as M2.
- **M4: the switch.** The build writes venv-made subdivided and solidified meshes at rest. Blender keeps Armature, Mask
  and the outline. QA measures a venv-made bundle. VRM carries the final meshes. Motion QA at extreme poses against
  Blender's per-frame modifiers, with numbers.

## The lab (measure first): `charkit/evalmesh.py`
A piece is a mesh (winding as given), optional corner UVs, edge creases and a modifier stack. `evalmesh.blender(pieces)`
runs the stack in a local headless Blender 5.2.2, the boxes' version (infra/gcp/build.env). `evalmesh.ours(p)` runs our
port. `evalmesh.compare` measures ours against Blender per vertex: nearest-vertex matching that must be one to one,
faces matched by vertex set, winding, and UV per corner. `evalmesh.shapes()` gives synthetic pieces: a smooth cube,
sharp and semi-sharp creases (a ring, one edge, an L), an open grid (borders and corners), UV seams, n-gons, triangles
and two levels. A run takes about 1.5 s.

## Findings
**Winding (M1), on the baseline build `charkit/out/evalmesh/base_clawd` (box, ae7fd45):**
- Blender (bmesh recalc) flips whole pieces: 14 of 18 pieces fully, the bow 456 of 942. Its reversal keeps the first
  corner ([v0, vn-1, ..., v1]). The old port reversed fully ([::-1]), so its child quads started elsewhere.
- On this head the old port and Blender agree in orientation on every piece. The sleeves' 0 of 1,856 came from an
  older sleeve (before hull-limbs) and doesn't reproduce: evaldrift's evaluated sleeves are 1.85e-6 L.
- The new rule (`charkit/geom/wind.py`): consistent per manifold region, then the sign of the region's flux
  Σ area (c − centre)·n. It gives Blender's faces tuple for tuple on all 18 pieces (0 differ). Conditioning
  |flux|/Σ|terms| is 0.68 at the lowest (a bow region), 0.85 on the collar, and 0.95 to 1.0 on the rest, so it is
  robust, unlike the old one-vertex heuristic.

**Subdivision (M2), in the lab:** OpenSubdiv as Blender 5.2 runs it. The rules, established by measurement:
- crease c becomes sharpness 10·c² (c = 0.5: 10c² matches to 2e-7, 10c is 0.1 off);
- boundaries: 'ALL' is EDGE_ONLY (open edges infinitely sharp);
- UVs: PRESERVE_BOUNDARIES smooths inside and keeps seams and borders linear, evaluated at the limit (seams match to
  3.3e-7).
- **The limit is evaluated at the adaptive isolation level (quality 3), not the true limit.** A vertex's value is the
  limit mask applied to the mesh refined to level 3. Any sharpness still semi-sharp at that level counts as smooth
  (infinite stays sharp). A border vertex with one face (a quad's corner on an open border) takes its level-3
  position (the end cap's corner). This matches darts, semi-sharp creases of 0.7 and 0.9, and borders to about 2e-7.
  The true limit is off by 0.03 to 0.07 on these shapes. Smooth extraordinary vertices and infinitely sharp creases
  are level-independent, so the old ports got those right.
- The old ports (`bodyeval.subdivide`, `charkit/subdiv.py`) get smooth, n-gon and triangle shapes to 1.5e-7. They miss
  creases (bodyeval.subdivide ignores them: 0.03 to 0.6 off) and open-border corners (0.004).

## Log
- 2026-09-30: merged pipeline-3d ae7fd45 (fast-forward). Baseline box build `charkit/out/evalmesh/base_clawd`
  (--boards views --no-blend) and `evaldrift --stages` on it: 0 of 110 checks drift. Stage drift: only the evaluated
  masked skin, 0.00879 L nearest-vertex (mean 1.4e-5), which is the subdivision port. The evaluated garments are within
  1.1e-5 L (the collar), and the sleeves 1.85e-6.
- M1 code: `charkit/geom/wind.py` (orient, reverse, consistent, flux). `geomstage._wound` winds `_object`'s faces and
  corner UVs in the recording and records `wound=True`. `garments._object(wound=)` takes them as given, and the
  in-Blender path winds with the same function. bmesh's recalc and `bodyeval.recalc_normals` are gone, and
  `Part.subdivided` uses the recorded faces. Tests: `charkit/tests/test_wind.py`; test_geomstage and test_bodyeval
  updated.

## Next
- M1: box build and evaldrift --stages (`charkit/out/evalmesh/m1_clawd`), boarddiff against base_clawd, then the gate.
- M2: fold the isolation-level rule into `charkit/geom/subsurf.py` locally, around the vertices that need it. Then run
  the build's pieces through the lab: the bundle's raw garments and skin base, with the eye margins creased.
