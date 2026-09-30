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
