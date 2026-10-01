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

## Michael's first pass (2026-10-01, ~13 min): 21 / 21 locks; views accepted 35, fixed 3, hidden 22, unsure 3
His flag (via the coordinator): lock 7's profile lock exists inside the back mass the splitter never segmented, so the
page had no region to click: some 'hidden' / 'unsure' answers are "present but unsegmented". Asked: (1) a point mark
answer in the tool, a short second pass (every unsure; every 'hidden' where the hull's projection says mostly visible);
point marks scored as location truth; (2) a lock-delineated hair reference (Michael authorised up to ~4 image calls,
n=2, same model and tooling, ledger): the head turnaround's three-quarter, profile and back redrawn at the same pose and
scale with every lock's boundary inked, not exploded; refcheck before it is an authority; if it passes: register,
re-split, fold the back-mass locks into the second pass.

### The lock map reference: the pass rule (declared before the calls)
Prompts: `charkit/out/hairident/refgen/prompts.py` (`hair_lock_map_lines`: the sheet redrawn with the hair one flat
orange cut into closed locks by ink lines; `hair_lock_map_colours`: each lock its own flat colour), ref
head_turnaround, gpt-image-2.5-sunburst 2560x1440 high n=2. History: tool/hair5's `hair_lock_lineart` failed (open
strokes, 10-22 closed regions per view, no structure the turnaround lacks; its prompt told it NOT to cut the smooth
masses). A view passes when all hold (three-quarter, profile, back; front reported):
1. silhouette: hair IoU >= 0.80 against the turnaround's hair on the design grid after registration (shapetruth's:
   the eyes, then scale +-4%, shift +-0.04 L), the views' scales within 5% of each other;
2. structure the turnaround lacks: the back view's hair below the buns cut into >= 6 closed regions of >= 0.01 L^2,
   >= 5 of them reaching >= 0.3 L up from the hem; the profile's back mass (behind the side locks) >= 4 such regions;
3. agreement with the drawn locks: each of the back's 7 hem-flick truth regions >= 70% inside one region of the
   redraw, >= 5 of the 7 in different regions; the turnaround's drawn lock lines recalled >= 0.5 within 2.5 px.
Registered (structure only; placement stays the turnaround's) for the views that pass; else reported, not registered.

## Plan (the brief's order)
1. `python -m charkit label serve TASK.json` (charkit/label.py, generic) + the hair identity task (~20 locks: side locks,
   back flicks; tools/hairident/mktask.py) -> hand the page to the coordinator.
2. While Michael labels: the ribbon template test (flat section, twist, tip curl) on the pilot's locks.
3. The joint fit with assignment across views; scored on Michael's held-out links + held-out views; sweep optimize.
4. Review page, the default switch (shells from the cross-view fit) with every hair check, pregate, gate.

## Jobs
None.
