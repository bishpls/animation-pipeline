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

## State
- Code: `charkit/romvideo.py` (`python -m charkit rom video BUILD`, dispatched from cli.py's `rom`: rom.py untouched,
  so the rom QA part's measuring code doesn't change), `charkit/tests/test_romvideo.py` (quaternions, slerp, schedule,
  poses as local rotations composed back, the extra nodes' hook), `charkit/reviewpage.py` (a `videos` section with
  chapter buttons). Box env files copied from motion1's worktree (gitignored).
- Clips: rom.json's 27 poses (rest skipped) + motion QA's 7 (charkit.evalmesh.POSES, as mqa_*). 60 frames each
  (1 / 0.5 / 1 s, smoothstep); the out is the in reversed, so 24 renders + the shared rest per clip.
- Renderer: gpu.Renderer subclass rewriting the vertex streams per frame, live normals on the posed surface, the head
  light in the posed head's frame (look.js). Node constraints: rom.Rig.nodes.deform when the codebase has it
  (motion1's rom.Rig does), else reported as not evaluated.
- Encoding on render2: its ffmpeg's NVENC fails (driver), so libx264 (system ffmpeg, an external process); the Mac
  would use VideoToolbox.
- Test 1 (motion1's m1_base on render2, 4 clips): 240 frames, 97 renders, 0.88 s a render, 0.38 s an output frame
  (skin 0.26, upload 0.11, render+normals 0.51 a render); 716,700 vertices skinned. `charkit/out/motionvid/test1`.
- Sample build: the default spec at 348397e7 on the render box with boards (`charkit/out/motionvid/base`, job
  build-motionvid-1001-204838-49a2 on render2).

## Next
1. The sample run on the base build (all clips), review page, check frames.
2. The constraint path tested on motion1's m1_s2 (40 constrained nodes) with tool/motion1 merged into a throwaway
   branch (not committed to tool/motionvid).
3. Pregate on the box, gate into pipeline-3d.
