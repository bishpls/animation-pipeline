# The authored body, fitted to the hull (plan)

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
