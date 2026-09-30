# The authored body, fitted to the hull (plan)

## Checkpoint: end of round 3 (2026-09-29). Start here.

The branch, gates, numbers, open items and gotchas are in `docs/workstreams/garments.md` (its checkpoint section);
the body and the garments share `tool/body`.

Round 5 (2026-09-30), body-side: the boots are a template on the leg joints (the two ankle joints made mirror images
about the legs' midline, x 0.0107 L: the body's legs are symmetric about it, not about 0), hiding the leg and foot
inside; the top eases onto the waistband. Details in garments.md's round 5 checkpoint.

Round 4 (2026-09-30), body-side: the collar now seats on the design's neckline per azimuth (below tool/face's cut, so
it holds on their slender neck); the skirt clears the hands, forearms and wrist bands at bind (`clear_hands`, tool/rig's
finding). Details in garments.md's round 4 checkpoint.

The body-side state:
- **Chest in profile:** `body_profile_chest` is 0.036 L flatter than the design (WARN). What remains is the bow's
  very top and bottom rows (z −0.65 and −0.90 L).
- **Waist:** `waist_skin` is 0 in every view (the checkpoint's bare waist read 0.09 FAIL).
- **Torso bounds:** the torso stays behind the bow and its tails by their measured depth (`code_body.IN_FRONT`,
  counting only the bow's hull points inside its drawn extent).
- **Owned elsewhere:** tool/face owns the torso's top rows and the neck join (its new slender neck isn't merged
  yet; the collar will need re-seating on it). tool/rig owns the skin and garment weights, joints and twist bones.
- **Hull and outfit:** private to this worktree since 18:08, rebuilt from its own code at 18:18.


Why: garments lying on the body (the collar, a hull-true top, sleeves, cuffs) end up inside the MakeHuman body, which
isn't the design's. Its waist sits about 0.3 L low, it's up to 0.12 L wider at the sides, and its back stands out.
The loose pieces (skirt, waistband, bow) work only because they sit outside the body or hide it.

Michael's decisions: MakeHuman is retired, and the code-authored base replaces it. Skeleton and weights come from our
own rig code or are transferred once.

## Shape

The body is the design's inner envelope: the hull's surface, less the clothing, where the drawings show skin or a
tight garment.

- **Torso:** a `geom.loft` field around a vertical axis, from the neck cut (the code head's CUT, joined by its zip) down
  to the crotch. Where a tight piece covers it (the top, the shorts), the hull's surface less the piece's thickness.
  Where a loose piece hides it (the skirt, the panels), the field is filled from the rows the design shows, bounded by
  a style-profile prior (waist-to-hip taper).
- **Limbs:** a loft around each bone: upper and lower arm, thigh, shin. The hull already carves the limbs apart (the
  per-piece limb split). Measured where skin shows (forearms, thighs below the shorts, knees); under sleeves, boots and
  cuffs, the covering piece's section less its thickness.
- **Joints:** measured from the hull. Shoulder, elbow, wrist, hip, knee and ankle come from the limb sections'
  narrowing and bends, and the outfit graph's skeleton (front-view bone segments) gives the depth from the hull.
- **Hands and feet:** hands are a template (the anime style profile's), scaled to the hull's hand; feet sit inside
  the boots, so a simple template is enough.
- **Topology:** a quad cage per part, joined with arc-length zips (as the head's neck is), then subdivided and fitted
  to its own limit surface (code_base.fit_limit).

## Rig

- A VRM humanoid armature on the measured joints (body.build_armature's bone set).
- Weights transferred once from MakeHuman: its weights per vertex, sampled at the nearest point of its rest mesh after
  the MakeHuman body is registered to ours bone by bone. That's a one-time transfer, not a dependency. Then smoothed.
  Later, our own heat-diffusion weights.

## Measurement first

- Body checks against the hull:
  - per part, the reach and excess to the hull's skin and tight-garment surfaces;
  - the waist height, and each joint's height against the drawn figure;
  - the limb widths per view.
- The QA's body_* checks, unchanged.
- A fold and self-intersection count; joint-bend deformation checks (elbow and knee at 90°).
- The garments' piece checks, with the collar and a hull-true top switched on: the test that the body is inside the
  design.
- A review page: the body alone per view against the drawn figure less clothing, sections, and the joints.

## Order

1. Torso loft with the neck zip.
2. Limbs and joints.
3. Weights transfer.
4. Build integration (`spec['base'] = 'code'` takes the body too).
5. Garments on it: collar conform, a hull-true top, sleeves and cuffs.

## Baseline: the MakeHuman body against the hull (2026-09-29, the tuned spec)

Signed distance from the hull's points to our body, in L. Positive means our body stands outside the design's surface
there; for a tight piece, that is where it buries the garment.

| where the design shows | points | median | p90 | share out > 0.02 L |
|---|---|---|---|---|
| the top (tight) | 1156 | +0.077 | +0.155 | 86% |
| skin, all | 15620 | −0.036 | +0.090 | 40% |
| skin on the thighs | 6689 | +0.036 | +0.104 | |
| skin on the shins | 2316 | +0.021 | +0.091 | |
| skin on the arms | 3903 | −0.092 (p10 −0.42: the arm pose's angle) | +0.064 | |
| skin on the hands | 226 | −0.464 (placed elsewhere) | −0.406 | |
| skin on the neck | 238 | −0.020 | +0.028 | |
| the boots | 3770 | −0.057 | +0.044 | 19% |
| the sleeves | 1806 | −0.033 | +0.088 | 36% |

Acceptance for the authored body:
- under tight pieces, the body sits inside the hull by the piece's thickness (median −0.02 to −0.01 L, p90 ≤ 0);
- where skin shows, within ±0.02 L (median) and ±0.04 L (p90);
- the hands and arms placed as drawn (the rest pose from the hull).

## First look: how much of the torso the hull shows

A radius field for the torso, fitted to the hull's skin (neckline), the top and the waistband (each pulled in by its
thickness) around a vertical axis:
- only 29% of the cells are measured;
- the rows from −1.0 to −1.36 L (the lower bodice and the waistband) are 53–89% measured;
- the chest under the bow, collar and sleeves (−0.69 to −0.85) is 0–6%;
- below the waistband, under the skirt, it's 0%.

Where it's measured the torso is 0.58–0.73 L wide and 0.54–0.70 L deep.

So the torso can't be a pure loft. It needs a parametric torso: superellipse sections per height, as the head's
analytic skull has, with width, depth and exponent profiles set by the style profile. It's anchored to:
- the head's neck ring at the cut;
- the graph skeleton's shoulders (±0.545 L at −0.886) and hips (legs at ±0.28 L, −2.55);
- the measured bodice and waist rows.

It's bounded above everywhere by the hull's full envelope less a clearance: the body can't stand out of the design
anywhere, which is the property the garments need. The limbs are better observed (bare forearms, thighs and shins).

## The torso, v1 (charkit/code_body.py, `python -m charkit.code_body SPEC`)

One superellipse section per row (half-width, front depth, back depth, exponent, centre depth). All rows are fitted
at once:
- the data is the hull's measured cells, mirrored across the midline;
- the parameters are smooth down the rows;
- weak priors hold a torso's proportions;
- anchors at the neck ring (from its bare skin) and at the hips (the leg joints apart plus the thighs' radius, at the
  thighs' centre depth).

It's then clamped inside the hull's torso envelope less 0.012 L. Fitting row by row had let sparse rows flatten a front
or balloon a back; the joint fit doesn't.

Against the hull (where our torso stands out of each tight piece after its pull-in):

| piece | MakeHuman body | authored torso |
|---|---|---|
| the top | median +0.077, p90 +0.155, 86% out > 0.02 L | median −0.003, p90 +0.009, 1% |
| the waistband | | median −0.001, p90 +0.021, 11% |
| the neckline's bare skin | | median −0.019, p90 +0.007, 6% |

The review page is `charkit/out/body/clawd/index.html` (sections from above: the hull, the measured points, ours).
Next: the limbs along the graph's skeleton; the weights; the build integration; then the garments on it.

## Limbs, v1

Each limb is sections along its bone chain from the graph skeleton (the leg hip → knee → ankle; the arm shoulder →
elbow → wrist → hand), fitted like the torso with near-circular priors. The points are its bare skin, its boots and
cuffs pulled in by their thickness, within reach of its bones in the front view. The joints' depths come from the
middle of the limb's points about each joint; a joint nothing measures (a shoulder under its puff, a hip inside the
skirt) takes its neighbour's or the torso's hips.

| part | points | median | p90 | out > 0.02 L |
|---|---|---|---|---|
| left leg | 5222 | −0.006 | +0.027 | 14% |
| right leg | 5215 | −0.005 | +0.017 | 8% |
| left arm (with the hand) | 2732 | −0.008 | +0.017 | 9% |
| right arm | 2571 | −0.009 | +0.022 | 10% |

Radii along the leg: thigh 0.26, knee 0.165, calf 0.20, ankle 0.12 L. Along the arm: 0.17 at the shoulder, 0.10 at
the wrist.

On the page (`img/views.png`) the body is z-buffered on the design's grids through the QA's projection, outlined over
the drawing in every view. It sits inside the clothes and meets the bare thighs, knees, arms and hands.

Next, the build integration, with its costs:
- The feet: the boots are shells of the body's feet today; hull-loft the boots, or loft the feet from the boots pulled in.
- The neck join to the code head: code_base's zip, onto the torso's cut ring.
- The rig and weights: per part along its chain, a torso split by height.
- The garments' shells, which read body regions by bone and the body's UVs.

## First full builds (2026-09-29, the box)

The code head on the authored body, rigged by our own code (joints for every VRM bone; weights along each part), with
the hull-sourced garments. Measured against the same authored head on the MakeHuman body (clawd_code.json):

| | clawd_code.json (MakeHuman body) | clawd_body.json (authored body) | + hair pieces |
|---|---|---|---|
| PASS / WARN / FAIL | 65 / 29 / 17 | 70 / 25 / 16 | 79 / 23 / 17 |

Better (16):
- the feet and boots in every view: FAIL/WARN → PASS;
- body_profile_iou: 0.786 → 0.886, PASS;
- the skin IoUs in the back, profile and three-quarter views: FAIL → WARN;
- the profile and three-quarter outfit IoUs: → PASS;
- the sleeves: → PASS (0.91 and 0.79, hull-lofted);
- the right panel: 0.36 → 0.67.

Worse (9):
- the back and three-quarter hems at the middle, and the back leg (the back panels);
- the profile skirt width: 1.229 FAIL;
- the bow: 0.52 → 0.30;
- the collar: 0.50 → 0.41;
- the front hair length, marginally.

Found and fixed on the way:
- The parts' faces were wound inward.
- The code head's eye plane was its nose bridge (SectionsHead.eye_df).
- The head sheet sets the eyes 0.11 L further forward of the neck than the body sheet does. On the authored body the
  head goes where the body sheet's eyes are.
- The hull's stamp reached all of charkit; merged separately as tool/stamp.

Next:
- the back panels (the hull labels them across 90 degrees of the back);
- the bow and collar on this body;
- a gate for tool/body (the default spec doesn't take the authored body; gate it with --spec clawd_body.json too).

## Second round (2026-09-29)

- **Behind the chest's accessories.** The torso's envelope leaves out the bow, its tails and the collar, which stand
  in front of the chest without bounding it. The torso stays behind the bow and its tails by their depth
  (`IN_FRONT`), counting only the bow's hull points inside its drawn extent. A torso grown into the bow's space had
  hidden the bow behind the top.
- The chest's profile under the bow (−0.70..−0.80 L) now meets the design's within 0.01 L; see garments.md.
- Owned elsewhere from 849b9a7: the torso's top rows (the neck join) belong to tool/face.

## Round 3 (2026-09-29)

- `body_profile_chest` measures the chest's front edge in profile: round 2 is 0.036 L behind (WARN; the checkpoint
  was 0.049). What remains is the bow's very top and bottom rows.
- `body_*_waist_skin` catches the checkpoint's bare waist (0.09 FAIL); round 2 and later read 0.
- The hull and outfit under `charkit/out` were hard-linked with other worktrees until 18:08. They're private now,
  rebuilt here from this worktree's code (18:18).
