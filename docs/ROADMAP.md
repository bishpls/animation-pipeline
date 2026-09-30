# charkit roadmap (2026-09-30)

Where charkit stands against the commercial default, what's missing for a production rig, and the architectural and
algorithmic changes planned. The state of each branch is in `docs/CHARKIT_HANDOFF.md`; this is the direction.
Michael's goal: any character's reference images in, a fully rigged model out, with no per-character tuning. The
generality metric is the share of checks a new character passes out of the box. The first reading, on a second
character from an unpublished project: 30% against Clawd's 83% on the same code.

## Our approach: construction, not reconstruction

The only generative step is 2D. After it, everything is built.
1. **2D references.** GPT Image turns the model sheet into a reference set: turnarounds, breakdowns, close-ups.
2. **Geometric evidence.** The references become produced references:
   - a visual hull built from the turnaround's silhouettes;
   - outfit masks;
   - hair layers.
3. **Code builds every part.** Each is made from a few parameters fitted to the design's per-view silhouettes:
   - the code-built head;
   - the authored body;
   - garment templates;
   - cut hair pieces;
   - accessories.
4. **The rig comes with the construction.**
   - The body's skin weights are blended along each part's own parametric chains.
   - Garments inherit the body's weights.
   - Flaps and locks get spring chains, exported as VRM spring bones.
   - Expressions are shape keys.
5. **The look** (toon shading, ink lines) renders in our own renderer (`charkit.render`, wgpu), with EEVEE as a
   parity reference.
6. **Measurement.** Every stage is measured against the design per view. Merges are gated and previewed, and
   Michael's review flags become calibrated regression checks.

## Against the commercial default

The usual pipeline: image -> Tripo / Meshy / Hunyuan3D / TRELLIS (one fused, textured mesh) -> part segmentation ->
autorig (a predicted skeleton and weights) -> AI-assisted cleanup, then an artist does retopology, weights and
blendshapes.

| | Commercial default | charkit |
|---|---|---|
| First output | a sculpt: one fused surface, lighting baked into its textures | separate parts with meaning (a lock, a flap, an eyelid) |
| Hidden surfaces | invented at segmentation, often holes | built: every part is whole |
| Topology | triangle soup, retopologised by hand | authored for deformation (lid, mouth and joint loops), clean normals for cel shading |
| Rig | predicted skeleton and weights on a fused mesh; no face rig or secondary motion | skeleton and weights by construction; expressions; spring chains per part |
| Fidelity | what the model saw; unseen views are guesses | measured against the sheet per view, gated |
| Editing | regenerate or sculpt | change a parameter, rebuild, diff |
| Anime lines and cel shading | jagged terminators on noisy normals | built for it |
| A new character | minutes, any shape | a builder per new piece type (the gap the generality metric tracks) |

**Where each wins:** the commercial default wins on breadth and speed. We win on control, deformation and fidelity.
Our gap is vocabulary: a builder, or a generic fallback, for every piece type.

## Missing from a production rig

**In place:**
- skeleton and weights by construction;
- the VRM humanoid and VRMC_springBone export (through the VRM Add-on for Blender, MIT);
- expression shape keys, visemes and blink;
- flap spring chains;
- motion QA R1-R4.

**Missing, or with no clear plan:**
1. **Deformation at the joints.** Twist bones and correctives are scoped in `tool/rig` (paused) but nothing is
   measured yet. Plan: pose-space correctives trained on motion QA's extreme poses, and dual-quaternion skinning or
   delta mush, hand-rolled.
2. **Spring-bone colliders and tuning.** Body colliders and per-chain stiffness aren't fitted, and there's no QA for
   secondary motion.
3. **Loose garments in motion.** Skirt and coat-tail penetration during a kick isn't solved in general. It needs
   collision-aware chains or simulation (see the cloth solver below).
4. **Face rig breadth.** Still to build:
   - the modular expression system (eyes, brows, mouth and face as combinable components; Michael's direction);
   - an eye look-at rig;
   - a separate iris per eye (heterochromia can't be built today).
5. **Anime rendering tricks.** Still to build:
   - SDF face-shadow maps;
   - smoothed outline normals stored as a vertex attribute, so hard edges don't split the line;
   - brows and eyes drawn through the hair (a stencil pass).
6. **UVs, textures and decals.** Garment UVs are ad hoc, and nothing covers prints or small details (pins,
   emblems).
7. **Hands.** Gesture-level hand rigging isn't planned.
8. **Weights for pieces we didn't build** (the generic fallback): a hand-rolled heat-diffusion or
   bounded-biharmonic solver. UniRig's code is MIT, but its weights' licence is unstated.

## Changes, ranked

1. **A character-description layer.**
   - A vision-language model reads the breakdown sheets into a structured character graph: pieces, piece types,
     layering, attachments, materials, colours, asymmetries.
   - Measurement against the sheet verifies it.
   - Builders dispatch on piece type, and everything character-specific (palette, piece lists, check names) comes
     from the graph.
   - It removes the hand-written garment lists, the palette-tuned detection and the Clawd-named checks.
2. **Detection that doesn't use colour.**
   - Views come from the sheet's layout.
   - The palette comes from its palette strip.
   - Eyes are found inside the face.
   - A floor line under the figures must not merge the views.
3. **Garments as sewing patterns, with our own cloth solver,** for the tailored and draped pieces.
   - Panels and seams give UVs (one island per panel), seam edges for lines and creases, rest lengths for physics,
     and a few meaningful parameters.
   - Rigid stylised pieces (stepped flaps, bows, boots) stay templates.
   - Physics is the baseline; stylisation is a set of deliberate, code-tuned dials.
   - Pilot: Clawd's skirt as a pattern, compared with the current template on the same checks.
   - Licences: GarmentCode's pattern DSL is MIT (usable). Its NVIDIA Warp fork is non-commercial, so write our own
     XPBD solver, on upstream Warp (Apache-2.0) if the GPU helps. Seamly2D is GPLv3+ (no fork). DXF-AAMA/ASTM is
     only an interchange format for fashion CAD (CLO, Marvelous Designer); support it with ezdxf (MIT) only if an
     artist refines garments there.
4. **Hair as ribbons from 2D flow fields.**
   - Hair reconstruction's orientation fields (2D orientation maps lifted to 3D across views) give each lock its
     growth direction and curve, from the design's hair lines.
   - A lock becomes a ribbon between two contour curves ("Modeling 3D Hair by Outlining Hair Cards").
   - Braids get a dedicated builder.
   - GaussianHaircut (CC BY-NC-SA) and hair-gs (it depends on non-commercial Gaussian Splatting code) are ruled out
     by licence and by fit: they reconstruct realistic strands from calibrated photos, not stylised clumps from four
     drawn views.
5. **Differentiable silhouettes in `charkit.render`,** so template fits optimise with gradients rather than by
   sampling. Hand-rolled: nvdiffrast is non-commercial.
6. **Finish single-source geometry** (docs/GEOM_TRUTH.md, including call J: subdivision and Solidify in the venv).
   Blender then remains only an exporter and the EEVEE parity reference, and a direct VRM writer would remove even
   that.
7. **QA the generated references.** Measure each against the canonical sheet (palette, counts, shapes) and
   regenerate or inpaint only what fails. The second character's pupils and braid link count drifted.

## To hand-roll (in order)

1. XPBD cloth and spring solver.
2. Skin-weight solver and pose-space correctives.
3. Subdivision and Solidify (call J, planned).
4. Soft silhouette rasterisation.
5. Hair orientation fields and a ribbon builder.
6. A direct VRM writer.

Not worth hand-rolling: 2D image generation, and the vision-language model for the character graph.

## Iteration speed: the gate loop

Measured 2026-09-30:
- 62 gates ran; 29 of them (47%) were on the MakeHuman spec, which is now retired.
- A default-spec candidate build took a median of 546 s wall on the loaded box (about 290 s unloaded), 219 s of it
  in Blender.
- Baseline builds were cached in 41 of 62 gates.
- Gate builds took 10.4 h of wall time in all.
- 23 gates failed.
- The build box averaged 8.3 builds at once on 32 vCPU (load 32.6). Only Blender takes a slot; the Python stages
  run unbounded.

Speed-ups, largest first:
1. **Retire the MakeHuman gate:** done, about half the gates.
2. **Stop oversubscribing the build box.**
   - A slot should cover the whole build, not only Blender.
   - Each build's thread pools (numba, BLAS, OpenMP, llvmpipe) should be capped to its share.
   - Under today's load a build ran at about half speed, and ssh dropped.
3. **Reuse a gate when pipeline-3d moves.** Agents re-gate after every pipeline-3d merge. A gate result should carry
   over to a new target when the intervening commits' changed stages (their cache keys) don't meet the candidate's.
   The integrator merges on that without a new build.
4. **Share build-stage caches across gate clones** (as the produced-reference cache does), so a hair-only change
   doesn't rebuild the body, garments and character.
5. **One live gate per branch.** A new gate cancels the branch's older one (`remote kill`). Superseded gates were
   left to run today.
6. **Skip work a gate doesn't need:**
   - VRM and shape-key export (80 s wall, 63 s of it evaluating shape keys) unless the branch touches export;
   - Blender's 46 s character assembly, once GEOM_TRUTH step 4 lands.
7. **Iterate locally, gate once.** An exact evaluator (single-source geometry) and QA boards from `charkit.render`
   (0.02 s a board on the laptop) let agents converge before the first gate, instead of using gates to iterate.
