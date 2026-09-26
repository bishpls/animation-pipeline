# MOTION: making Clawd's dancing alive (measured, then built)

Michael asked how to make the choreography "even more alive / full of motion / bouncy / vibrant … really, really high-quality motion design, that pushes the border of what would typically be done in 3D for a human workflow." This is the phase-1 audit (measure, rank, prototype), the Seedance mocap test on the hook, and the rig extensions the mocap showed we need.

Tools (all repeatable):
- `src/motionlab.js`: `MOTIONLAB.dump()` (per-frame performed channels, located body points, rig springs), the fix-#1 groove layer (`MOTIONLAB.groove(P, o)`), and the loops `motionlab` (before | after), `motionlab_hook` (keyed | mocap | reference), `motionlab_range` (the rig's new range).
- `tools/motion_audit.py`: metrics and plots from a dump plus the song.
- `tools/retarget_mocap.py`: MediaPipe pose → rig channel curves, time-warped onto the song.
- `tools/mocap_diagnose.py`: where a retargeted clip runs out of rig.
- Plots and dumps go to `projects/tsuzuku/board/motion/` (gitignored).

```bash
node engine/render.mjs projects/tsuzuku --eval='MOTIONLAB.dump(45, 93, 24)' > projects/tsuzuku/board/motion/dump.json
.venv/bin/python tools/motion_audit.py projects/tsuzuku/board/motion/dump.json projects/tsuzuku/assets/song.mp3
```

## 1. The baseline: world A as it stands (bars 45–93)

Clawd is about 1,000 px tall at the wide shot (stage px, s .27).

| Measure | Now | What it means |
|---|---|---|
| Core still (pelvis, chest and face all < 30 px/s) | **23%** of frames (verse 2: 30%, hook: 10%) | a statue between hits |
| Core vertical range (pelvis / chest / face, 5–95%) | **8 / 10 / 11 px** | the bounce is under 1% of her height: invisible |
| Core-to-hands motion (summed speed) | **0.33** | the arms dance; the body doesn't |
| Hand snaps | max **158–173 px/frame**; 176 and 143 frames over 25 px/frame (worst: bars 65.6 and 76.9) | smear speeds, with no smear drawings |
| Overlap: chest after pelvis, face after chest | **0 frames** lag, r .93 | rigid; no successive breaking |
| Drums vs the 170 BPM grid (world A) | kicks **+68 ms**, snares +43 ms | the grid runs about 1.6 frames ahead of the band |
| Motion hits vs the nearest drum | median **−45 ms**; 35% within one frame; **11.5%** of drum hits get a visible accent | the accents float off the music |
| Motion energy vs song loudness (per bar) | r = **0.26** | chorus 1 opens at 20–40% of peak motion while the song is at 85–95% |
| Hand-path straightness (per beat) | median 0.89; **26%** of windows near-straight | parts are linear, not arcs |
| Secondary (spring lag × gain, p95) | hair 4.6, ahoge 1.7, bun 14.9, skirt 22.5 | hair barely moves: it's driven only by head turns |

Plots:
- `board/motion/energy_vs_song.png`
- `board/motion/speeds.png`
- `board/motion/paths.png` (the core paths are tiny blobs)
- `board/motion/stillness.png`
- `board/motion/accents.png`
- `board/motion/secondary.png`

Strips (the fixed full-body camera, `--loop=clawdsolo`): `board/motion/strip_{c1,hook,walk,c2}.jpg`.

## 2. The ten biggest visible problems, by impact
1. **The core doesn't dance.** Legs straight, head level, pelvis moving 8 px: only the arms move (strips, `paths.png`).
2. **No successive breaking.** Pelvis, chest and head move as one block (0-frame lag), so the body reads rigid.
3. **The arms snap.** Hands jump up to 170 px a frame between poses, which is Michael's "fast jerking of the arms." The snaps aren't motivated by accents.
4. **The accents miss the music.** The grid leads the band's kicks by 68 ms in world A, motion hits sit 45 ms ahead of the drums, and only 1 drum hit in 9 is answered.
5. **The energy doesn't follow the song.** r = 0.26: the choruses and the hook are no bigger than the verse.
6. **Dead holds.** A held pose is frozen (23% of frames). A moving hold (breath, groove, a drifting hand) is what reads as alive.
7. **The feet are glued and flat-footed.** The boots move only on side-steps, and the weight-shift heel "lift" floated the whole boot.
8. **The head is passive.** An 11 px range, with no bob against the body and no lead or follow.
9. **Weak secondary motion.** The hair is driven only by head turns (not by the bounce), the ahoge barely moves, and the buns follow a bounce that barely exists.
10. **Straight transitions.** A quarter of the hand paths are straight lines: pose-to-pose blends in parameter space without arcs or overshoot.

Also measured: the hip sway at bars 58–61 moves the pelvis 13.8 px a frame at the wide (about 51 base px), with hipX stepping 0.5 a frame, which is the motion fork's lead. It goes away when the groove layer carries the sway.

## 3. What reads alive (research, briefly)
- **3D idol lives** (Love Live!, iM@S, Hololive 3D):
  - The groove never stops: the knees give on every beat, the torso rides the pelvis two or three frames late, and the head counter-bobs.
  - Hit poses land on the accents with 2–6-frame holds, and phrases end on a big silhouette.
  - The base is performer mocap, polished by animators: keyed hand shapes, exaggerated hit poses, retimed accents, cleaned foot contacts.
  - The camera punches and cuts on the accents.
- **The Live2D dance pieces Michael sent** (Brian Tsui's Helltaker, Hip Sway, "A Demon's Requiem"):
  - The body is a chain: the hips drive the torso, the torso drives the head, with a few frames of lag per link.
  - The whole-body rotation deformer pivots over planted feet: sticky feet, the body moving over them.
  - Hair and skirts are driven by body velocity, not head angle, with overshoot.
  - Squash and stretch are parameter deformers.
  - A loop never has a dead frame.
- **Sakuga timing:**
  - anticipation, then the accent, then overshoot, then a hold;
  - poses on twos with impacts on ones;
  - slow in and out around holds, fast through the middle;
  - smears or afterimages on the fastest arcs;
  - 1–2 impact frames (the extreme pose) at the hit.
  - Used sparingly, on the hits the music gives.

## 4. Fix #1, prototyped: the core dances (`MOTIONLAB.groove`)
An additive layer on the performed choreography, driven from the pelvis:
- **Bounce:** a bounce that rises ON the beat (Fable's rule: Clawd never lands), with a quick push through the beat and a sit in the knees on the "and". 70 base px of knee give, with the knees tracking over the toes (kneeOut 0.62).
- **Weight:** the weight arrives on each beat, alternating sides, so the rig's heel pivot unloads the free foot.
- **Successive breaking:** the chest counter-tilts two frames after the pelvis, the head tilts four frames after, and the head nods three frames after the drop.
- **Arms:** they settle after the drop, with the forearms trailing.
- **Energy:** set per section (chorus 1.0, the hook 0.8, verse 2 0.55, chorus 2 1.1, fading into the curtsy) and halved while she travels.
- **Phase:** grid + 26 ms, so the rise peaks one frame ahead of the measured kick.

| | now | fix #1 |
|---|---|---|
| core still | 23% | **1.8%** |
| pelvis / face vertical range | 8 / 11 px | **23 / 25 px** |
| core-to-hands motion | 0.33 | **0.43** |
| motion hits vs drums (median) | −45 ms | **−5.5 ms** |
| energy vs song (r) | 0.26 | **0.37** |
| bun p95 | 14.9 | **55** |

Clip: `out/motionlab_v1.mp4` (bars 46–54, now | fix #1, with sound). Folding it in is one line in `src/chorus.js` (`RIG.perform(RIGS.clawd, MOTIONLAB.groove(build()))`, or a `MOVES.groove` post-pass), plus retiring the old `bounce` amplitudes it doubles. Not done yet: moves.js and chorus.js were in use.

## 5. The mocap test: the hook from Seedance (`out/motionlab_hook_mocap_v2.mp4`)
- **Source:** `refs/mocap/hook_v1.mp4`, 5.04 s, one dancer, locked camera; tracked by `tools/posetrack.py` (MediaPipe) into `hook_v1_pose.json`.
- **Retarget:** `tools/retarget_mocap.py` writes `refs/mocap/hook_v1_rig.json`, which `LOOPS.motionlab_hook` plays as keyed | retargeted | reference, with sound.

**Time warp.** Her dips come every 0.75 s: a half-note pulse at about 160 BPM. Her accents (pinches) sit on half-notes, but the song's claps, which Clawd answers, are quarter notes. A uniform dip warp can't make those land, so the clip is warped by **structural anchors**: her event onsets onto the song's.
- ear at 62;
- the pinches at 62.5;
- the sweep at 63;
- the pinches at 63.5;
- the other ear at 64;
- the pinches at 64.5;
- the sweep at 65.

Her clip ends mid-way through the second sweep, so bar 65.5 reuses her second pinch segment, crossfaded over 8 frames. The dip warp is kept as an option (`--dip beat|and`: onto the beats, or onto the "and"s, per Fable's rule).

| hook, bars 62–66 | hand-keyed | mocap (rig v2) |
|---|---|---|
| pelvis / face vertical range | 6 / 8 px | **35 / 36 px** |
| core-to-hands motion | 0.13 | **0.42** |
| feet moving | 13% of frames | **46%** |
| bun p95 | 14 | **71** |
| worst hand jump | 158 px/frame | 134 px/frame |

**Verdict: mocap as the base layer, keyed hits on top.**
- **From the data:** her body is better than anything keyed: the weight, the knee give, torso lean, the head, the feet. So the body channels (hipX/Y, bodyZ/X, head, feet, kneeOut) come from the data. The arms carry the circles and arcs, blended with the keyed arms.
- **Keyed on top:**
  - the accents on the song's quarter-note claps (snap into the pinch pose one frame early, with a 2–3-frame hold);
  - the hand shapes (pinch, the flat wipe hand) from our drawn variants;
  - Fable's rules: both wipes left to right, and wipe 2's edge tracking her hand_L;
  - anime exaggeration: arm angles ×1.1–1.2 at the hits.
- **What the data lacks:** hand shapes, face and eyes and mouth, the drawn head views, the song's clap rhythm, and the accent sharpness the warp softens.

### Retargeting method (`tools/retarget_mocap.py`)
The rig is a front view; the image plane is what reads, so most channels are measured there.
- **Arms:**
  - The rig's image-left arm is the dancer's right (landmarks 12, 14, 16). No mirror.
  - Shoulder: `armS` = the upper arm's outward angle from straight down, minus the rig's rest of 29.7°.
  - Elbow: `elbowS` = the forearm's outward angle minus the upper arm's. It's continuous through crossings: re-wrapping it to ±180° flips it mid-windmill.
- **Pelvis:** `hipY` = the pelvis drop from her standing height (base px, + down). `hipX` = the pelvis over the ankles, in units of the pelvis D (140 base px).
- **Torso:** `bodyZ` = the shoulder-mid against the hip-mid (deg). `bodyX` = the shoulder yaw from world z, divided by 35°.
- **Head:** `angleZ` = the ear line's roll against the shoulder line. `angleX` = the nose against the ears (turn, divided by 30°). `angleY` = the nose's drop against the ears (nod).
- **Feet:** the ankles against their standing places. **Contact lock:** a planted run holds its median, and the swing is eased from one planted place to the next. Toe in/out comes from world-space heel→toe yaw, heavily smoothed (MediaPipe's foot depth is its noisiest channel). Heel pivot and point come from the heel against the toe.
- **Arm depth:** `armFrontS` / `armBackS` from the wrist's depth against the shoulder plane (< −12 cm in front, > +6 cm behind), held at least 3 frames.
- **Scale:** the rig's shoulder-to-ankle (1,705 base px) over hers.
- **Smoothing and limits:** Savitzky-Golay (7, 2), then re-clamped to the rig's limits.
- **Time:** `--anchors 'src:bar,…'` and `--tail 's0:s1:b0:b1'`, or the dip warp.
- **Where it plugs in:**
  - `MOTIONLAB.groove(P, { curves, only: [bar0, bar1], bounce, sway })` takes the JSON's `curves` (`mode: 'set'` replaces a channel, `'add'` layers onto it).
  - To layer keyed hits over mocap, play the mocap as 'set' and the accents as 'add'.
  - For a new clip, track it, retarget it with anchors from its structure, and point `MOCAP.url` at the output.

## 6. Rig limits the mocap found, and the extensions built (rig v2)
From `tools/mocap_diagnose.py` (`board/motion/limits/rig_limits.json`, `rig_limits_arms.png`, `rig_limits_feet.png`), before and after:
- **The windmill:** the image-right forearm circles past the upper arm, its elbow angle running 2–312° (0.86 turns), beyond ±150° for 22% of frames. It was clamped for 21%, and the upper arm swung to −93° across the chest (clamped 18%). *Built:*
  - the elbow sharpens into a hinge past 120° (the skin blend shrinks), so the forearm circles over the upper arm without smearing;
  - elbow limits to ±320°, the shoulder to −100…175°.
  - Clamps are now 0%.
- **Arm depth:** the wrists are well in front of the shoulder plane 62–82% of the time (the pinches at her face), and behind it 11% (image-right arm). *Built:* per-frame layer order in `rig.js`: `armFrontS` draws the arm, cuff and hand over the face and hair; `armBackS` draws them behind the torso.
- **Torso and head:** lean, yaw and head turn exceeded the old limits 12–17% of the time. Limits are raised to bodyZ ±12°, bodyX ±0.9 and angleX ±0.7. Head roll still clamps 3.7% at ±14°.
- **Feet:**
  - *Sliding:* the source's planted feet don't slide (p95 about 1 px), but the rig slid 47 and 37 planted frames (tracking jitter ×3). The contact lock brings that to 2 and 10.
  - *Built in `rig.js`: foot articulation below the ankle (`pelvis.ankleJ` 3300):*
    - a **heel pivot** (`heelS`, px): the ankle and shin rise while the sole stays planted;
    - **toe in/out** (`footSR`, deg, + out): the toe box swings;
    - **point/flex** (`footSP`, −1…1).
  - *Changed:* the weight-shift heel lift is now a real pivot (`pelvis.heelPivot`), where it used to lift the whole boot.
  - Board: `board/motion/range_feet.jpg`; arms: `board/motion/range_arm90.jpg`, `--loop=motionlab_range`.
- **Not built:**
  - *Drawn arm variants* for overhead and behind-the-head positions. The mesh holds to about 170°, but a hand behind the head needs a drawing. Cost: about 10–15 GPT Image edits (high quality, 2K: two or three poses × five views, the size of the mouth set), at the ledger's image rate. Awaiting your go.
  - *Forearm foreshortening* (a scale along the forearm axis): the hook needed it for only 3–10% of frames.
- **Pre-existing, not from this change:** the harness shows holes in world A's dance on 838 frames (max about 10k px) on the committed rig too (my extensions: 839). Worth a rig-art pass (`out/rom/worst.png`).

## 7. Mocap sources and licences (checked on the source pages, September 2026)
- **Our own directed references (recommended):**
  - Seedance → MediaPipe → retarget. We direct the exact moves, tempo and structure.
  - Michael has signed off. One paid request at a time (CLAUDE.md, CRAFT §11).
- **CMU Graphics Lab mocap:** "The motion capture data may be copied, modified, or redistributed without permission." Free for anything, but little idol dance: useful for walks, turns and generic dynamics.
- **Mixamo (Adobe account):** royalty-free for personal, commercial and non-profit projects, films included. The raw files can't be redistributed or used to train ML. Good stock dance loops; FBX, downloaded by hand.
- **AIST++ / AIST Dance Video Database:** the AIST Dance DB terms say "Use for commercial purposes is not permitted without prior written consent from AIST," with no unauthorized redistribution and a required credit. AIST++'s motions derive from those videos. **Avoid** unless the film stays strictly non-commercial or AIST consents.
- **Bandai Namco Research motion dataset:** "CC BY-NC 4.0": non-commercial only. It does include dance styles. **Avoid** for a public release.

## 8. The phased plan
Each phase lists its engine change, the expected effect, effort, and risk.

1. **The groove layer, folded in.**
   - *Change:* `MOTIONLAB.groove` becomes a `MOVES.groove` post-pass in chorus.js's build; the old `bounce`/`groove` hipY amplitudes it doubles are retired.
   - *Effect:* the core is alive everywhere (see §4).
   - *Effort:* small. *Risk:* low; it's additive, and halved on travel.
2. **Accents from the audio.**
   - *Change:* an accent track from the cue sheet's kick, snare and clap onsets.
     - Hit poses arrive one frame before each onset, with overshoot and a 2–4-frame hold; the springs are bypassed on hits.
     - A per-section clock offset (world A: +68 ms) moves every beat-locked move onto the band.
     - Hand speed is capped at about 70 px/frame outside accents.
   - *Effect:* the hits land and the jerks become accents.
   - *Effort:* medium. *Risk:* medium; the timing touches every move.
3. **Successive breaking in `RIG.perform`.**
   - *Change:* bodyZ and bodyX sampled from the pelvis two frames late, the head four; shoulder rotation from the arm swing.
   - *Effort:* small. *Risk:* low.
4. **Arcs and smears.**
   - *Change:* move crossfades eased out-back (overshoot); an arc term on hand transitions (bend the elbow through the middle of a shoulder move); afterimages on frames where a hand exceeds 60 px/frame (the MV layer below).
   - *Effort:* medium. *Risk:* low.
5. **Mocap as the base layer, section by section.**
   - *Change:* a Seedance reference per section (chorus groove, the walk, the side-steps), retargeted; body channels from the data, keyed arms, hands and accents on top, with per-channel blend weights; the contact solver; structural anchors.
   - *Effort:* medium per section, plus about one paid clip each. *Risk:* medium; the style must stay hers, not the reference dancer's.
6. **Secondary motion.**
   - *Change:* the hair springs driven by the bounce and body velocity as well as head turns (a new drive, e.g. `headY + bounce`); the skirt by pelvis velocity; higher gains; the ahoge on the bounce.
   - *Effort:* small. *Risk:* low (rig.json and rig.js).
7. **The rig for the rest of the range.**
   - *Change:* drawn arm variants (overhead, behind the head) via tools/variants.py, cost above; forearm foreshortening; automatic arm-in-front from the pose.
   - *Effort:* medium. *Risk:* low.
8. **The MV layer (below).**

## 9. The MV layer (Clawd's world only: Fable's world never gets these)
Michael shared a motion-graphics vocabulary built frame by frame in Python. What suits Clawd's world, where it goes, and how it sits in our engine. The effects go in `idolstage.js`'s `cardFrame`, as a post pass **inside** the washi border: the border is Fable's paper, the card's edge, and it never shakes or fringes.
- **The beat-punch camera** (a zoom that jumps on the beat and decays; a small shake on the biggest hits):
  - *Where:* the chorus downbeats (46–62, 82–90) at 1.5–2%; the drop (46.0) at 5% with a 6 px shake decaying over 6 frames; "Ikuzo!" (58.53) at 4%; the side-step landings (54, 56) at 1%.
  - *Not in the hook:* Fable ruled one locked shot there, which fans learn from.
  - *Engine:* `camAt()` multiplies z by `1 + A·e^(−k·(t − hit))` and adds decaying shake offsets.
- **Three-colour afterimages** (the silhouette 2, 4 and 6 frames ago, filled pink, cyan and lemon, behind her):
  - *Where:* only on the fastest arcs, the two page-wipes (63, 65), the "Ikuzo!" pump (58.53) and "watch me walk it!" (80.0), and wherever a hand exceeds 60 px/frame. At most a handful per section; they replace smear drawings.
  - *Engine:* the cast draws the rig at t − 2/24, t − 4/24 and t − 6/24 into an offscreen canvas, tinted with `source-in` at 40/28/16% alpha, before her. It needs an `opt.afterimage` hook in chorus.js's cast.
- **Sticker outline and offset colour shadow:**
  - *Where:* the crowd-call words on the side LED screens (Tsuzuku!, Me-kut-te!, So-re-ka-ra?!): a 4 px white outline and a 6 px offset shadow in pink or clay.
  - Not on Clawd, and never on Fable's type.
- **Slam-in text with overshoot:**
  - *Where:* the same crowd-call words, landing on the call (scale 1.25 → 0.96 → 1 over 4 frames).
  - *Engine:* `drawLED`, keyed on `callAt()`.
- **Glitch** (horizontal strips shifted):
  - *Where:* 2–4 frames at the stage powering up (K1, about bar 43.2, where the card tore: Clawd is code), and at the breakdown's tape-stop (90).
  - *Engine:* a strip-shift post pass.
- **Chromatic aberration** (R and B shifted a few px):
  - *Where:* 2–3 frames decaying on the drop (46.0) and "Ikuzo!"; and as a pink/cyan fringe on the page-wipe edges (63, 65, the card pulls) instead of the plain white edge.
  - *Engine:* a post pass (channel offsets via 'lighter' composites).
- **Diagonal and iris wipes:** **not used.** The page-wipe is Clawd's world's transition grammar (Fable's ruling); anything else would compete with it.

## 10. The review loop
1. **Metrics:** `tools/motion_audit.py` on each change (stillness, core range, overlap lags, accent offsets, energy r, snaps) against this baseline.
2. **Strips:** the same four phrases, plus the `motionlab` side-by-sides.
3. **Fable:** her rulings govern her feature (e.g. Clawd never lands, the fable's step lands flat on the downbeat, both wipes left to right).
4. **Michael:** he watches full-length passes with sound.

## 11. Dance refinement v9: the hands, two more capture phrases, the jump, the follow-through

Michael on v8: the dance is "definitely improvable, albeit with clear effort", and "the hands in particular for a lot of the detailed actions might be a little iffy". This pass measured first, then worked on the hands, the two capture clips, the accents and the secondary motion.

Tools:
- `tools/dance_audit.py` (new): a per-phrase audit of a `MOTIONLAB.dump()`, which now records the hands. It reports mocap coverage, held-pose clusters, arm speed, lean/tilt variety, airborne frames, and the hands: plain-hand share, changes per bar, instant swaps, named shapes in turned views, and the plain hand on fast swings (arm over 150 deg/s). It also reports the springs against hip speed.
- `LOOPS.clawdhands` (in `src/chorus.js`): the arms and hands, large, on a camera that follows her (world A, and the finale from 170 s).

```bash
node engine/render.mjs projects/tsuzuku --eval='JSON.stringify(MOTIONLAB.dump(45, 93, 24))'                    # (unwrap the JSON string)
node engine/render.mjs projects/tsuzuku --eval='JSON.stringify(MOTIONLAB.dump(126, 143.5, 24, true, "finale"))'
.venv/bin/python tools/dance_audit.py DUMP.json projects/tsuzuku [--finale] [--phrases phrases.json] --out board/motion/dance_v9.json
```

### v8, measured (world A)

| phrase (bars) | arms mocap | held poses | arm deg/s | plain hand L / R | instant swaps L / R | named shape in a turned view, frames L / R | plain hand on fast swings L / R |
|---|---|---|---|---|---|---|---|
| build (45–46) | 0.00 | 1 | 16 | 1.00 / 1.00 | 0 / 0 | 0 / 0 | – / – |
| C1a drop (46–50) | 0.00 | 3 | 54 | 0.50 / 0.72 | 1 / 1 | 38 / 0 | 0.0 / 0.58 |
| C1b wave (50–54) | 0.83 | 4 | 74 | 0.66 / 0.25 | 3 / 2 | 8 / 38 | 0.0 / 0.66 |
| C1 sideways (54–58) | 0.00 | 2 | 50 | 0.85 / 0.78 | 10 / 11 | 0 / 0 | 1.0 / – |
| C1c ikuzo (58–62) | 0.89 | 1 | 292 | 0.21 / 0.05 | 5 / 6 | 0 / 0 | 0.09 / 0.09 |
| hook (62–66) | 1.00 | 3 | 126 | 0.48 / 0.73 | 20 / 18 | 0 / 0 | 0.72 / 0.83 |
| V2a telling (66–70) | 0.69 | 4 | 82 | 0.67 / 0.75 | 2 / 1 | 43 / 34 | 0.8 / 0.7 |
| V2b wrote her own (70–74) | 0.90 | 3 | 115 | 1.00 / 0.22 | 0 / 1 | 0 / 46 | 1.0 / 0.13 |
| V2c side-step (74–78) | 0.00 | 3 | 91 | 0.65 / 0.51 | 6 / 7 | 9 / 4 | 0.45 / 0.29 |
| V2d walk it (78–82) | 0.00 | 5 | 49 | 0.30 / 0.87 | 3 / 1 | 56 / 0 | 0.14 / – |
| C2a continued (82–86) | 0.00 | 3 | 50 | 0.47 / 0.72 | 2 / 2 | 38 / 0 | 0.14 / 1.0 |
| C2b and-then (86–90) | 0.73 | 1 | 231 | 0.16 / 0.16 | 7 / 6 | 0 / 0 | 0.09 / 0.13 |
| breakdown+curtsy (90–93) | 0.00 | 4 | 29 | 0.31 / 0.31 | 2 / 2 | 0 / 0 | – / – |

- **The hands snapped, every time.** All 119 shape changes in world A were instant swaps (26 in the finale): the move vocabulary's hands are strings, and `choreo` switches a string halfway through a crossfade. The hook alone had 38.
- **Shapes vanished in turned views.** The rig drew the hands' named shapes only in the front view: the view tables in `views/*/variants.json` hold only the face. So 314 frames of world A (38 in C1a, 77 in V2a, 46 in V2b, 56 in V2d, 38 in C2a...) drew a point, cup or palm as the plain open hand. The hand layers are front-body layers in every view.
- **The plain hand on fast swings:** 34% of swing frames in world A, and 57% in the finale (hook .72 / .83, V2a .8 / .7).
- **Shapes that didn't match the arm.** 104 frames in world A and 50 in the finale drew a shape whose arm wasn't doing its job: a cup away from the ear, a point on a folded arm, a palm swung across. Nearly all fall where motion capture replaced the keyed arms and left the keyed hand on top. For example, the finale's point held through f1/f3's arms at -92 to 144 deg.
- **Still hand-keyed:** the build, C1a (46–50), C1 sideways (54–58), V2c, V2d, C2a (82–86) and the breakdown. The two chorus openings and the sideways claws are the highest-energy of these.
- **Pose variety:** 27 held poses in world A, but the top six take 56% of the held time (the director's "about six upper-body poses cycling"). The finale has 12 held poses, with the top six at 79%.
- **Secondary motion:**
  - The hair had no correlation with body speed (r 0, rms 4.4). It was driven only by head turns.
  - The skirt correlated at .40 and the buns at .34.
  - Nothing reacted to her travelling across the stage.

### What changed
1. **Two in-between hand drawings per side.**
   - `relax`, a half-curl: the resting hand between open and fist. `loose`, a soft open ballet hand.
   - Made with `tools/variants.py` (GPT Image, four edits, logged) and checked at 100% and 2x (`board/motion/hands_inbetweens_100.png`).
   - One set per side covers every view, because the arm, cuff and hand are front layers in all five views.
2. **The rig takes the front drawings in turned views.** `engine/rig.js` draw(): a front-body layer in a turned view uses the front variant table when the view's own table lacks it.
3. **`MOVES.hands(P)`, a hand-shape rule layer over the performance.** It runs last in `chorus.js` perform() and `finale.js` get().
   - A keyed shape stays while the arm does its job:
     - cup: elbow ≥ 80
     - point: elbow ≤ 95
     - pinch: elbow 45–165
     - peace: elbow ≥ 75
     - palm: elbow ≤ 110
     - skirt-pinch: arm down
   - Elsewhere, and on the plain hand, the shape follows the arm's speed and phase:
     - `relax` while a swing (over 150 deg/s) accelerates;
     - `loose` on the follow-through as it slows;
     - the plain hand at rest.
     - A speed shape holds at least 3 frames.
   - Every change passes through an in-between for one frame: `relax` to or from a closed shape, `loose` between open ones.
     - The in-between takes the frame from the side that matters less: a keyed shape arrives on time, and a release lags a frame. A snip reads plain, relax, PINCH, relax, plain.
   - It is computed once on the 24 fps grid from a fixed start and cached, so it gives the same result in any render order.
4. **Motion capture: two Seedance clips, 5 s each, one request at a time, about $2.94 in total.**
   - `c1a_v2` (46–50, reused at 82–86):
     - Directed as a bouncing, travelling dance, because c1a_v1's body was posed.
     - Its arms, set from 46 to 48: the pointing arm punches up on each beat, with the point drawing at the top and `relax` on the way down, then flings into the V.
     - Her sway, lean and head as residuals, plus residual arms over the keyed hand-to-ear.
     - `tools/retarget_mocap.py --wrap` (new, opt-in per phrase): the elbow unwrap had slipped a turn (368° while the arm hung), which spun the forearm round as it blended back into the keyed arm.
   - `c1s_v1` (54–58), plus its leftward half reused as `V2c_side` (74.25–75.5):
     - Her claws bob (×1.5), with her lean and head (×.6) as residuals over the keyed claws.
     - Her beats are spliced onto our steps (her rightward travel onto ours, then her leftward).
     - A modest gain: she held stiff claw mittens.
5. **The jump (`MOVES.hop`, on a channel of its own)** comes on each chorus's big "then!" (60.91, 88.91).
   - It opens with a crouch (50 base px) and a push through the toes with the heels up.
   - A 160 px lift, with the legs tucking in the air.
   - The apex falls on the word (86.0 s).
   - The landing is given in the knees, 0.3 beat after the downbeat. Clawd never lands on it.
   - The groove drops its knee bounce while both feet are off the floor.
6. **The turn:** chorus 2's "Me-kut-te!" (84.3–85.05) goes F > HR > R and back, with the feet pivoting toward image right.
7. **Follow-through** (`rig.json` springs; `mix` and `max` are new in `rig.js` springs(), mirrored in `MOTIONLAB.springs`):
   - The hair also feels the lean (bodyZ ×1.2), the hips (hipX ×6) and the travel (rootX ×.025).
   - The ahoge feels the bounce (hipY ×.1).
   - The skirt trails the travel (rootX ×.035).
   - The buns get a soft limit (max 70), so the jump's landing doesn't splay them to 27° and show the dark under-fill.

### v9, measured (world A)

| phrase | arms mocap | arm deg/s | lean + tilt sd (deg) | plain hand L / R | instant swaps | plain hand on fast swings L / R | airborne frames |
|---|---|---|---|---|---|---|---|
| build | 0.00 | 23 | 5.5 | 1.00 / 0.97 | 0 | – / 0.5 | 0 |
| C1a drop | **0.94** | **150** (54) | **11.7** (7.6) | 0.37 / 0.59 | 0 | 0.13 / 0.05 | 0 |
| C1b wave | 0.83 | 75 | 13.5 | 0.62 / 0.03 | 0 | 0.0 / 0.0 | 0 |
| C1 sideways | **1.00** | **72** (50) | 13.5 (12.6) | 0.71 / 0.68 | 0 | 0.14 / 0.0 | 0 |
| C1c ikuzo | 0.91 | 292 | 11.0 | 0.12 / 0.00 | 0 | 0.03 / 0.0 | **8** |
| hook | 1.00 | 126 | 11.4 | 0.27 / 0.31 | 2 | 0.17 / 0.08 | 0 |
| V2a telling | 0.69 | 82 | 9.2 | 0.60 / 0.61 | 0 | 0.05 / 0.15 | 0 |
| V2b wrote her own | 0.90 | 115 | 7.8 | 0.90 / 0.15 | 0 | 0.1 / 0.03 | 0 |
| V2c side-step | 0.31 | 98 | **6.7** (4.7) | 0.51 / 0.35 | 0 | 0.05 / 0.0 | 0 |
| V2d walk it | 0.00 | 50 | 4.2 | 0.27 / 0.87 | 0 | 0.07 / 0.0 | 0 |
| C2a continued | **0.93** | **144** (50) | **12.3** (7.9) | 0.32 / 0.59 | 0 | 0.13 / 0.07 | 0 |
| C2b and-then | 0.73 | 231 | 12.4 | 0.09 / 0.08 | 1 | 0.0 / 0.02 | **9** |
| breakdown+curtsy | 0.00 | 29 | 5.7 | 0.30 / 0.30 | 0 | – / – | 0 |

| measure | v8 | v9 |
|---|---|---|
| instant hand swaps: world A / finale | 119 / 26 | **3 / 0** (each of the 3 is two one-frame shapes back to back) |
| named shapes drawn as the plain hand in turned views | 314 frames | **0**: the front drawings now come in (V2b's point toward R, `board/motion/turned_view_point.jpg`) |
| shape drawn on an arm not doing its job: world A / finale | 104 / 50 frames | **≈0 / 0** (8 frames at sub-frame sample times) |
| plain hand on fast swings: world A / finale | 34% / 57% | **5% / 1%** |
| plain-hand share: world A / finale | 55% / 74% | 45% / 54% |
| held poses, and the top six's share of held time | 27, 56% | 26, **52%** |
| hair rms, and r with hip speed: world A / finale | 4.4, 0 / 4.7, .29 | **7.0, .20 / 5.7, .41** |
| skirt rms, and r: world A | 7.4, .40 | 7.7, .35 (it now also trails the travel) |
| energy vs song per bar, r (`motion_audit`) | .445 | **.486** |
| fastest hand, px/frame at the wide | 170 (76.9) | 190 (46.89: the fling into the V) |
| range-of-motion holes, dance clawdA (`romrun`) | 188 frames, max 59 px | **126 frames, max 45 px**; exposed hair_back +40 frames (the hair moves more); no new holes elsewhere |

Review images are in `board/motion/`:
- `hands_inbetweens_100.png`
- `film_hands_100.jpg` (film frames cropped at 100%)
- `jump_c1_frames.jpg`
- `c1a_v2_sheet.jpg` and `c1a_punch_strip.jpg`
- `c1s_before_after.jpg`
- `turn_c2.jpg`

The clips are `out/dance_worldA_v9.mp4` (61.0–131.29) and `out/dance_finale_v9.mp4` (177.8–202.59), with the film's mix.

### Open
- **No finale jump.** Fable copies Clawd's hips and feet in unison from bar 135 (`fablestage.js` mapP). A jump into the freeze at 141 would lift her too: that call belongs to the paper session.
- **Still keyed:** V2d (78–82), the build and the breakdown.
- **The fling into the V at 46.9** is now the fastest hand in world A. It comes from the dancer's own two-frame fling.
- **SFX stem:** the hook's snip at 92.49 now draws one frame later. `out/paper_mix.wav` wasn't rebuilt.
