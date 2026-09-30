# Produced references stamped by what they read (tool/stamp-spec)

State: in progress. Numbers below are from the build box unless marked.

## The bug

Two box copies at the same code held different outfit masks and graphs, and so different hulls, under one stamp:
masks `074d9a3f` / `bc0f48dc` under `57c5e3f0`, hull `.npz` `996c4195` / `7524e943` under `a3d52ea2`.

## Which cause: the TRELLIS field, not the spec, not staleness

The outfit reads a gitignored file no stamp covered: the TRELLIS field
`charkit/out/i3d/ext/runA/clawd_3dstyle_s1_field.npz` (`outfit.find_field`, 17 MB, sha `42ff8718`). With it, the
pieces are placed by the field's votes; without it, by landmarks (`landmark_prediction`). Whether a copy has it depends
on how the copy was made:
- a worktree made by `tools/worktree.sh` has no `charkit/out/i3d`, and its box sync (`rsync --delete`, with
  `charkit/out/i3d/***` included) deletes the i3d it was seeded with;
- a gate's clone takes its i3d from the gated worktree's box copy, else `/srv/work/repo/charkit/out/i3d`, which doesn't
  exist.

**Survey of the box's 23 copies (2026-09-30 01:20):** masks `074d9a3f` in every copy with the field (13), `bc0f48dc` in
every copy without it (10). No exceptions.

**Controlled run, one copy, one code (pipeline-3d `6ca18da`), `charkit outfit` then the hull's fast path:**

| run | spec | field | masks | graph | hull `.npz` |
|---|---|---|---|---|---|
| A | clawd.json | yes | `074d9a3f` | `659eebc6` | `996c4195` |
| B | clawd.json | no | `bc0f48dc` | `59380eb7` | `7524e943` |
| C | clawd_body.json | yes | `074d9a3f` | `971d5e3b` | `996c4195` |
| D | clawd_body.json | no | `bc0f48dc` | `82cd7456` | `7524e943` |

- (a) spec dependence: the masks don't depend on the spec (A = C, B = D). The graph does, only in its `comparison`
  (the knob deltas of matched entries) and `generated_by.command` (the spec's path). The matched draft-to-hand pairs
  and the missed list, which are all the QA (`bodymeasure.piece_map`) and bodyfit read, are identical for clawd.json
  and clawd_body.json: their garments have the same names, kinds, sides, bones and region bones.
- The hull follows the masks: A = C (`996c4195`, glb `b2ccb711`, pieces `7b1836ab`: the pipeline-3d and look copies'),
  B = D (`7524e943`, glb `41ddb090`, pieces `bcd6a376`: the bis and default-spec copies'). It reads the graph's pieces
  and skeleton, not its comparison.
- (b) staleness through STAMP_DEPTH=1: no. Run A reproduces the pipeline-3d box copy's masks and graph byte for byte
  (`074d9a3f`, `659eebc6`), and run B the bis copies' (`bc0f48dc`, `59380eb7`).
- (c) what differs between copies: yes, the field. `--boards` can't matter: `manifest.produce` runs in `cli.resolve`,
  before anything reads the build flags, and the producers take none.

## The fix

Each produced reference in `charkit/refs/clawd/manifest.json` declares what it is made from, and
`manifest.stamp()` digests exactly that, with the producer's code (one import deep, as before), its own entry (its
command and declarations) and the tracked references' sha256s (as before):

| | outfit_masks | hull | hair_layers |
|---|---|---|---|
| `reads_files` (each match by sha256, none if absent) | the TRELLIS field, `outfit_notes.json`, the rig's `build/*`, `rig.json`, `base.png` | | |
| `reads` (a produced one by its stamp, another by its entry's data) | rig, body_turnaround, trellis | outfit_masks, body_turnaround, body_turnaround_back34, head_turnaround, head_construction | outfit_masks, hair_breakdown, body_turnaround |
| `reads_spec` | name, ref, eyes.x, the garments' and accessories' roles | name, ref, style, eyes.x | name, ref, eyes.x |

- **Files** are the part that fixes the bug. The field is gitignored; the notes and the rig are tracked but had no
  sha256 in the manifest, so an edit to them rebuilt nothing either. A read reference's entry counts by its data
  (path, hash, scale, layout, views), not its prose (role, cautions, provenance, checks).
- **Spec sections, kept as far as they change an output.** `eyes.x` and `ref` set the frame and the pictures the
  masks are measured in: clawd.json with `eyes.x` 0.172 (not the rig's 0.168) gives masks `4fe07bb3`, every one of
  the 104 on a grid of another size. The garments don't change the masks or the hull (A = C, B = D above); they change only the
  graph's `comparison`, whose matched draft-to-hand names the QA's piece checks read (`bodymeasure.piece_map`, from
  the graph beside the produced masks). So the stamp takes only what that matching reads: each garment's name, kind,
  side, bone and region bones, each accessory's name, kind, side and az (`outfit._role`), not a knob. The four Clawd
  specs have the same roles, so they share every stamp; a flare, a boot's region extent (bodyfit's knobs), a body or
  face knob move none. Dropping the garments altogether would leave the comparison either against a fixed spec (a
  hidden file input) or empty (the piece checks lose the hand mapping).
- **The producer runs on the build's own spec, cut down to those sections** (with those of what it reads), written to
  `PATH.spec.json` and passed as the command's `{spec}`; `charkit/spec/clawd.json` is no longer named. What a
  producer doesn't declare, it can't read. The produced graph's comparison therefore has the same matches, misses and
  extras as one made from the whole spec (checked on clawd_body_pieces: 23 matched pairs, equal to clawd.json's and
  clawd_body.json's), but no knob deltas, and its `knob_only` notes don't see knobs (a skirt's `panel`) the cut-down
  hand list lacks. Nothing reads either (only outfit.md); `python -m charkit outfit SPEC` still gives the full one.
- The stamp's parts go to `PATH.stamp.json` (code, entry, refs, each read's stamp or digest, spec, each file and its
  sha256), and a rebuild logs which field it read or that the copy has none.
- A rebuild runs under a lock (`PATH.lock`) and unshares hard links first (`cache.unshare`, as before).
- A copy holding masks made without the field (or by older code) rebuilds them on its own once the field arrives:
  its stamp no longer matches (`test_a_declared_file_coming_or_going_makes_it_stale`).

## One version per copy, rebuilt on change (not variant folders)

Measured on the build box (32 vCPU, load 33-50 from other gates), per produced reference, from runs A-D:

| reference | wall | CPU | size |
|---|---|---|---|
| outfit masks + graph (`charkit outfit`) | 72-122 s | 62-138 s (with the field: 136-138 s) | 7.2 MB (6.5-7 MB of it `outfit.png`) |
| hull (fast path) | 172-216 s | 157-198 s | 7.7 MB |
| hair layers | 32 s | 37-39 s | 3.0 MB |
| **all three** | **4.6-6.2 min** | **4.3-6.3 min** | **18 MB** |

- **Rebuild on change** costs those 4.6-6.2 minutes each time one copy switches between specs that differ in a declared
  section, and nothing otherwise. The four Clawd specs (clawd, clawd_body, clawd_body_pieces, clawd_code) don't differ
  in any: their cut-down specs are identical (`test_the_clawd_specs_share_their_produced_references`), so they share
  one outfit, one hull and one hair-layer set, and switching among them rebuilds nothing. A body or face tune, and
  bodyfit's garment knobs (a flare, a boot's region extent), don't move a stamp either.
- **Variant folders** (keyed by the cut-down spec's digest) would cost 18 MB a variant, and need every reader to find
  the variant: `bodymeasure.piece_masks`, `qa3d.hair_layers_masks` and `garments.drawn_extent` read the manifest's
  path directly, and the hull's path reaches about eight modules as the spec's `hair.shape.glb` (garments, scene,
  bodyeval, bundle, fit_blender, cli's geom and pieces hair, geom.parts), which `produce()` would have to rewrite. Those
  are outside this branch's files (garments.py is tool/body's), and today they would buy nothing: every Clawd spec
  maps to the same variant.
- Picked: rebuild on change, under a lock (`PATH.lock`), so parallel builds of one spec in one copy build it once.
  What it doesn't cover: two builds running at once in one copy on specs that differ in a declared section. The second
  rebuilds in place while the first may still read. No current spec pair does that; if one appears, variant folders
  are the fix, with the three readers above going through a `manifest.path(spec, rid)`.
