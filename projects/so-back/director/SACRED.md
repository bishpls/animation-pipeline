# The sacred combo: measurements and the script

`sacred.py` is the script. `sacred_params.json` holds the tuned inputs, and `sacred_cam.py` builds the portrait camera
(`sacred_cam.json`) from a lab trace.

To rebuild:
1. `sacred_try.sh '{}'` (a res-1 lab run with traces);
2. `sacred_cam.py <lab osreport> sacred_cam.json 1110`;
3. `run.py sacred --res 4 --out ...`, with `--env SOBACK_STAGE=0 SOBACK_BG=0,0,0` and `96,96,96` for the two key passes;
4. `machinima/deliver.py`.

Film time is script time minus PRE (60 frames). All numbers below come from the game's own log, in labs `lab_falcon.py`,
`lab_punch.py`, `lab_knee.py`, `lab_fox.py` and `lab_foxpath.py`.

## Captain Falcon's attributes (ATTR/ATTR2 lines, from the disc)

| attribute | value |
|---|---|
| walk | 0.85 |
| dash, initial | 2.0 |
| run (dash max) | 2.3 |
| jumpsquat | 4 frames |
| jump v (full hop) | 3.1 |
| jump v (short hop) | 1.9 |
| jump h, initial | 0.95 |
| ground-to-air momentum multiplier | 0.75 |
| jump h max | 2.1 |
| double jump, v × | 0.9 |
| double jump, h × | 0.9 |
| gravity | 0.13 |
| terminal velocity | 2.9 |
| fast fall | 3.5 |
| air speed (air drift max) | 1.12 |
| air accel | 0.04 × stick + 0.02, so 0.06 at full stick |
| air friction | 0.01 per frame |
| weight | 104 |

Landing lag is 4 normally, and nair 15, fair 19, bair 18, uair 15, dair 24 raw. L-cancelled, the fair lands in 9.

## Carried momentum (POS traces)

**A dash jump.**
- Takeoff speed is min(ground speed × 0.75 + stick × 0.95, 2.1). Even an initial dash (2.0) hits the 2.1 cap.
- The first airborne frame reads 2.09 and falls by 0.01 per frame through the jump animation: 34 frames, down to 1.79.
- On the first frame of Fall, `ftCo_Fall_Enter` calls `ftCommon_ClampAirDrift`: vx drops to 1.12 in one frame.
- Holding the stick forward doesn't stop the decay above 1.12.

**A double jump** resets vx: 1.91 becomes 1.02, then climbs to 1.12. The carried speed is thrown away.

**Running off the ledge** without a jump: 2.3 becomes 1.12 on the first air frame (the same clamp).

**An aerial Falcon Punch started during the jump** keeps the momentum. vx decays 0.01 per frame and gravity is normal,
so a dash jump plus a punch carries Falcon about 90 units forward before the hit. The punch's stall at the hit and the
Fall clamp come after it.

## The moves

**Knee (fair).**
- **Sweetspot:** hitboxes 0 and 1 do **18%** at angle **32**, on fair frames 14–16. The game's data says 18%, not the
  folklore 22%. HIT logs 18.0.
- **Sourspot:** 6% at 361, from frame 17.
- **SHFFL on a standing Fox:** every spacing from 6 to 12 sweetspots with the fair on air frames 1–6. On air frame 7 he
  lands first.

**The SHFFL in the film.**
- **Frames 43–47:** X press on script 43, jumpsquat (KneeBend) until 47.
- **Frame 50:** the fair (AttackAirF) is drawn from here.
- **Frame 63 (film 3):** the sweetspot is drawn. Falcon hangs in hitlag for 9 frames.
- **Fast fall:** vy goes from −0.05 (the first descending frame) to −3.5 on the next frame (the director's closed loop).
- **L-cancel:** a shoulder press at y < 6 while descending.
- **Landing:** LandingAirF lasts **9 frames** (film 15–23); raw would be 19.
- **Frame 84 (film 24):** Wait.
- **Frame 85 (film 25):** Dash starts, out of the first actionable frame.

**Aerial Falcon Punch (SpecialAirN, motion 348).**
- B on frame s, action frame 1 on s + 1.
- **"FALCON"** starts on action frame 6.
- **"PUNCH!"** fires on action frame 50.
- **Hitboxes** from action frame 51: 27% (the fist), 25% and 23%, angle 361.
- **At the hit:** vy = 0 through hitlag and about 12 more frames, and a forward lunge (vx 1.5, decaying).
- The action lasts 99 frames. Drift control comes back late in it.
- If he lands during the windup it continues as the grounded punch, with no landing lag.

**Fox's Firefox charge (SpecialAirHiHold).** It lasts 42 frames and launches on frame 43. He hovers (about −2 units
over the charge). The fire hitboxes (2%, radius 8.2) fire on alternate frames in charge frames 20–32. The film's punch
lands on charge frame 40, after the fire and before the launch, so it's clean and no trade happens.

**Falcon Dive (up-B) recovery.** It rises about 38 units and travels about −32 horizontally with the stick back. The
double jump adds about +30 up.

## Fox's DI and path
- **The knee.** Fox is at 90% with the knee at x ≈ −56. He holds DI (−56, 56), 135° (up and in), from the frame after
  the hit through the hitlag.
  - He flies over the stage and off the right side: peak y ≈ 74 at x ≈ 100–146 around film 60–80.
  - Tumble starts at film ≈ 98, at (180, 56).
- **The recovery.** He drifts in (stick −80) until film 115, double-jumps at film 149 from (182, −43), and starts
  Firefox at film 170–171 near the jump's apex, (165, −7): below the ledge.
- **Kill threshold.** 90% is the highest non-kill percent from that spot. From x = 30, 80% and above KO at the side.
- **The punch.** He DIs (−56, 56) through its hitlag (108% → 135%) and is KO'd at the side blast line (DeadRight) at
  (248, 146), film ≈ 802.

## Frame conventions
- **Plates:** plate k shows logic frame s = k − 1.
- **HIT** logs s + 1. **MS and POS** are logged at the start of a frame and report the previous logic frame.
- `KNEE` and `PUNCH` in `sacred_params.json` are the **logged** HIT frames: 4 and 772. They're drawn on film 3 and 771.

## Round 2: re-aims, the taunt and the ending

**The camera re-aims.** The choreography stays byte-identical; only `sacred_cam.py` changed.

- **10.1–10.9 s, the hero shot.** His face and cocked fist in the windup aura.
  - The points come from the frozen pose's hurtbox capsules (the `shield` cue logs them in world space): the face,
    the fist pulled back behind him, and the open forward hand.
  - It's a −40° dutch angle, so the line from fist to face runs up the portrait frame.
- **12.27–12.95 s, the dive.** Nearly side-on (yaw 18) and low.
  - `dive()` pushes in, every frame, as far as the frame still holds Falcon's body, Fox and the impact. It only ever
    moves in, and at the hit it also holds the fire bird behind the fist.
  - The impact lands at frame centre on film 771.
  - A 3/4 from beyond Fox (yaw 65) was tried and dropped: Fox's Firefox charge flare, a column of light, stood between
    the lens and the punch and hid the bird.

**The taunt ("Show me your moves!"): film 976–1036.**
- **Facing.** Melee's taunt turns Falcon to face *into* the stage (−z), away from the game's own camera. The front-on
  close-up therefore sits behind the stage (yaw 180).
- **The voice.** In the voice band it starts on film 986 and ends on 1025.
- **The gesture.** It peaks on film 998: a raised open hand beside his face, palm to the lens.

**The ending (`SOBACK_END=1`)** is a real one-stock match with the same inputs and no freeze. The punch is logged at
script 270, and Fox is KO'd at the side blast line. After GAME!, the scene change comes at loop frame 423.
- **The victory pose** is chosen by the button held on the winner's port as the screen sets up (gm_1798.c):

  | button | pose | what he does |
  |---|---|---|
  | B | 0 | a flying kick, a landing in dust, then a low guard facing the viewer with his palm out |
  | Y | 1 | crouched, head bowed, then a wide power stance facing the viewer |
  | X | 2 | turns his back, spins, then a high kick held |
  | none | random | `HSD_Randi(3)` |

  `Film.menu_hold` holds the button, starting at loop frame 415.
- **Audio across the scene load.** The load has no frames but keeps its DSP audio (1.64 s of silence), so the victory
  audio is re-synced to where the audio comes back.
- **The announcer**, found by cross-correlation with his own clips:
  - GAME! plays on plate 309.
  - "This game's winner is..." starts with the victory screen's first frame (plate 416).
  - "CAPTAIN FALCON!" comes 2.53 s later (plate 568), just before the results table slides in (plate 576).
