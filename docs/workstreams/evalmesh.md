# evalmesh: subdivision and Solidify in the venv (tool/evalmesh)

Worktree `~/animation-pipeline-evalmesh`, branch `tool/evalmesh` (round 3 from pipeline-3d 9eba0b0). Michael's
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

**UVs:** Blender's converter (subdiv_converter_mesh) groups a vertex's corners into one UV value when they sit within
STD_UV_CONNECT_LIMIT (1e-4) of the group's first corner *and* share its UV winding. The winding is cross_poly_v2 > 0:
the trapezium rule in float32, summed from the last corner's edge. The float32 detail matters. The boots' sole caps
have zero-area UV triangles (the trapezium gives exactly 0 in float32 and -1e-16 in float64), and deciding them in
float64 put 800 boot corners 0.18 off. With the float32 rule the boots, skin and masked skin match to 1.6e-6.

**Vertex groups through Subsurf:** Blender carries vertex data linearly: kept at the vertices, the mean of the ends at
an edge's point, the mean of the corners at a face's (`subsurf._carry`, 4.7e-8 against Blender). Not the limit
stencil. Weights above 1 are clamped when added to a group.

**Solidify, as Blender lays it out** (offset -1, the lab's strips): the input vertices first and unmoved, then the
copies moved t in along Blender's vertex normals (unit polygon normals weighted by corner angle). Then the input
polygons, the copies reversed with the first corner kept, and a rim quad (b, a, a+n, b+n) per open edge a→b (rim
faces in Blender's edge order; ours in loop order, which only reorders faces). Rim UVs are [ub, ua, ua, ub].
edge_crease_outer goes on the input's open edges, _inner on the copies', _rim on the cross edges (v, v+n). The old
port had the halves swapped and the copies fully reversed: the positions were right, the winding inside out.

**The build's pieces** (`python -m charkit evalmesh build charkit/out/evalmesh/base_clawd`, report
`charkit/out/evalmesh/lab_base/evalmesh.md`). Ours (geom.subsurf, geom.solidify) against local Blender on the same
input:

| piece | max L | mean L | faces, winding, first corner | UV max |
|---|---|---|---|---|
| skin (level 1) | 9.1e-6 | 3.0e-7 | all equal | 7.2e-7 |
| skin, masked | 3.7e-6 | 3.4e-7 | all equal | 7.2e-7 |
| garments, Solidify + Subsurf (16 pieces) | 9.9e-6 (shorts), 1.1e-5 (collar) | ≤ 4.7e-7 | all equal | ≤ 1.5e-6 |
| garments, Subsurf alone on Blender's Solidify | ≤ 9.9e-6 | ≤ 4.4e-7 | all equal | ≤ 1.5e-6 |
| garments, Solidify alone | ≤ 4.6e-7, collar 2.3e-5 | ≤ 1.3e-7 | all equal, vertex order identical | ≤ 6.6e-8 |
| boots, bow (Subsurf only) | ≤ 1.5e-6 | ≤ 4.5e-7 | all equal | ≤ 1.6e-6 |

Local Blender against the box's bundle (ARM against x86, same 5.2.2): ≤ 1.9e-6 L, except the collar at 1.1e-5.
The old evaluator (evaldrift, box) had the masked skin 0.0088 L off.

Residuals, explained:
- The largest subdivision errors sit on the skin's and shorts' highest-valence poles (valence 72, 48 and 36, and the
  edges next to them): 9e-6 L = 2.3 µm. OpenSubdiv evaluates the end-cap weights there in float32; ours is float64.
- The collar's Solidify (2.3e-5 L) is Blender's float32 vertex normal at a near-degenerate corner. Box and laptop
  Blender disagree there by 1.1e-5 themselves.
- Everything is 10x or more under GEOM_TOL (1e-4 L).

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

- **M1 result** (box, 82f2c5d, `charkit/out/evalmesh/m1_clawd`): evaldrift --stages shows 0 of 110 checks drifting.
  The evaluated sleeves are 1.85e-6 / 1.35e-6 L and every garment is within 1.1e-5 L. The only stage drift is the
  skin's subdivision (M2). boarddiff base_clawd -> m1_clawd: 375 QA checks identical, 22 of 24 images identical (face_030
  max 4/255 on a few pixels, sheet_views max 1). Bundle to bundle, every garment's raw loops are identical. The
  evaluated meshes are the same geometry (0 L; the collar 1.2e-7 L on one vertex) with the same winding, first corners
  and UVs. Only their vertex order changed: BMesh's to_mesh no longer reorders the edges.
- Merged pipeline-3d 4de65ab (tool/face4) at 2ac1653.
- **M1 gate: PASS under K** (73be408 into 4de65ab; report `charkit/out/gate/gate_tool-evalmesh_73be408_into_4de65ab.md`).
  No check changed, all 56 test files ok, build CPU 819.9 -> 934.6 s (1.14x), Blender and QA 315.7 -> 283.1 s.
  **M1 is mergeable at 73be408**; the commits after it are notes only.

- **M2 in the evaluator** (box: a build of the merged tree `charkit/out/evalmesh/m2_clawd`, evaldrift --stages with
  the M2 evaluator). 0 of 110 checks drift. The masked skin's subdivision went from 0.00879 L nearest-vertex (mean
  1.4e-5) to **3.42e-6 L (mean 3.6e-7)**. The garments are unchanged, ≤ 1.1e-5 L. One new stage drift, crab_1 2.05e-4
  L, isn't this branch's: the M1 evaluator on the same build shows it too (`m2_drift_M1evaluator.md`). It came with
  face4's merge (the accessories sit on the hair volume, step 2's two volume ports).
- **M3 in the evaluator** (local, the evaluator's own garment Parts against m2_clawd's bundle, per vertex one to
  one): every piece ≤ 1.1e-5 L (the collar), all faces, windings and first corners Blender's (the old port had every
  shell's winding inside out).

- **M3 evaldrift** (box, 16c0040's evaluator on m2_clawd): 0 of 110 checks drift. The stage drift is only crab_1
  (face4's, above). Masked skin 3.42e-6 L, garments ≤ 1.1e-5 L. Commits: M2 9ee0a9e, M3 16c0040. The gate on
  M2 and M3 together follows: the evaluator isn't in the build's geometry, so the QA should not move.

- **M4 groundwork: `evalmesh.finalize(o)`**, a recorded garment's final mesh at rest (geom.solidify, then
  geom.subsurf with the carried weights; materials through the parents). On m2_clawd, against the build's bundle:
  every piece ≤ 9.8e-6 L per vertex (one to one), UVs ≤ 1.2e-6 per corner, materials 100% per face, winding and
  first corners 100%. The weights, rounded as `_object` rounds them, match Blender's own evaluated vertex groups
  (lab, local Blender, Solidify + Subsurf) to 8e-8. The lab carries vertex groups now (`piece['groups']`). Not wired
  into the build yet.

- **Merged pipeline-3d d60486a** (garments3: call L's creased rims, the garment changes, the QA per-piece crops). One
  conflict, bodyeval: both sides changed the evaluator's Solidify and Subdivision. Kept: this branch's exact ports
  (geom.solidify, geom.subsurf) and `Part.solid_settings`, which already carries `edge_crease_outer/_inner/_rim` to
  geom.solidify; its creases go to geom.subsurf as OpenSubdiv sharpness 10·c² (call L's crease 1 is sharpness 10,
  infinitely sharp). Kept from garments3: `Part.subdiv = 0` for a piece built without a Subdivision Surface, and the
  QA's `min(level, subdiv)`. garments3's hand-rolled `sharp=`/`with_sharp` in the old ports went with them;
  `test_creased_rims_stay_flat_and_square` now runs on the exact API with the same assertions (24 loop edges, no cross
  edge, crease 1 infinitely sharp, every vertex at z 0, t/2 or t, 48 child sharp edges, uncreased a bead) and checks
  the evaluator's wrapper gives the same mesh.
- The lab gained a garment shell (`grid_shell`, `grid_shell_rim_creased`: Solidify 0.08, then Subsurf, UVs with a
  seam). Against local Blender: 1.0e-6 / 9.9e-7 L, all 232 faces, windings and first corners equal, UVs 3.3e-7.
  garments3's port gives the same positions there (9.9e-7 L: crease 1 is level-independent); it differed in winding.
- **Gate on the merge: PASS under K** (f35db5a into d60486a; `charkit/out/gate/gate_tool-evalmesh_f35db5a_into_d60486a.md`):
  0 items, no check changed, 64 test files ok, build CPU 717.8 -> 827.2 s (1.15x). Superseded by the fixes below.
- **evaldrift --stages on the merge** (box build `charkit/out/evalmesh/merged_clawd`, f35db5a): 0 of 110 checks drift,
  but three stage rows new with garments3 (the first report kept as `drift_oldmeasure.md`):
  - overskirt_panel_L/R evaluated: n 7526 against 2072. The panels have no Subsurf (garments3's `Part.subdiv = 0`);
    evaldrift subdivided every garment once. Fixed in evaldrift (each Part at its own level, as the QA's Geometry
    does). Then 0.01 L, n equal: a real miss, below.
  - the masked skin: n 49156 against 49251, 0.199 L. Blender's Mask keeps kept vertices whose faces it drops, and
    Subsurf carries them: 95 loose vertices (44 isolated, 51 loose-edge points) under the jacket, 0.02-0.2 L from any
    drawn vertex. evaldrift compared all of Blender's vertices with only our on-face ones. Remeasured on-face on both
    sides, the loose count and the all-vertex measure still in the row. Then 0.0107 L, n equal: a real miss, below.
- **Solidify, a loose vertex** (the template flaps' panels have 126): Blender's vertex normal has a fallback. Where the
  angle-weighted sum has no length, the normalised position. The copy moves t along it (measured to 1.2e-7 L; ours
  left it in place: exactly t = 0.01 L off). `geom.solidify.vertex_normals` takes the fallback: the panels 0.01 ->
  5.7e-7 L, vertex order identical, every face, winding and first corner equal.
- **Subsurf after the Mask, loose edges** (51 on the masked skin): Blender's subdiv converter marks both ends of a loose
  edge infinitely sharp, so a face vertex with a dangling edge subdivides as a corner. The evaluator's masked skin takes
  them as vertex creases (`bodyeval.mask_loose_edges`, `mask_corners`; `Part.corners`): 0.0107 L -> 3.1e-6 L (mean
  3.4e-7) against the bundle. The lab: pieces take `loose_edges` (Blender gets them through bmesh: `edges.add` crashes
  5.2 on the skin), compared on-face; `grid_loose_edge` 9.2e-7 L (0.039 L without the rule), level 2 1.3e-6,
  `grid_shell_loose_vertex` 9.8e-7; `skin_masked` with the Mask's loose edges 3.1e-6 L against local Blender.

- **evaldrift --stages at 1939469** (merged_clawd, the box): 0 of 110 checks drift. Stage drift: only crab_1
  (2.05e-4 L, face4's, above). Masked skin 3.8e-6 L on-face (n 49156/49156; the build's 95 loose vertices reported,
  0.199 L with them), overskirt panels 5.6e-7 L, every garment ≤ 1.2e-5 L (the collar).
- **Gate: PASS under K** (1939469 into pipeline-3d 4007276, infra3 run 3; report
  `charkit/out/gate/gate_tool-evalmesh_1939469_into_4007276.md`): 0 items, no check changed, 65 test files ok, build
  CPU 758.7 -> 751.6 s (0.99x). 4007276 merges into the branch cleanly (the gate's own merge). **M2+M3 mergeable at
  1939469**; the commits after it are notes only.

- **M2+M3 merged** into pipeline-3d (81ffcb1); pipeline-3d 25b1936 (infra-auth: box control on a service account,
  `CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud` in every box shell) fast-forwarded in. Coordinator's go-ahead for M4:
  skin weights linear (Blender's), the panels' loose vertices kept as Blender keeps them, charkit/subdiv.py left to
  tool/face5.

## M4, the switch (in progress)
- `geomstage.finalize(P)`: every recorded garment with a Solidify or Subsurf gets its final mesh at rest
  (`evalmesh.finalize`) in its `_object` call (`final=True`); its 'thick'/'sub' events go; where they stood, its
  object gets `ck_shell` (the outline's cap: `shade.shell_of` reads it) and `ck_final_levels`. The recording as made
  stays in `meta['coarse_events']` (`pieces(P, coarse=True)`: the lab, motion QA). `garments_product` and the
  evaluator's `garment_piece` finalize, so the evaluator's garments are the build's meshes by construction (no
  solid, no subdivision left in their Parts).
- Weights: `garments.group_weights` (3 decimals, 1e-4 and under dropped, clamped to 1) is what `_object` gives the
  coarse vertex groups and what finalize carries; a final object's weights go in as carried (not rounded again).
  `_object` sets corner UVs, smooth flags and material indices with foreach_set (the final meshes are 8x larger).
- On merged_clawd's product: finalize 0.9 s for 19 pieces, the product 13 MB (save 1.0 s). Against the bundle's
  Blender-evaluated meshes: all 19 one to one, ≤ 1.2e-5 L (the collar), every face, winding and first corner
  equal, UVs ≤ 1.2e-6.
- **The M4 build** (box, `charkit/out/evalmesh/m4_clawd`, cf5053a + the UV-centre fix):
  - evaldrift --stages: 0 of 110 checks drift; the only stage drift crab_1 (face4's). Every garment's raw f32-identical
    to the evaluator's, evaluated ≤ 7.2e-7 L (exact by construction); masked skin 3.8e-6 L.
  - The export (NAME.look.glb, gltf.export's own writer, as the VRM): every garment mesh against the base build's
    (merged_clawd, Blender's modifiers) within 1e-5 L, the collar 1.07e-4 L (the export's build pose moves the
    shoulders: the collar's blended weights, see motion QA); the skirt 22563 against 22562 exported vertices (one seam
    split). Every other mesh identical (0 L).
  - boarddiff merged_clawd -> m4_clawd: 487 QA checks, 1 differs: poke_share 0.0028 PASS -> 0.02 FAIL. Not geometry:
    the check casts rays at 'raw', which is now the final mesh with the Solidify's inner layer t inside the surface;
    skin within the shell's thickness (under the surface) read as poking through (shorts 166, bodice 30, skirt 31).
    Rescored on the surface layer only: 0.003 (bodice 19, skirt 10, panels 3 + 3, collar 1, top 1; the base 0.0028:
    bodice 18, skirt 10, panels 3 + 3, collar 1): the subdivided surface against the coarse one. Remeasured: a final
    mesh's faces carry their layer (`evalmesh.finalize` 'layer': 0 surface, 1 inner copy, 2 rim; `_object` sets the
    face attribute `ck_layer`; the bundle's raw exports it as 'layer'); `qa3d.poke` reads layer 0 when there is one.
    The gate scores it both ways (the 2x2). 13 of 26 images differ by a few levels (sheet_body/pieces max 186-204 on a
    handful of pixels: the subdivided hems at float32; face boards max 12).
- **Motion QA** (`python -m charkit evalmesh motion BUILD`, `m4_clawd/motion/motion.md`): each garment at 7 extreme
  poses in a local Blender with the build's armature; Blender's per-frame stack on the coarse mesh against the final
  mesh under the Armature alone. 15 of 19 pieces within 1.1e-5 L at every pose (their weights one bone where they
  bend). The bends: skirt 0.040 L max at the kick (p99 0.018, moved 1 L; limit-stencil weights 0.019), collar 0.020
  at twist_bend (stencil 0.016), top 0.0091 (p99 0.0019), bodice 0.0016. Linear weights shipped (the coordinator's
  call); the stencil halves the skirt's worst.
- **M4 gate: PASS under K** (0c9eb95 into pipeline-3d 25b1936; `charkit/out/gate/gate_tool-evalmesh_0c9eb95_into_25b1936.md`):
  nothing blocks, 1 item: poke_share 0.0028 -> 0.003 PASS (value moved). 66 test files ok, build CPU 577.3 -> 684.0 s
  (1.18x). The gate's report has no 2x2 section for poke's remeasure; its four cells measured by hand: old code, old
  geometry 0.0028 PASS; old code on the final meshes 0.020 FAIL (the inner layer read as skin through clothes); new
  code on the old geometry 0.0028 PASS (no layer attribute: every face, as before); new code, new geometry 0.003 PASS.
  **M4 mergeable at 0c9eb95.**

## Round 3 (R3a: limit-stencil weights; R3b: the skin's subdivision, after tool/face5)
- Merged pipeline-3d 9eba0b0 (fast-forward: it already held M4).
- **R3a, the switch to stencil weights** (the coordinator's call on motion QA's numbers: the skirt's kick 0.040 L linear,
  0.019 L stencil; the collar's twist 0.020 -> 0.016). `geom.subsurf.subdivide(carry_rule='limit')` puts the carried
  data through the positions' own refinement and limit stencil (the columns ride with V); `evalmesh.WEIGHT_RULE =
  'limit'`, `finalize(o, weight_rule=)`, the product's meta records it (`final.weight_rule`). The stencil is affine
  and non-negative: weights summing to 1 still do (test_carry_rules, creases, semi-sharp, open borders).
- Weight health, measured on m4_clawd's recording (both rules): at most 3 bones per vertex on any garment (the collar
  2 -> 3 through the subdivision, either rule), so the VRM's four slots never truncate; |sum - 1| <= 1e-3, the coarse
  groups' 3-decimal rounding (the writer renormalises). Motion QA now computes both candidates through `finalize`,
  says which the build ships, and tabulates each one's weights as the VRM takes them (`weight_stats`).
- The VRM checks its own skin weights (`gltf.check` -> `skin_weights`): per skinned primitive, weights >= 0, the sum
  within 1e-5 of 1, every weighted joint inside its skin; faults are errors (the export fails). On existing exports:
  0 errors, sums within 1.4e-7. gltf.py is EXPORT_CODE, so the gate's candidate builds with --vrm and runs it.
- pregate: PASS (0 moved, 0 blocking, 268 s; `charkit/out/pregate/pregate_tool-evalmesh_ed0f91a_into_9eba0b0.md`).
- **R3a gate: PASS under K** (ed0f91a into pipeline-3d 9eba0b0; `charkit/out/gate/gate_tool-evalmesh_ed0f91a_into_9eba0b0.md`).
  Nothing blocks; 66 test files ok; build CPU 721.1 -> 814.2 s (1.13x, the candidate with --vrm: gltf.py is
  EXPORT_CODE). 7 values moved, statuses unchanged: face_shadow_neck_3q 0.0986 -> 0.0398 INFO, face_shadow_chin_edge
  0.0568 -> 0.0479 (FAIL both, better), face_shadow_3q 0.313 -> 0.342, face_shadow_face_3q -0.0558 -> -0.0596,
  face_shadow_chin 0.694 -> 0.676 (FAIL both), face_noise(_sweep) 1e-4 to 2e-4. **All 7 are the export the QA draws
  from, not the weights:** the candidate drew from its .vrm, the baseline from look.glb. The same code built without
  --vrm (`charkit/out/evalmesh/r3a_novrm`) gives the baseline's values to the digit (face_shadow_neck_3q 0.0986, ...),
  and it differs from the --vrm build (`r3a_clawd`) in exactly these 7 of 487 checks. So the stencil weights move no
  QA check. For infra: a gate whose branch touches gltf.py compares a VRM-drawn candidate with a look.glb-drawn
  baseline, and the face shadows read the two exports differently (up to 0.059 on face_shadow_neck_3q).
- **Carried to 6f2e1a4** (`python -m charkit gate --carry`: after ed0f91a only notes and the steps literal, which reach
  neither build; test_cache, test_gate, test_lookqa and test_registry ran again, all ok):
  `charkit/out/gate/gate_tool-evalmesh_6f2e1a4_into_9eba0b0.md`, PASS. **R3a mergeable at 6f2e1a4.**
- **The R3a build** (box, `charkit/out/evalmesh/r3a_clawd`, ed0f91a with --vrm): its QA equals the gate candidate's
  to the digit. The VRM carries valid, normalised weights: 58 skinned primitives, `skin_weights` 0 errors, sums
  within 1.25e-7 of 1, at most 3 bones per vertex; all 19 garments.
- **Motion QA on it** (`r3a_clawd/motion/motion.md`; 19 pieces, 7 poses): every multi-bone piece ships stencil (the
  single-bone ones are identical under either rule). Worst max per pose, linear -> stencil:

  | piece | arms_up | elbows_bent | arms_fwd | kick | squat | twist_bend | split |
  |---|---|---|---|---|---|---|---|
  | skirt | 1e-6 | 1e-6 | 1e-6 | **0.040 -> 0.019** | 0.019 -> 0.019 | 1e-6 | **0.014 -> 0.0066** |
  | collar | 1.2e-5 | 1.2e-5 | 1.2e-5 | 1.2e-5 | 1.2e-5 | **0.020 -> 0.016** (mean 1.3e-3 -> 7.7e-4) | 1.2e-5 |
  | bodice_panel | 1.4e-6 | 1.4e-6 | 1.4e-6 | 1.4e-6 | 1.9e-6 | 0.0016 -> 0.0010 | 1.4e-6 |
  | top | 4.8e-6 | 4.3e-6 | 4.8e-6 | 4.8e-6 | 4.3e-6 | 0.0091 -> 0.0092 (mean 1.6e-4 -> 1.4e-4) | 4.8e-6 |
  | the other 15 | <= 1e-5 at every pose, identical under both rules | | | | | | |

  Worst over all pieces and poses: 0.040 L -> 0.019 L. The top's twist is the one max that grows (1%); its mean falls.
- poke_share's M4 remeasure registered in `charkit/steps/qa3d.py` (the coordinator's bookkeeping for infra4's rule;
  3569e1b).
- **crab_1's stage drift (2.05e-4 L, since face4), attributed** (local, m4_clawd's own code products, scripts in
  `charkit/out/evalmesh/crab/`). The crab moves rigidly: rotated 0.24 deg and shifted 9.8e-5 L, residual 2.5e-7 L.
  Its anchor is nearly the same; the hair volume's slope under it isn't. The star, 14 deg away, is 2.4e-7 L. Ruled out:
  - the volume's ray cast (mathutils float32 against charkit.geom): the same 7,139 rays, 0 hit/miss flips, the grid
    within 3.5e-7 L, the crab within 6e-8 L between the two;
  - the gridded `bodyeval.cull_face` against the build's exact `Face.y`: 1 vertex decided differently (az 28, el -62),
    the crab unchanged;
  - the analytic clipping: no cell round either accessory is clipped.
  **The cause: the selection's signed distance** (`i3d.hair_by_outside` in Blender, `bodyeval.hair_by_outside` in
  the venv: (p - nearest) . normal). Blender's `find_nearest` returns the polygon's normal (Newell's to 0.03 deg), and
  on a tie (the nearest point on a shared edge or vertex, usual 0.5 L out) whichever polygon its float32 BVH reaches
  first. The port takes its own triangle. On the same inputs, 1,804 of 75,006 generated vertices get the other sign at
  `clear` (normals a median 103 deg apart at the same nearest point, 2.2e-7 L apart). 117 survive the masks (24 only
  ours, 93 only Blender's, one at az 12, el 27 beside the crab). **With Blender's selection the evaluator's crab is
  2.7e-7 L from the bundle's.** face4 moved the head's vertices and exposed a latent tie near the crab; it isn't a
  face4 fault.
  Not fixed here: matching Blender means its BVH traversal order, which isn't a small change. The fix is structural:
  one selection for both sides (GEOM_TRUTH step 2, the hair volume venv-side), ideally with a tie-free sign (the
  angle-weighted pseudo-normal at the nearest feature). That's hair3's round.

## Next
- R3b, the skin's subdivision (rollout step 4: shape keys, two UV layers, render level 2) once tool/face5 has merged
  into pipeline-3d (it moves charkit/subdiv.py onto geom/subsurf.py). Not started. geom.subsurf's carry_rule='limit'
  is ready for the skin's weights if motion QA says so.
- crab_1: one selection for build and evaluator (hair3's round, above).
- infra: the gate's VRM-vs-look.glb drawing difference (above).
- The coordinator's merge. Then: the skin's subdivision (rollout step 4: shape keys, two UV layers, render level 2);
  the 2x2 not triggered for a QA change that comes with a geometry change (infra); the stencil weights as an option
  for the skirt and collar if the bends matter in motion.
- M4, the switch (plan):
  1. Garments first; they're already a venv product. The mesh content is done and measured (`evalmesh.finalize`,
     above). What's left is wiring it into the product. After `garments_geom` records build(), a venv pass gives each
     `_object` its final mesh at rest: geom.solidify then geom.subsurf at the modifier's `levels` (garments: 1 for
     viewport and render). Polygons come as (loopv, counts), per-corner UVs from subsurf, mat_idx through `parent`,
     and weights copied to the Solidify copies and carried linearly through Subsurf, as Blender carries vertex data.
     The pass drops the 'thick' and 'sub' mod events. Armature ('rig', inside _object) and the outline stay.
  2. The outline's cap reads the shell's thickness from the 'thick' SOLIDIFY (`shade.shell_of`). With the modifier
     gone it needs the thickness as a custom property the recording sets (`ob['ck_shell']`).
  3. The bundle's 'raw' variant of a garment becomes the final mesh. Checks that read raw (poke-through, open edges)
     change measure: score them both ways (the gate's 2x2). The evaluator's Part then has no solid and no subdivision:
     exact by construction.
  4. The skin waits for rollout step 4 (the character product). It carries shape keys, two UV layers, the Mask and
     render level 2. geom.subsurf is numpy-only, so Blender's character stage could call it meanwhile, but GEOM_TRUTH
     wants it venv-side.
  5. Motion QA: at extreme poses, Blender per frame (Armature, then Solidify and Subsurf on the posed coarse mesh)
     against the engine way (Armature on the final rest mesh). Per-vertex distances per piece, with linear weights
     (Blender's own) and limit-stencil weights as the two candidates.
- Follow-ups: `charkit/subdiv.py` (faceeval, code_base, headfit) is a third Catmull-Clark. Its `carry` puts vertex
  weights through the limit, but Blender carries them linearly (measured). Delegating it to geom.subsurf changes
  faceeval only near its crop border and in carried weights, so do it with tool/face.
