# Gate tooling round 4 (tool/infra4, 2026-09-30)

Worktree `~/animation-pipeline-infra3`, branch `tool/infra4` from pipeline-3d 9a12d01. The brief, in priority order:
(1) unregistered remeasures slip past the 2x2; (2) a `remote gate` follow that printed another branch's result; (3) the
carry is too conservative; (4) pregate's coverage (sleeve, face); (5) the TRELLIS cleanup (decision 8); (6) k, the
last-bit masked-skin nondeterminism; (7) j, the load sampler at boot.

## State (read first when resuming)

Subset 1 (items 1-3) in progress. Code for item 1 done and unit-tested; real-pair gates on the box next.

## 1. Unregistered remeasures (charkit/codediff.py, gate.py)

**The gap.** The gate ran the 2x2 only for checks matching a registered measurement step (MEASUREMENT_STEPS). Twice
today a measure changed with the geometry and nothing was registered: tool/evalmesh 0c9eb95 changed `qa3d.poke`
(poke_share reads the surface layer), and tool/look6's steps sat in a second literal the registry never read. The gate
then compared poke_share across both changes at once (0.0028 -> 0.0030 PASS, "value").

**The fix.** After the compare, the gate compares each QA part's measuring code between the baseline's tree and the
merged tree (`codediff.measure_changes`, no import of either tree's code):
- a part's measuring code is what the build cache's code walk reaches from the part's function, plus the QA's shared
  code every part runs through (qa3d.Design, the check naming, checks.authorize, bundle.Bundle/Obj/load);
- the walk is cache.code_units in a new "fine" mode: each top-level constant is its own unit reached by name (so a
  threshold like FACE_EXPECT reaches the parts that name it, not every part of qa3d.py), imports left out of `<top>`.
  Cache keys use the old walk, unchanged (the same digest before and after, checked);
- cache.code_units reads any tree: `cache.code_tree(Tree(root=...) | Tree(repo, rev))` (a worktree, or a git commit or
  tree id read with git, nothing checked out); parsed modules memoized per blob across trees.

When a part changed and the geometry changed, the gate runs the 2x2 (the crossed QAs, as for a registered step). The
checks whose two measures read differently on the same geometry (`measure_moved`: base vs new-on-old, or old-on-new vs
candidate) are the unregistered remeasures; they get 2x2 rows (`detected`) and block as registered ones do (a drop to
FAIL under one fixed measure, a flag check worse, a crossed cell unmeasured), with "its measure changed with no
registered step: register a remeasure". Their direct comparison is not relaxed (nothing registered). With the geometry
unchanged, the moved checks of the changed parts are listed as the measure's own moves. The report has a new section
"Measuring code changed with no registered step" (part, the code that changed, the checks). qa.json now records each
part's checks (`measured.part_checks`), so later gates attribute checks to parts exactly; older builds fall back to the
part's prefix, else "any check".

**Detection on real pairs (static, laptop, 3-9 s each):**
| pair | parts flagged | the code |
| --- | --- | --- |
| evalmesh 0c9eb95 into 25b1936 | poke | qa3d.py:poke |
| look6 bb3fdf1 into 4007276 | look; artifacts, details, hair_noise, scalp | the design light (designlight.py, anime_head.vertex_normals); qarender.view |
| look6 6e5c1f9 into 25b1936 (registered) | the same | the same |
| infra-auth c488918 into 4007276 | none | |
| mouth3 1c282c6 into 25b1936 | eye_views, face, face_region, sheet_expr | expressions.PRESETS, exprqa (its steps registered in steps/qa3d.py) |
| face5 2d3f594 into 25b1936 | every part | code_base.head_sections (the design side reaches it) |
| hairtag d4d9033 into 25b1936 | none | |

Before the fine walk, bundle.py (the Blender-side export evalmesh also changed) flagged all 24 parts, and qa3d.py's
FACE_EXPECT all qa3d parts.

## 2. The follow that printed another branch's result

Not remote.py's lookup: neither remote.py nor boxjob.py looks for "the newest report". The mouth3 agent's output
(gate-mouth-0930-140348-ac99) and tool/infra-auth's `remote gate` both redirected to the same file,
`<the session's shared scratchpad>/gate.log`. mouth3's `>` truncated it while infra-auth's command was still writing:
its first lines are mouth3's (the job start), then 172 NUL bytes (infra-auth's write offset past the truncated end),
then infra-auth's result and its "report in ~/animation-pipeline-infra-auth/charkit/out/gate". The job itself was
mouth3's (its box log: tool/mouth3 b4f049f into 4007276, PASS) and its report came back to the mouth worktree.

## 3. The carry

**Before (pipeline-3d 9a12d01's gate code):** every real gate report of 2026-09-30 with closures (27, branches not
tmp-*), carried to each later first-parent pipeline-3d commit up to 9a12d01: **151 pairs, 2 carried (1.3%)**.
(harness: carry_rate.py in the session scratchpad; `gate.carry(tip, into=T, write=False, run_tests=False)`, a carry
waiting only on tests counted as carried.)

## Next steps

- Gate the real pairs with this gate code (`remote gate ... --code tool/infra4`): evalmesh 0c9eb95 into 25b1936, look6
  bb3fdf1 into 4007276.
- Item 2: `remote gate` names its own report (by the job's gid, branch and sha), a local copy of each job's log by JID.
- Item 3: the definition-level carry rule; the after numbers.
