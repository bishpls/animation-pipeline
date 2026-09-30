# Face labs (docs/workstreams/face.md)

Fast loops for the head's eye region and neck, run from the face worktree's root with the venv
(`~/animation-pipeline/.venv/bin/python tools/face_labs/X.py ...`). Seconds a try instead of a box build.

| script | what |
|---|---|
| `eye_lab.py [json face configs...]` | assembles the head sections (`headfit.assemble`) per style `face` config and prints the eye region's numbers on the sections: hollow and cheek lead down the eye's column, predicted profile/three-quarter eye widths, a local concavity map, the head's sheet checks. `SHADE=out.png` also writes `shade.py`'s shading of each. A config may carry `"terms": [...]` to switch headfit terms off. |
| `shade.py` | numpy shading of a head's sections (z-buffer, the boards' key light): two-tone toon and Lambert, front / three-quarter / 70 degrees. Overstates what geometry does on the face front (the build shades it with the SDF map and proxy normals), but shows edges and rings. |
| `forward_lab.py` | where the eye window moves the face forward of its natural surface (a map over x and z). `CFGS='cfg1\|cfg2'`. |
| `neck_lab.py GEOM_DIR` | the neck's crease as the QA measures it (`faceregion.crease_of`), on the local assembly (`character.assemble` with a build's `head_code.npz`/`body_code.npz`) subdivided once with `charkit.subdiv`, as the bundle's eval mesh is: reads the box build to within 2 degrees. `RAW=0,90` / `RINGS=0.0,-0.04` dump the base mesh's rows. |
| `neck_sil.py BUILD...` | the neck's silhouette per row, ours against the body sheet's (front skin run half-width, profile front edge). |
| `chin_cmp.py OUT.png BUILD...` | the chin and neck from the builds' face boards beside the head sheet's views at the same px per L (front, three-quarter, profile). |
| `face_views.py`, `render_slot.py BLEND OUTDIR` | close renders of a saved build's face and neck (hair shown and hidden), in a build slot. The hair lacks the boards' pass in these. |
| `face_page.py BASE AFTER OUT ...` | the workstream's review page (see its docstring). |
| `jaw_lab.py OUT.png BUILD` or `--geom GEOM_DIR` | the jaw checks (`faceregion.jaw`) on a build's bundle, or on a local assembly of a build's `head_code.npz`/`body_code.npz` (the skin alone, subdivided once; 30 s): the design's classes beside ours in the boards' camera and a level one, the face region tinted, the chin point and jaw-line columns marked. `--geom` also prints `qa3d.face_folds`' rest count and the join's crease. |
| `carve_lab.py OUT_DIR [SPEC] [KEEP ...]` | the hull's face carve (`hull.carve_face`) with its detail: every voxel it would take, how far in front of the face, hair or not, kept or not, by region (the fringe, the sides, the jaw), for a few `hair_keep` margins. Heavy: run it on the build box (`infra/gcp/build.sh run . 'python tools/face_labs/carve_lab.py charkit/out/carve_lab'`, then `fetch`). |
| `jaw_page.py OUT_DIR BUILD [BUILD ...] [--labels a,b] [--bare DIR,DIR]` | the chin and jaw review page: the head sheet beside the builds' face boards at one px per L (whole heads and close on the chin), cut round the eyes as each side's eyes project, and the jaw, face region and gate numbers per build. |
| `decision_views.py OUT_BASE BUILD --call C --option O --settings JSON` | one option of a face taste call (eye flatness, brow) as a picture (the head sheet over the build's face boards, cut round the eyes) and a json of its numbers. |
