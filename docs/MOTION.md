# Motion: making a rigged character dance and act

The method from TSUZUKU's dance work, general to any rig on `engine/rig.js` channels. `projects/tsuzuku/MOTION.md` is the worked
example with every measurement (the audit, the groove, the mocap test, the v9 hand pass); `docs/CRAFT.md` §5, §13 and §14 hold the
short rules. Tools are indexed in `docs/TOOLS.md`.

## 1. Measure before touching it
Hand-keyed dance reads as poses cycling, and stills hide it. Dump the performance per frame and measure:
```bash
node engine/render.mjs P --eval='JSON.stringify(MOTIONLAB.dump(b0, b1, 24))' > dump.json     # channels, body points, springs
.venv/bin/python tools/motion_audit.py dump.json P/assets/song.mp3 --out board/motion         # stillness, range, lags, accents, energy
.venv/bin/python tools/dance_audit.py dump.json P --phrases phrases.json                      # per phrase: poses, hands, mocap share
.venv/bin/python tools/phrase_metrics.py before.json after.json hook:62:66                    # a change, before against after
```
The dump format is `MOTIONLAB.dump` in `projects/tsuzuku/src/motionlab.js`; a new film copies it (or promotes it) with its rig.
What mattered on Clawd, with the thresholds that read at 1080p:
- **Core stillness:** pelvis, chest and face all under 30 px/s. 23% of frames was a statue between hits; 2% reads alive.
- **Core range:** a bounce under 1% of the character's height is invisible (8 px on a 1,000 px figure); 23 px read.
- **Overlap:** zero lag between pelvis, chest and head is a rigid block. Chest 2 frames after the pelvis, head 3–4.
- **Accents:** measure the band's kicks against the grid (world A's ran 68 ms late) and phase every beat-locked move to them.
- **Energy vs song:** correlate motion per bar with loudness; a chorus no bigger than the verse is a bug.
- **Hands:** instant shape swaps, shapes lost in turned views, a shape on an arm not doing its job, the plain hand on fast swings.

## 2. The layers, in order
A performance is a stack of pure functions of t, each adding to the channels (`P(t) -> { hipY, armL, view, mouth, ... }`):
1. **Choreography** (`engine/moves.js`): `MOVES.choreo(clock, { legs, arms, head }, { lips, blinks })` sequences named moves by bar
   per track, crossfaded; moves set targets.
2. **Motion capture** where the body needs weight (§4), set per channel group over its bar span.
3. **The groove** (`MOTIONLAB.groove`): the core never stops. A bounce that rises ON the beat and gives on the "and" (the knees
   tracking over the toes), weight arriving on each beat alternately, the chest and head breaking 2–4 frames late, the arms settling
   after the drop; energy set per section and halved while travelling; no knee bounce while both feet are off the floor.
4. **Accents** (TSUZUKU's plan, not yet built as a layer): hit poses land one frame before the onset, overshoot, hold 2–4 frames;
   hand speed capped outside them (Clawd's hands jumped 170 px a frame between poses, read as jerking).
5. **Follow-through** (`MOVES.follow`, rig springs): hair and skirt driven by body velocity, lean and travel, not only head turns;
   soft limits so a landing doesn't splay them. Springs step from a fixed pre-roll, so any frame renders alone.
6. **Hands** (`MOVES.hands`), last: a keyed shape stays only while its arm does its job (a cup near the ear, a point on an open
   arm); elsewhere the shape follows the arm's speed (a half-curl as a swing accelerates, a soft open hand on the follow-through);
   every change passes through an in-between for one frame. Cache it on the 24 fps grid from a fixed start.
7. **Body coupling** (`RIG.perform`): the body follows the head, measured, so turns read as a person.

## 3. Feet, steps and jumps
- Feet step on the counts; a planted foot never slides (check its world position numerically: `leg_metrics.py`, `phrase_metrics.py`).
- Weight shifts lift the unloaded heel (a pivot), never float the whole boot.
- Check every reversal in a strip: a side-step reversal that jumped both feet looked fine in stills.
- A jump is its own channel: a crouch, a push through the toes, a tuck, the apex on the word, the landing given in the knees.

## 4. Motion capture from a directed reference (video models are off by default)
Only with the user's sign-off for the film (CLAUDE.md). The video's pixels are never used: it becomes numbers.
1. **Direct one clip per phrase:** one dancer, full body, locked camera, plain set, 9:16, 5 s, the exact moves and tempo written
   out. `tools/seedance.py`, one request at a time.
2. **Track:** `.venv-pose/bin/python tools/posetrack.py clip.mp4 refs/mocap/<name>`; judge it with `mocap_sheet.py`.
3. **Retarget:** `tools/retarget_mocap.py` measures the image plane (the rig is a front view): the dancer's right arm is the rig's
   image-left, elbows unwrapped continuously (`--wrap` when a turn slips), pelvis in the rig's units, a contact lock on planted feet,
   depth order from wrist depth. Time-warp by **structural anchors** (her event onsets onto the song's), not a uniform tempo.
4. **Apply** as `groove(P, { curves, only: [bar0, bar1] })`: body channels from the data, keyed hands, face, views and accents on top.
   `mocap_phrases.py` rebuilds every phrase listed in `refs/mocap/phrases.json`; `mocap_diagnose.py` shows where the rig clamps, which
   is where to extend the rig (TSUZUKU added the elbow hinge, depth order and foot articulation this way).
- **Licences:** CMU mocap is free to use; Mixamo is royalty-free but not redistributable; AIST++ and Bandai Namco's set are
  non-commercial only. A directed reference avoids the question (projects/tsuzuku/MOTION.md §7).

## 5. Lip-sync
- Mouths come from the song's word timestamps plus a pronunciation table (`MOVES.lips`), on ones, through in-betweens: a consonant is
  a one-frame dip, not a snap shut; m/b/p press the lips first.
- **A held note keeps the mouth open** after its word's timestamp ends: drive the opening from the vocal's loudness envelope
  (`tools/vocalenv.py`, from a separated vocal stem placed where the song used it).
- A mouth shape that reads wrong at 100% plays as a pop every time: draw more in-betweens rather than reuse one.

## 6. The music-video layer
Effects that belong to a performer's world, used on the hits the music gives, never everywhere: a beat-punch zoom with a decaying
shake on the biggest downbeats; three-colour afterimages (the silhouette 2, 4 and 6 frames back) on the fastest arcs, in place of smear
drawings; sticker outlines and slam-in type for crowd calls; a strip glitch and a colour fringe for a few frames at a power-up or a
tape-stop. They go inside the frame device, never on it. TSUZUKU's are in `src/idolstage.js` (projects/tsuzuku/MOTION.md §9).

## 7. The review loop for motion
Metrics on every change against the baseline; strips of the same phrases before and after (a side-by-side loop helps: `LOOPS.motionlab`);
the character's own reviewer rules on its rules; the director watches full-length passes with sound. See `docs/REVIEW.md`.
