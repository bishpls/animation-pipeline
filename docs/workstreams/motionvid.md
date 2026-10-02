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
- Started 2026-10-01 late. Sample build: the default spec at 348397e7 on the render box with boards
  (`charkit/out/motionvid/base`).
