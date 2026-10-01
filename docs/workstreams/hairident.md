# hairident: cross-view lock identity for the hair (tool/hairident)

Worktree `~/animation-pipeline-hairident`, branch `tool/hairident` from tool/hairshell3 feee7702 (the lock-shell code:
det fit, per-vertex skin clearance, speckle hair_noise). Brief: `~/animation-pipeline-3d/charkit/out/coord/brief_hairident.md`
(read all of it: step 0 done by tool/hairtruth; the held-out-view check; the shadow-edge check's clean reading from
tool/hairtruth-art is this round's to land). Harness `tools/hairident/`, outputs `charkit/out/hairident/`.

## State
- Merged pipeline-3d 241f0547 (the hair truth without the clips; conflict in charkit/steps/qa3d.py: both sides' steps
  kept) and tool/hairshell3 08afe00f (the default switch reverted: no lock_shells, no shade_ellipsoid on the default).
- **Step 1 done: the labelling tool** (`charkit/label.py`, `charkit/labelui.html`, `python -m charkit label serve
  TASK.json` / `label status TASK.json`; tests `charkit/tests/test_label.py`; headless driver `tools/label/drive.mjs`:
  Chrome's DevTools protocol over Node's own WebSocket, real key/mouse events, screenshots). Generic task format
  (charkit-label-task/1: views, regions as index masks or polygons, items with a home region and per-view proposals
  with reason and confidence); answers (charkit-label-answers/1) written on every click (atomic replace) with a history
  (undo), resume at the first open item; 127.0.0.1 only.
- **The hair identity task** (`tools/hairident/mktask.py`, regions `tools/hairident/regions.py`): 21 locks in three
  groups (8 side locks, 6 side flicks and strands, 7 back hem flicks); regions per view = the lock truth's named locks
  (side_locks, lower_back, flyaways) + the splitter's locks over the rest of the side-lock / lower-back hair (>= 0.006
  L^2; the three-quarter, without family masks: from 0.25 L above the eye line down); proposals from the hull's
  projection (lockshell.envelope_points on round 2's context `charkit/out/hairident/ctx_r2.pkl`, copied from
  hairshell2's ctx_shells_r.pkl; visible within 0.04 L of the front-most envelope), tip heights, the splitter's layer
  ranks, and the lock truth's names as a second opinion (where they disagree the confidence drops). Inputs:
  `charkit/out/hairsplit/inputs.pkl` (the splitter's cached inputs, copied from ~/animation-pipeline-hairshell).
- **Michael's page:** server running (PID in `charkit/out/hairident/label/server.pid`, log `server.log`) at
  http://127.0.0.1:8770/ ; answers -> `charkit/out/hairident/label/answers.json`. Restart:
  `python -m charkit label serve charkit/out/hairident/label/task.json --port 8770`.
- Tested: 5 server tests (save at once, atomic, resume, undo, skip, bad input refused, 127.0.0.1); screenshots of every
  state (start, accept, pick mode, hover across views, picked, unsure, skip, undo, back, resume after reload, final
  screen; 1600x1000, 1440x900, 1280x800) in `charkit/out/hairident/label_test/shots*`; a keys-only pass of all 21 locks
  (Enter each) 12 s.

## Plan (the brief's order)
1. `python -m charkit label serve TASK.json` (charkit/label.py, generic) + the hair identity task (~20 locks: side locks,
   back flicks; tools/hairident/mktask.py) -> hand the page to the coordinator.
2. While Michael labels: the ribbon template test (flat section, twist, tip curl) on the pilot's locks.
3. The joint fit with assignment across views; scored on Michael's held-out links + held-out views; sweep optimize.
4. Review page, the default switch (shells from the cross-view fit) with every hair check, pregate, gate.

## Jobs
None.
