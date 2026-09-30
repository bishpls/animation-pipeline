# tool/hull-local: the hull's decimation made local

Branch `tool/hull-local` from pipeline-3d 3a0ad37 (worktree `~/animation-pipeline-hulllocal`). Started from face
round 5's collar trace (docs/workstreams/face.md, round 5): a jaw change moved the collar 0.035 L through the body fit,
which reads hull.ply, whose fixed-budget decimation had moved vertices far from the face.

## The measure (`tools/hull_local/locality.py`)

The hull built twice with one hull code, only the authored head's sections differing (`dump_sections.py` from two
trees: pipeline-3d 3a0ad37 and tool/face5 36908d0), every stage kept and compared: the carved voxels, the surface before
decimation (exact positions), hull.ply (vertices not bit-identical, and each vertex's distance to the other mesh's
surface) by distance from the changed voxels and by part of the figure, and the per-vertex labels. The lab's build of
the base reproduces the produced hull byte for byte (hull.ply and hull_pieces.npy, sha1 equal).

**Before (a fixed 150,000 faces):**
- voxels: 754 changed, all in the face's box (x -0.35..0.35, y -0.355..0.155, z -0.366..0.204 L); `rounded` identical;
- surface (marching cubes, blur 1): local. 5,912 / 5,862 vertices differ, the farthest 0.070 L from a changed voxel;
- hull.ply: 1,723 vertices differ; **401 of them farther than 0.06 L from the edit** (202 over 1e-6 L, up to 0.0008
  L), in 25 separate 2-vertex patches spread over the whole figure: the head's sides and back 314, crown 39, neck 3,
  torso 24, legs 21. These are the budget's last collapses. The face changes the face's triangle count, so the budget
  runs out at a different edge, anywhere on the figure.
- labels: 0 of the 73,280 shared vertices change class or piece.

**The change:** `hull.decimate_hull` decimates to a quadric error, `DECIMATE_COST` 1.2e-10 L^4 (the last collapse's
cost at 150,000 faces on the default spec, 1.204e-10: the same density), through `remesh.decimate(max_cost=)`. A face
count remains for labs (`--faces N`, `build(faces=N)`); the head-sheet hull (`--head`) keeps 150,000. With a count,
remesh.decimate is unchanged: it reproduces today's hull.ply exactly.

**After (the error bound; the same two surfaces):**
- hull.ply: 150,196 / 150,150 faces; 1,699 / 1,676 vertices differ;
- **the neck, torso and legs: bit-identical** (0 of 106,350 vertices; before 48 moved), and the back of the head (y >
  0.10 L) and the crown (1 vertex at 1.2e-6 L) too;
- what differs is three connected patches, all touching the edit: the face and, through the carve-filled gap between
  the cheek and the side locks, the head's sides to x +-0.69 L (1,609 vertices, the farthest 0.43 L from a changed
  voxel, 48 beyond 0.1 L), and two at the forehead within 0.08 L. That spread is the greedy collapse's own reach.
  Each vertex's quadric carries what it absorbed, so a changed collapse changes its neighbours' order. It stays on the
  surface the edit touches.
- decimation 6 s instead of 12 s (the heap stops at the bound).

**The body fit on the two hulls** (`tools/hull_local/bodyfit.py`: bodypage.save_body, code_body's rings, the spec held,
only the hull differing):

| body array (max change, L) | fixed 150,000 faces | quadric-error bound |
|---|---|---|
| torso rings (torso_P), rows moved | 0.0011, 56 of 56 | 0, 0 of 56 |
| torso centre (torso_cy) | 0.00065 | 0 |
| feet (right / left) | 0.00107 / 0.00032 | 0 / 0 |
| legs (left / right) | 0.00013 / 5.3e-6 | 0 / 0 |
| arms, joints, sole, eyes | 0 | 0 |

Under the budget a face edit moved every torso row, as round 5's trace found (1.6e-4 to 1.4e-3 L per row; the
collar amplified it to 0.035 L). Under the bound the body is bit-identical: the collar's chain is cut at the body.
The hull's per-vertex labels: 0 of 73,402 shared vertices change class or piece.

Test: `charkit/tests/geom/test_hull_local.py` (an ellipsoid with a dent: under the bound nothing moves beyond the dent's
own reach, 0.26 against the surface's 0.24; a budget of the same density moves 59 vertices beyond 0.42, up to 2.27).
A capsule's exact cylinder chains zero-cost collapses from end to end, so the test uses an ellipsoid. The hull has no
such walls: its torso and legs were bit-identical.

Contract (docs/HULL_CONTRACT.md): not breaking. The files, keys and order rules are unchanged; the face count varies
a little. Every mesh reader sees a new mesh once (the stamp changes): code_body, the hair's envelope and flyaways,
bundle.target_pieces.

## Jobs
