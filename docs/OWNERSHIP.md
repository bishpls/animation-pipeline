# Who owns what (charkit workstreams; updated 2026-09-30)

One owner per area. A workstream edits only its own areas. A change it needs elsewhere goes through its notes and the
integrator. Shared files are edited only in the named sections.

| area | files / functions | owner (branch) |
|---|---|---|
| hull: carve, labels, determinism | `geom/hull.py` (except below), `geom/det.py`, `geom/remesh.py`, `geom/volume.py` | hull (tool/hull-det merged; tool/hull-limbs for `limb_image` and rounded's limb depth) |
| face carve on the hull | `geom/hull.py: carve_face` | face |
| head and face geometry | `code_base.py`, `geom/headfit.py`, `geom/headgeom.py`, `faceregion.py`, styles `face` | face (tool/face) |
| eyes | `eyes.py` (eye functions), `eyetex.py`, `eyeqa.py`, styles `eyes` | face (tool/face) |
| mouth and expressions | mouth and expression-key functions (`eyes.py`, `base_anime.py`), `brows.py`, `exprqa.py` | mouth (tool/mouth) |
| hair | `hair.py`, `geom/hairpieces.py`, `hairlab.py`, styles `hair` / `hair_pieces` | hair (tool/hair3) |
| lower garments | `garments.py`: skirt, panel/flap, hem_cut, axis/symmetry, pleats, stepped band, boots template | skirt (tool/skirt) |
| upper garments | `garments.py`: top/jacket, bodice, waistband, collar, bow, puff sleeve, cuff, shorts, `arm_points`; `pieceqa.py` | garments2 (tool/garments2) |
| garment hull sampling | `garments.py`: hull_pieces, shell_points, shell_patches, STRAY, _knn_mean | integrator (was tool/garment-sampling) |
| body shape | `code_body.py` (torso, limbs, feet), `bodypage.py`, `detailqa.py` | body (done; limb depth via hull) |
| rig | `code_body.py` joints/weights, `rigweights.py`, `rigstage.py`, `rig.py`, gltf constraints | rig (tool/rig) |
| motion | `motion.py`, `motionqa.py`, `motionchecks.py`, `springs.py`, `clips/` | motion (tool/motion) |
| look | `shade.py`, `faceshade.py`, `look.js`, `lookqa.py`, styles `look` | look (tool/look2) |
| boards and render loop | `qa.py` render_view/render_views, `scene.py` boards, `boards/*` | integrator (render-batch merged) |
| accessories | `accessories.py`, `accqa.py` | accessories (tool/accessories) |
| measurement suites | `artifactqa.py`; `perceptual.py` | artifacts; perceptual |
| infrastructure | `manifest.py`, `cache.py`, `gate.py`, `remote.py`, `infra/gcp/*`, `tools/*` | integrator / infra |
| specs | `spec/*.json`: each owner edits only its sections; `clawd.json` = `clawd_body_pieces.json` (a test enforces it) | shared |
| registries | `registry.py` (the mechanism); a part registers in its own module (`@qa_part`), a step in `charkit/steps/<module>.py` (docs/CHARKIT.md, "Registering a QA part or a measurement step") | infra; each part and steps file is its module's owner's |
