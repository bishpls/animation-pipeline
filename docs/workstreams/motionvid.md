# motionvid: the motion video check (tool/motionvid)

Worktree `~/animation-pipeline-motionvid`, branch `tool/motionvid` from pipeline-3d 348397e7. Brief: the coordinator's
launch message (Michael, 2026-10-02: "a basic motion video check showing the animations we're testing on-rig").
Outputs: `charkit/out/motionvid/`.

## Task
`python -m charkit rom video BUILD [--poses ...] [--out DIR]`: the export's rig animated through the ROM poses (rest ->
pose -> rest, eased, 1 s in, 0.5 s hold, 1 s out, joints slerped), the toon renderer at one fixed scale, front and
three-quarter (+ profile) side by side, labelled; 24 fps H.264 yuv420p mp4 + a contact sheet at the holds. Test
animations from motion1 as extra clips if they exist as data. A unit test for the interpolation; a review page.
Report-only: no build output changes. Pregate, then gate into pipeline-3d.

## State (2026-10-01 ~21:50)
- **The command (any build dir):** `python -m charkit remote --box render2 run --fetch DIR rom video BUILD --out DIR`
  (on a box that holds BUILD; `--box auto` prefers a render box only for builds with boards, so name render2), or
  on the box itself `python -m charkit rom video BUILD [--out DIR]` (DIR defaults to BUILD/rom/video). Writes
  rom_video.mp4, contact.png, poster.jpg, video.json, page.json and page/index.html. `--rom ROM.json` adds the ROM
  suite's FAIL/WARN per clip (auto: BUILD/rom/rom.json). `--head-light rest` draws the face as the ROM boards do.
- Code: `charkit/romvideo.py` (dispatched from cli.py's `rom`: rom.py untouched, so the rom QA part's measuring code
  doesn't change), `charkit/tests/test_romvideo.py` (9 tests: quaternions, slerp, schedule, poses as local rotations
  composed back, the extra nodes' hook), `charkit/reviewpage.py` (a `videos` section: poster, chapter buttons).
  Harnesses: tools/motionvid/{probe,parity,make_page}.py. Box env files copied from motion1's worktree (gitignored).
- Clips: rom.json's 27 poses (rest skipped) + motion QA's 7 (charkit.evalmesh.POSES, as mqa_*). 60 frames each
  (1 / 0.5 / 1 s, smoothstep); the out is the in reversed, so 24 renders + the shared rest per clip.
- Renderer: gpu.Renderer subclass rewriting the vertex streams per frame, live normals on the posed surface, the head
  light in the posed head's frame (look.js). Node constraints: rom.Rig.nodes.deform when the codebase has it.
- Encoding on render2: its ffmpeg's NVENC fails (driver too old for this ffmpeg), so libx264 (the system ffmpeg as an
  external process); a Mac would use VideoToolbox.

## Numbers
- Sample (default spec at 348397e7, built on render2 with boards: `charkit/out/motionvid/base`; ROM suite
  `charkit/out/motionvid/base_rom`): 34 clips, 2040 frames (85 s), 817 renders; 0.405 s an output frame, 0.947 s a
  render (skin 0.28, upload 0.11, normals + 3 views 0.55); 716,700 vertices; wall 830 s. Video 8.9 MB.
  `charkit/out/motionvid/sample/` (page: sample/page/index.html, built by tools/motionvid/make_page.py).
- Parity with the ROM boards (tools/motionvid/parity.py; `charkit/out/motionvid/parity`): the slerped and composed
  key reproduces the solve to 1e-15; with the boards' head light ours is within 1-2 levels (raise_side_90 front: 29 on
  0.0004% of pixels); the posed head light changes the face only (0.013-0.035% of pixels; up to 68 levels).
- Finding: a bowed head (squat, head_nod, spine_bend) side-lights the face under the runtime's head-space light
  (look.js applies the head's whole rotation; the SDF reads the azimuth in head space): a 35 deg nod moves the front
  key light from 30 to 65 deg off the face's front. A shadow blob by the nose. Asked of Michael: A keep / B yaw only.
- Node constraints on motion1's m1_s2 (40 nodes: rotation 36, roll 4): honoured with tool/motion1 merged (a throwaway
  branch, deleted), "not evaluated" without (`charkit/out/motionvid/m1s2_{nodes,plain}`, m1s2_compare.png).

## Gate
- Merged pipeline-3d 3144b1f6 (hairident) cleanly as ff45723e. Pregate on build2: PASS (0 moved, 0 blocking).
- Gate on build2 (job gate-motionvid-1001-214656-81d3): tool/motionvid 9038e7f9 into pipeline-3d 3144b1f6 **PASS**
  under K: nothing blocks; reported: the declared part's count (55 vs 47, pre-existing) and build CPU like for like
  1252 -> 1150 s (0.92x); the candidate built cold (cli.py, reviewpage.py, romvideo.py read by the build); the tests
  pass (test_romvideo.py, test_reviewpage.py among them). Report:
  `charkit/out/gate/gate_tool-motionvid_9038e7f9_into_3144b1f6.md`. Later commits: notes only.

## Next
1. The final run on the production build the coordinator names (the command at the top of State), then
   `python tools/motionvid/make_page.py`-style extras only if wanted (the tool's own page is complete).
2. Open for Michael: the face light on a bowed head (A keep look.js's full head-space light / B yaw only).
3. Possible follow-ups: the motion QA clips with the cloth baked (charkit.sim.bake), spring chains once the export
   carries VRMC_springBone.
