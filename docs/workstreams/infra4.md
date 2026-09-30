# Gate tooling round 4 (tool/infra4, 2026-09-30)

Worktree `~/animation-pipeline-infra3`, branch `tool/infra4` from pipeline-3d 9a12d01. The brief, in priority order:
(1) unregistered remeasures slip past the 2x2; (2) a `remote gate` follow that printed another branch's result; (3) the
carry is too conservative; (4) pregate's coverage (sleeve, face); (5) the TRELLIS cleanup (decision 8); (6) k, the
last-bit masked-skin nondeterminism; (7) j, the load sampler at boot.

## State (read first when resuming)

Subset 1 (items 1-3, plus the coordinator's --vrm drawing artifact): done, unit-tested, gated. **The tip f75a550 into
pipeline-3d 3ebc3fb: PASS under K** (`charkit/out/gate/gate_tool-infra4_f75a550_into_3ebc3fb.md`): no check changed,
CPU 1.33x (644 -> 855 s), 611 s. Commits after it: notes only. Items 4-7 not started: "Next steps" below.
Earlier:
- **tool/infra4 9ef6d1a into pipeline-3d 9eba0b0: PASS under K** (pipeline-3d's gate code;
  `charkit/out/gate/gate_tool-infra4_9ef6d1a_into_9eba0b0.md`): no check changed, CPU 1.26x (721 -> 910 s), 658 s.
  Commits after it: the crossed-QA rebase (1766073), the carry's later-commit check and the closure's test-scan fix
  (b7d8dc4), the --vrm look export (ed6f902), notes: gate.py, closure.py, cli.py, qa3d.py and tests.
- Real pairs with this gate code: evalmesh 0c9eb95 into 25b1936 **FAIL** (poke_share, the unregistered remeasure: below);
  look6 bb3fdf1 into 4007276 **PASS** (the face_shadow_* found and scored, as look6's registered gate did).
- evalmesh 0c9eb95 again with the rebase (1766073): hair_folds gone from the found checks (only poke_share), the same
  FAIL; 2x2 209 s, the gate 572 s.
- tmp/infra4-vrm (evalmesh ed0f91a with this branch) into 9eba0b0, the candidate built with --vrm: **PASS, no check
  changed** (the 7 face_shadow moves gone; 720 s). Its measure-code check flagged all 24 parts for this branch's own
  cache.py and the 2x2 (217 s) found every check alike: the kit's bookkeeping (cache, closure, trace, procs, registry)
  is now left out of a part's measure (2a0a39e; the pair then flags nothing, evalmesh and look6 unchanged).
- Carry measurement: the definition rule first measured 2/151 like the file rule; the refusals were the measure guard
  counting cache.py (fixed above) and the unseen-data rule counting infra/*.sh, env examples and engine/*.js (closure:
  only the kinds Blender's C code loads count unread, e02b2c5). The after numbers are in section 3.

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

**Gated with this gate code on the box** (`remote gate tmp/infra4-* --code tool/infra4`):
- **evalmesh 0c9eb95 into 25b1936: FAIL** (the old gate: PASS, poke_share 0.0028 -> 0.0030 "value"). The `poke` part
  flagged (qa3d.py:poke); the 2x2 ran (235 s): poke_share under the old measure reads the new geometry **0.02 FAIL**
  (the old geometry 0.0028 PASS), under the new 0.0028 -> 0.003 PASS. Blocks: "new FAIL under one measure on both
  geometries (the 2x2; its measure changed with no registered step: register a remeasure)". The old poke measure reads
  the final mesh's inner copy and rim, which the new bundle carries; whether that's the intended remeasure (register
  it, and --accept poke_share by name) is evalmesh's and the coordinator's call. 637 s (the old gate 480 s).
- **look6 bb3fdf1 into 4007276: PASS** (the old gate: PASS with the face_shadow_* compared across both changes). Five
  parts flagged; the 2x2 found the six face_shadow_* read differently and scored them: face_shadow_chin_edge FAIL
  under the new measure on both geometries (not a drop), nothing worse under a fixed measure. The same as look6's
  gate once its steps were read (6e5c1f9: PASS, the six remeasured). 645 s.
- Both also listed **hair_folds**: the merged tree's QA read the cached baseline's bundle as 1342 FAIL (the build: 5
  WARN). An artifact of the crossed cell, not a measure change: the bundle's spec names the hair builder's report by
  the folder the baseline was built in, another gate's clone since removed, so the QA fell back to counting dihedrals.
  Fixed (1766073): the crossed QA measures a copy of the bundle whose spec paths point where the build's folder is now
  (`gate.rebased_bundle`, the build folder mirrored so the look export stays beside it). It had been in every 2x2
  on a cached baseline; it showed only now because an unrecorded part's checks are "any check".

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

**Item 2's fix anyway** (remote.py): a gate's report comes back into its own folder
(`charkit/out/remote/gates/<gate id>/`), and `remote gate` / `remote attach` take from it only the report of that branch
at that sha into that head (`remote.gate_report`), copy it into charkit/out/gate and print it by name with its verdict:
`remote gate: exit 1, gate tool_mouth3-5b6fd763: tool/mouth3 (b4f049f) into pipeline-3d (4007276): FAIL, report ...`.
No report of it: it says so and doesn't exit 0. Each job's followed log is also kept by its id
(`charkit/out/remote/jobs/<jid>.log`), whatever the caller redirects to. For agents: never share a redirect file
between two commands (use one per branch or job). Test: test_gate's test_remote_gate_names_its_own_report_never_the_newest.

## 3. The carry: by definition (gate.py `_carry_hits`)

The rule (the default; `gate --carry --rule files` the old one): for charkit's own Python, the move's changed
definitions (H0 -> HEAD) and the branch's (H0 -> the merged tree at H0) must not meet: neither side's changed definitions
among what the other's reach (itself included), in either tree (the move's in HEAD and the new merge, the branch's in
its merge at H0 and the new one). The brief's rule is the first half (the move's among what the branch's reach); the
second half also stops a move that changes a caller of the branch's change. Data files and Python outside charkit stay
file-level against the two builds' closures. Guarded at the QA boundary, where data (the bundle), not calls, joins the
two sides: the move changes a QA part's measuring code or adds a part while the branch's candidate was built; or the
branch changes a measure (registered or not) while the move changes a file the baseline read. Those refuse.

## The coordinator's --vrm artifact: both sides draw from the same export (ed6f902)

A branch changing gltf.py builds its gate candidate with --vrm, and `cli.build` then passed Blender `--vrm` alone: no
NAME.look.glb, so the QA's drawing (render.buildboards.export_of: the look export, else the VRM) drew the candidate
from its full VRM and the baseline from its look export; tool/evalmesh ed0f91a's gate moved 7 face_shadow values with no
change. Now every build writes the look export (unless --no-look), and the VRM besides with --vrm, so every QA draws
the look export. qa.json's measured.draw names the export it drew (`export`), and the gate notes two reports that
drew from different kinds (`gate.draw_exports`). Validation running: ed0f91a merged with this branch, into 9eba0b0.

**After** (the same 151 pairs, 27 reports; 23 pairs no longer merge, so 128 could carry at all):
| rule | all pairs | the next pipeline-3d commit | laptop time |
| --- | --- | --- | --- |
| files (before; also with the narrowed unseen-data rule) | 2/151 (1.3%) | 1/25 | 153 s |
| **definitions, both halves, QA guard (the default)** | **4/151 (2.6%)** | **3/25** | 1071 s |
| definitions, the brief's half only | 5/151 (3.3%) | 4/25 | 1082 s |
| definitions, no QA guard | 4/151 | 3/25 | 1076 s |
What still refuses (a pair can have several): the two changes' definitions meet (120), the move changes a data file
the baseline read (100: charkit/refs/clawd/manifest.json, spec/clawd.json, styles/anime.json, the render shaders,
the references) or the candidate did (87), the QA guard (80, never alone once cache.py is bookkeeping). Today's merges
were overlapping rounds of the same parts (hair, face, garments, the look) and nearly every one edited the manifest or
the spec; a carry across them isn't safe by any rule that reads the files. The two variants are one pair apart; the
default keeps the symmetric half (it refuses a move that changes a caller of the branch's change). The rule costs about
7 s a carry (git trees parsed per blob, memoized).

## Next steps (items 4-7 not started; the survey below is read-only)

**Item 4, pregate's coverage.** The sleeve checks (sleeve_*_rough/spikes/profile, waistband_*, shorts_*, cuff_*: the
`piece_details` part, charkit/pieceqa.py) and the face (`face` face_*, `face_region`: chin_angle, jaw_taper_shape,
tq_cheek_hollow, ...) are QA parts that take a charkit.bundle.Bundle. pregate's evaluator (bodyfit.BodyChecks) makes
bodymeasure's plain-dict bundle (bodyeval.Geometry.bundle), which those parts can't read. Two routes:
1. build a real Bundle from the evaluator's geometry with bundle.Builder (as charkit.faceeval does for the face) and run
   `qa3d.evaluate(B, parts=('piece_details', 'face', 'face_region'))` on it; first check which of the parts' reads the
   Builder bundle carries (objects by name, per-face classes, the look), part by part, timing each;
2. the face through charkit.faceeval, which needs a Blender-cached hair and garments (fit_blender.py --env) once per
   base commit.
Then measure the agreement with a real gate (`pregate --against` tool/face5's gate report, which had
sleeve_profile_rough_L WARN -> FAIL and the chin checks), and list what stays gate-only (the render drawing's
art_*/look, hair_*, poke, mesh, the expressions).

**Item 5, TRELLIS (decision 8).** `git grep -n i3d` outside docs: bucketsync.py 25, scene.py 16, remote.py 12,
bodyeval.py 11, infra/gcp/build.sh 10, geom/parts.py 7, tools/imageto3d/trellis_remote.sh 6, manifest.json 5,
garments.py 4, tools/worktree.sh 3, geom/io.py, gate.py (_link_inputs), flapchains.py, faceeval.py, closure.py 3 each,
and single references in preview, fit_blender, code_base, cli, cache, hair, geom/hull, faceqa, eyeqa, lookqa, sheetqa,
spec/clawd_locks.json, refs/clawd/outfit_graph.json. The 'trellis' authority labels: checks.py AUTHORITY rows,
bodyfit.AUTHORITY and _iou_term calls, facefit's terms, the manifest's "trellis" entries. Order: (a) a full build with
charkit/out/i3d moved away, and grep the produced references' stamps for i3d paths: what still reads it; (b) stop
shipping it (bucketsync's i3d handling, remote.py's seed and gate links, gate._link_inputs, tools/worktree.sh,
build.sh); (c) rename the i3d module (the generated-GLB loader and aligner) and the 'trellis' labels (the manifest's
authority names are data the QA reads: a label change may need a measurement step for face_shape_* and shape_iou*);
(d) retire trellis_remote.sh, keep tools/imageto3d/trellis_ext. Gate it: the renames must move no value.

**Item 6, k (masked-skin nondeterminism).** infra.md "Round 2" item (c) cause 2 has the probe. First, from two builds
of one commit with --cache off (infra3's i A/B: charkit/out/i_before and i_after on the box), compare the bundles'
array hashes: if only o/clawd_skin/masked/* differ, that's the case on the default spec; then the probe.

**Item 7, j (the load sampler at boot).** boxjob.install_sampler writes the per-minute user crontab line as the box
owner (jobs run as the owner through the as-owner wrapper); add an `@reboot` line the same way (the same CRON_MARK),
install it with a no-op job on each box (`remote run true`, `remote --box render run true`), and check `crontab -l` as
the owner on both. No VM metadata or startup-script changes.
