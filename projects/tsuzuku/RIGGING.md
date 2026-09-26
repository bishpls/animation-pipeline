# Rigging illustrated characters: the handoff (Clawd's rig, what it taught, and Fable's finale rig)

Written for the session rebuilding Fable's finale rig at Clawd's level (Michael, 2026-09-25). CRAFT §12 has the short rules; this is
the long version: the interface the finale needs, what Fable does in it, how Clawd's rig was built and tested, and what broke.

## 1. The interface (src/finale.js → Fable). Keep these stable and the finale keeps working as the model changes
- `FABLESTAGE.room(X, t, T)`, t = real song seconds, called **177.8–181** (the room wide and the push-in through the window) and again
  **~200.47–202.59** (the freeze's room wide: only the cushion and her lantern should draw; she has walked out). T = `{x, y, s}` in
  **screen px**: her feet point, and screen px per drawing px. finale.js passes her feet at butai (3308, 2104) through the room camera,
  `s = 1.394 * cam.zoom` (.697 at CAM_WIDE: 812 px tall, matching B9's silhouette). Identity transform when called.
  Her drawings: hold (lantern on its stick in her fist) → set-down 178.2–178.85 → empty-handed → walk out right from 179.2 (turns, 0.3 s
  hops). The room drawings are good (Michael); keep them unless the new model changes her look.
- `FABLESTAGE.stage(X, tt, FW, P, { enter: 2000 })`, tt = song seconds **frozen at 199.07** (the hit), called every frame from 181.
  FW = `{ x: 1520, y: 1000, h: 1072, s: 1072 / 2085 }` in **world coords of Clawd's card** (X already carries the card camera's
  transform: draw in world units). x, y = the point between her feet on Clawd's floor, one step upstage of Clawd (Clawd: x 960 +
  rootX·.27, y 1040, s .27). **h is the contract: her standing height in world px, soles to crown** (Clawd is 975; Fable is 10%
  taller on screen: Michael). The old puppet reads s; the new rig should scale itself from h. `enter`: the entrance distance in her
  drawing px (she starts off the frame's right edge; any equivalent is fine). Returns anything (unused).
  P = Clawd's performed channels, `P(t) -> { rootX, hipX, hipY, bodyX, bodyZ, angleX/Y/Z, armL/R, elbowL/R, footLX/LY/RX/RY, kneeOut,
  handL/R, view, mouth, ... }` (engine/rig.js, `RIG.perform`), on the song clock. Also `CHOREO.clawdF.P()`.
- Nothing before bar 128.25 on stage (song 181.05). Draw order: she's upstage, so finale.js draws her before Clawd.
- The seated room Fable in world A (src/fableseat.js, rig/fable_seated) is separate and stays with me.

## 2. What Fable does in the finale (Fable's rulings; CLAWDWORLD.md "F"; run changes past your Fable)
- **Medium:** illustrated, full colour, "the puppet survives the illustration": brass rivets at the shoulders, elbows, wrists, hips,
  knees, ankles (visible where the hakama doesn't cover them); her indigo plate misregistered 1–2 px from her keyline (the only thing
  in Clawd's world that is); two coloured shadows on Clawd's floor (pink and cyan, laid back from her feet).
- **Timing:** on **twos** (12 drawings/s, held), **snap and hold**, **no springs** on her (Clawd's secondary motion is springs; hers is
  none). Her ribbon (Verlet in her own world) may swing, stepped on twos.
- **128.25 / 128.75:** two small hops in from the right (Reiniger's hop), hood up; she pushes the hood back on the second.
- **129–135: the canon.** Clawd's pose **one bar late**, at **half amplitude**, on twos. Face out to the hall, neutral, half-lidded.
- **131.5–133.3, "why":** Clawd turns to her (image-right) and finds a face: Fable glances at her (image-left), then the
  one-raised-eyebrow smile (133.3–135).
- **135–141: unison.** The delay closes on the sideways step: two steps to image-left landing on the downbeats, weight low, **feet
  flat**, still half amplitude, still on twos. "The retelling catches the telling and stays caught."
- **141: freeze together** on the hit (finale.js holds tt). The smile holds.
- F4 and F6 notes press in the margin with no hand (finale.js does them). No props on stage: "what steps in has empty hands".
- Proportions: tall, narrow; long straight blue-black hair cut flat, bangs; a black haori with wide sleeves and white deckle cuffs; the
  red cord; a long pleated indigo hakama over white tabi and black geta. The skirt hides her legs: her steps read through the hem, the
  feet and the hips, not knees.

## 3. The build pipeline (Clawd; tools/, in order)
1. **The base drawing.** GPT Image (tools/gptimage.py; it beat Gemini on an A/B): one full-body front view on flat green, at the
   size you'll rig from (Clawd: 2160×3840). Arms slightly away from the body (a rig can close a gap, never open one it can't see).
   Key it (tools/chroma.py --full, or `from chroma import key` in a builder: despill, full canvas). Everything later is registered to this canvas.
2. **Part masks vote; the lines decide.** tools/segment.py (SAM 2.1, points and boxes per part, `vendor/seed-vc/.venv`) gives rough
   masks; tools/layers.py cuts the image along its own drawn lines into flat-colour cells and gives each cell whole to the part whose
   mask covers most of it, so every boundary is the artist's line; each line pixel goes to the front-most part within `line_r`. `order`
   (front → back) decides overlaps; `split` carves by polygon (hair into front, sides, back); `force` fixes wrong votes. Review
   `_labels.png` / `_sheet.png` every time.
3. **Hidden areas get real drawing.** tools/rigbuild.py underpaints what motion can reveal, in this priority:
   - **companion drawings** (`fromimg`): GPT Image edits of the base showing what's hidden (hair tied back: the jaw, ears, neck,
     shoulders; a sleeveless jacket under the sleeves), registered with tools/register.py (ECC on lineart-weighted luminance in an ROI
     that shouldn't change) and cut by the same cells. Best by far;
   - **crossfill** from other drawn views; **plates** (e.g. back hair drawn from a companion, plus an extension);
   - **invented fills** (inpaint from the layer's own flats, `hull`/`flat`/`within`) only as a last resort, and **every invented pixel
     is exported** (`<layer>.inv.png`) so the tests can see when motion exposes one.
   - `outer_margin` (14 px): invented pixels and colour bleed never reach the figure's outer silhouette (a single layer within 18 px).
     Without it, relative motion slides a flat fill past an outline and you get "paint outside the lines" (Michael caught it on the buns,
     the ahoge and the puff sleeves). `lines`: ink laid on invented pixels only (a torso's side contour under a sleeve).
   - Invariant: **the rest pose reproduces the illustration exactly** (tools/restcheck.py: heat map of any difference).
4. **Drawn views, not warped faces.** A turned head pasted on the front body can never match at the collar: each view (Clawd: L/HL/HR/R
   at ±35/±20°) is a whole new upper-body drawing (GPT Image edit of the base, registered on the waist and below), cut with the same
   parts (`views/*`, `view.py`), and the runtime swaps the whole upper body. Joins only where drawings agree (waist, cuffs).
5. **Variants** (tools/variants.py): mouths, eyes and hands as GPT Image edits of a crop, registered back, cut to the same patch, per
   view and per crop (`edits` dirs per crop, or the cache mixes them). Hands: `isolate: skin` so the edit's cuff doesn't ride along.
   Check every variant at 100% beside its siblings: one mismatched drawing (Clawd's wide grin) reads as a pop every time it plays.
6. **rig.json**: manifest, origin (feet), head (pivot, displacement tables), neck, body (bodyX, breath, bend, pelvis, legs, feet, heel),
   arms (elbow pivots, axis, blend), mesh density per layer, views, springs, perform, variants.

## 4. Articulation (engine/rig.js; WebGL2 grid meshes, one per layer)
- **Head:** turn by measured displacement ratios per feature (kx/ky tables), rigid features (the eyes and mouth move, don't bend);
  the "bent paper face" came from warping features. **Neck** skinned by height: its top follows .5/.16/0 of the head's tilt; head
  controls never move collar, shoulders or chest (measured from Live2D's samples: docs/research/README.md §4, live2d/coupling.json).
- **Body:** an X shear field, a breath profile, a progressive Z bend over pivots; the body follows the head via `RIG.perform` (ratio x
  1.76, z .41, 60 ms lead), which is what makes turns read as a person, not a head on a stick.
- **Arms:** FK: the elbow skinned across the joint, then the shoulder. The **elbow hinge** sharpens past 120° (a soft blend folds the
  forearm into rubber); shoulder range −100…175°. **Arm depth order**: per frame, an arm draws over the face and hair or behind the
  body (a front-view rig can only show depth by order). The puff sleeve is skinned by region (stays on the body at the shoulder top,
  moves fully with the arm at the cuff): a rigid puff over a rotating arm slid off its trim and doubled the cream band.
- **Pelvis and legs:** hipX/hipY, legs skinned pelvis → ankle, knee bend (`kneeOut` so knees track over toes), feet footLX/LY/RX/RY.
  Weight shift: the unloaded heel lifts and draws in (a **heel pivot**, not the whole boot floating); toe in/out and point/flex.
- **Springs** stepped from a fixed pre-roll (deterministic in t). Fable gets none.
- For Fable's rivet puppet, the same lessons: rotate at the rivets, give every joint real underpaint (a sleeveless jacket, a headless
  collar, an under-skirt), and a cloth fan past each elbow cut so a bent elbow never opens a gap.

## 5. Motion data
- **engine/moves.js:** a move is `(b, o) => channels` over its local bars. `MOVES.choreo(clock, { legs, arms, head }, { lips, blinks })`
  sequences moves by song bar per track with crossfades (`fade`) and held root positions (`root`, `root0`); `MOVES.follow(P, BODY,
  { start })` adds springs (fixed start); `RIG.perform` adds the body's coupling. `MOVES.lips` drives mouths from the vocal envelope
  plus a pronunciation table, on ones, through in-betweens; `MOVES.blinks` seeded.
- **The groove (src/motionlab.js, MOTION.md §4):** a post-pass on the performed channels: a bounce that rises on the beat, weight
  shifts, the chest and head following the pelvis 2–4 frames late, phase-locked to the measured kick (~50 ms behind the grid), energy
  per section (`ENERGY`). It took the core from still 23% of frames to 1.8%.
- **Mocap:** a directed Seedance clip (one dancer, full body, locked camera, plain set, 9:16, 5 s, one request at a time) →
  tools/posetrack.py (MediaPipe 0.10.14 in .venv-pose, CPU; 1.0 crashes on this Mac) → tools/retarget_mocap.py (image-plane angles
  onto the channels; the dancer's right arm is the rig's image-left; time-warped onto the beat grid by structural anchors) →
  `MOTIONLAB.groove(P, { curves, only })`, keyed hands, faces and views on top. tools/mocap_diagnose.py shows where the rig clamps.
- **What depends on Clawd's proportions (compensate for Fable):** channel units are Clawd's base px (hipY, feet X/Y, rootX) and
  degrees (arms, elbows, bodyZ, angles); the arm rest angle (29.7°); the pelvis D (140 px); the stance width (feet at 860 and 1285
  base px). For Fable: scale translations by her leg length and hip height against Clawd's (her drawing is ~.74 of Clawd's scale;
  the old puppet used K = .37 = .74 × half amplitude), offset arm angles by her own rest, and let the hakama carry the steps (the hem
  swings so it stays over the foot; the feet step and lift).

## 6. Gotchas, and the review loop
- **A single test loop hides most bugs.** src/rom.js: every control alone and combined, fast whips, tilts and nods inside every view,
  every view switch both ways, the performance range and the extremes; tools/romrun.py renders only the ID pass (every layer a flat
  colour, invented pixels half-bright), tools/romcheck2.py checks every frame for holes (excluding gaps drawn into the art) and exposed
  invented pixels beyond each view's rest baseline, and sheets the worst frames; tools/romheat.py maps where. ~70 s for the whole range.
- **Stills lie about motion.** Neck sliding, snapping off-model, feet glued during a sway, a dragged trailing foot, arms snapping on
  every beat, a held note with a closed mouth, a side-step reversal that jumped both feet: all looked fine in stills and broke in motion.
  Look at `--strip` of every frame of a move, and at crops at 100%, before watching the clip.
- **Verify any critic's claim at full resolution** before acting (Gemini is noise on detail).
- Renders: `--out` for sheets (two sessions writing board/sheet.jpg overwrite each other), `--workers ≤ 4`.
- The loop that worked: build → ROM harness → strips and crops at 100% → a clip with sound → Fable's review (meaning, her rules) →
  Michael (feel). Fix at the root (the build or the runtime), never with a per-frame patch.
