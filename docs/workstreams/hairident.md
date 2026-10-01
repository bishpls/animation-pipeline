# hairident: cross-view lock identity for the hair (tool/hairident)

Worktree `~/animation-pipeline-hairident`, branch `tool/hairident` from tool/hairshell3 feee7702 (the lock-shell code:
det fit, per-vertex skin clearance, speckle hair_noise). Brief: `~/animation-pipeline-3d/charkit/out/coord/brief_hairident.md`
(read all of it: step 0 done by tool/hairtruth; the held-out-view check; the shadow-edge check's clean reading from
tool/hairtruth-art is this round's to land). Harness `tools/hairident/`, outputs `charkit/out/hairident/`.

## State
- Merged pipeline-3d 241f0547 (the hair truth without the clips; conflict in charkit/steps/qa3d.py: both sides' steps
  kept) and tool/hairshell3 08afe00f (the default switch reverted: no lock_shells, no shade_ellipsoid on the default).
- Step 1 (the labelling tool) in progress.

## Plan (the brief's order)
1. `python -m charkit label serve TASK.json` (charkit/label.py, generic) + the hair identity task (~20 locks: side locks,
   back flicks; tools/hairident/mktask.py) -> hand the page to the coordinator.
2. While Michael labels: the ribbon template test (flat section, twist, tip curl) on the pilot's locks.
3. The joint fit with assignment across views; scored on Michael's held-out links + held-out views; sweep optimize.
4. Review page, the default switch (shells from the cross-view fit) with every hair check, pregate, gate.

## Jobs
None.
