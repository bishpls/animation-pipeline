# SO BACK: storyboard (draft 1)

A 30 s, 9:16 hyperpop hard edit. Everything you see is Super Smash Bros. Melee (NTSC 1.02), rebuilt from the doldecomp
decompilation and driven by the FRAME PERFECT director. Everything the announcer sings is cut from his own recorded clips,
with cuts, PSOLA pitch and crossfades only. The instrumental is ElevenLabs Music take c4.

**Clock:** 150 BPM, first downbeat 0.05 s. A beat is 0.4 s (24 frames at 60 fps) and a bar is 1.6 s.
Beat b falls at 0.05 + 0.4·b, and bar n (1-based) at 0.05 + 1.6·(n−1). Take c4 is in C minor, and its drop leans C major:
vocals are tuned to C, D, F and G, which sit in both.

| section | bars | time | music (measured) |
|---|---|---|---|
| cold | 1–2 | 0–3.25 | the drop at full energy from the first beat; hard cut to near silence at 3.2 (the mix adds a tape stop over the last beat) |
| over | 3–6 | 3.25–9.65 | music box in C minor, sub only, no drums (half-time feel); melody G5 C6 F6 E♭6 D6 E♭6 |
| turn | 7–8 | 9.65–12.85 | quiet (−36 dB) riser; pickup at 12.64; silence before the drop |
| drop | 9–12 | 12.85–19.25 | four-on-the-floor, supersaws, distorted 808 |
| drop2 | 13–16 | 19.25–25.65 | the same, bigger; 16th-note drum fill 24.05–24.65, breakdown 24.65–25.45 |
| end | 17– | 25.65–28.8 | final stab at 25.65, ring-out to about 28 |

## The spine: the sacred combo (Michael, 2026-09-27)

The film hangs on one combo, split across the song:
- **The knee (0.05).** Fox is at high, non-kill percent, measured in a lab sweep with DI. Falcon's sweetspot knee sends him
  offstage. The knee is **SHFFL'd** (short hop, fast fall, L-cancel: Michael), so Falcon lands out of the halved landing
  lag and dashes straight after him.
- **The freeze (~2.9).** The tape stop freezes the world: Falcon offstage, just into the Falcon Punch windup; Fox below
  the ledge charging Firefox (the punish window). Falcon gets out there by a **dash jump from the stage at full run**,
  never a double jump. Melee's double jump resets horizontal speed, and Falcon's own air speed is middling, so the
  sacred combo lives on carried run momentum (Michael). The double jump and up-B are saved for the recovery. The lab
  measures the carry from the disc attributes and POS traces. The director freezes the fighters, items and effects
  while its camera keeps moving.
- **It's so over (3.25–11.9).** The suspended moment in grey, the camera orbiting, the abyss below, intercut with flashes
  of other "over"s.
- **The turn.** The windup resumes on the silent beat (~12.0) and the fire bird forms under READY?.
- **The drop (12.85).** The Falcon Punch connects on GO!. We're so back.

One continuous in-engine capture holds the knee, the chase, the freeze with its orbit, the unfreeze and the punch on its
frame. Falcon recovers with up-B afterwards (no SD).

## The arc

1. **Cold open, a flash-forward:** the hype state. "GAME!" hits frame 0.
2. **The tape stop:** the picture decelerates with it and drains to grey.
3. **It's so over:** slow, monochrome, grainy; one image per bar.
4. **The turn:** "CONTINUE?". Colour returns with the revival platform.
5. **The drop:** we're so back. Keyed fighters over code-drawn Y2K fields, cut on every beat, Melee's slang as captions.
6. **The end:** a "GAME!" freeze, then the end card. The last frame loops into frame 0.

## Vocal arrangement (announcer only)

"(sung)" means PSOLA onto notes with hard tuning; "(chop)" means a whole clip placed as recorded (level, EQ, reverb).
Beats are counted from 0 at the first downbeat.

| beat | t | line | treatment |
|---|---|---|---|
| 0–2 | 0.05–0.85 | **WE'RE SO BACK** (preview) | sung G4 G4 C5 plus an octave double; the knee lands on beat 0 |
| 4 | 1.65 | GO! | chop, as Falcon leaps offstage |
| 6.5–8 | 2.65–3.25 | FAILURE | chop, dragged down by the tape stop |
| 8 | 3.25 | **it's so o-ver** | sung, slow and low: G4 F4 E♭4 C4; long reverb |
| 12 | 4.85 | GAME OVER. | chop, −5 st, reverb, low-pass |
| 16 | 6.45 | **it's so o-ver** | sung, answered an octave down |
| 20, 22 | 8.05, 8.85 | DEFEATED. · NO CONTEST. | chop, −3 st, reverb |
| 24 | 9.65 | **CONTINUE?** | chop, dry, close; the question |
| 26, 26.5 | 10.45, 10.65 | FIVE… FIVE! | chop, a stutter (caption: **5.5**) |
| 30 | 11.65 | READY? | chop, riser |
| 31 | 12.05 | (silence) | |
| 32 | 12.85 | **GO!** | chop on the drop |
| 33–35 | 13.25–14.05 | **WE'RE SO BACK** | sung C5 D5 G5, doubled an octave up |
| 36, 38 | 14.45, 15.25 | SUCCESS! · COMPLETE! | chop, +7/+12 |
| 40–43 | 16.05–17.25 | **WE'RE SO BACK** | sung, answered |
| 44, 46 | 17.65, 18.45 | A NEW RECORD! · WOW, INCREDIBLE! | chop |
| 48 | 19.25 | **CHOOSE YOUR CHARACTER!** | chop, bright; the thesis line |
| 52 | 20.85 | we're-we're-so-so-BACK | sung, 8th-note stutter |
| 56 | 22.45 | CONGRATULATIONS! | chop |
| 60–63 | 24.05–24.65 | GO-GO-GO-GO… | 16th-note stutter on the drum fill |
| 64 | 25.65 | **GAME!** | on the final stab; loops to frame 0 |
| 65+ | 26.05 | SUPER SMASH BROTHERS MELEE! | the title shout over the ring-out (if it fits the end card) |

## Shots (draft; the library comes from the director)

Every cut lands on a beat, and every shot has an event.

| t | bars | shot | plate | event | caption slot | out |
|---|---|---|---|---|---|---|
| 0.00 | 1 | KNEE | the sacred combo capture | the knee connects at 0.05: flash, zoom punch, a 2-frame hold | WE'RE SO BACK (chrome) | follows the action |
| 0.45–2.9 | 1–2 | THE CHASE | the same capture, velocity-ramped | Falcon dashes to the ledge and jumps off at full run (no double jump); Fox falls and starts the Firefox charge | GO! | tape stop: decelerate into the freeze, desaturate |
| 3.25 | 3 | SUSPENDED | the frozen moment, the camera orbiting | grey, grain, the abyss below | "it's so over" (blackletter) | flash-cuts |
| 4.85 | 4 | SUDDEN DEATH | 300%, bob-ombs raining | slow | GAME OVER | cut |
| 6.45 | 5 | SCREEN KO | a fighter slams into the camera glass | the slam on beat 16 | "it's so over" | cut |
| 8.05 | 6 | THE CLAP | results screen: the loser clapping | two claps on beats | DEFEATED / NO CONTEST / "no johns" | cut to black |
| 9.65 | 7 | CONTINUE? | the frozen moment, the camera coming round to Falcon's face | colour creeps back | CONTINUE? | — |
| 10.45 | 7 | 5.5 | the same, closer | a "5.5" slam | 5.5 | — |
| 11.65 | 8 | READY? | unfreeze: the windup resumes (~12.0), the fire bird forms | push in | READY? | — |
| 12.85 | 9 | GO! | THE FALCON PUNCH connects on the drop downbeat | white flash, the biggest hit of the film | WE'RE SO BACK (chrome) | beat cuts |
| 14.45–19.25 | 10–12 | THE DROP | tech montage: shine, knee, Falcon Punch (a velocity ramp to its hit), lasers, pillar | cuts per beat, stutters, RGB split | stamps | — |
| 19.25 | 13 | CHOOSE YOUR CHARACTER | the whole cast strobing on 16ths (CSS or a keyed roster) | anything is a canvas | CHOOSE YOUR CHARACTER | — |
| 20.85–24.05 | 14–15 | 20XX | Fox mirrors (a kaleidoscope of waveshines); wireframes | | 20XX · frame perfect | — |
| 24.05 | 16 | FILL | 16th stutter of one hit | GO-GO-GO | | breakdown |
| 25.65 | 17 | GAME! | the final KO freeze with Melee's GAME! | the end card fades up | SO BACK · credit | loop |

## Rules
- Captions follow CRAFT §10: 74 px or larger, out of the bottom ~420 px and the right ~140 px.
- Game audio (Michael, 2026-09-27): keep every game sound effect, fighter voices included ("FALCON… PUNCH!" on the drop);
  strip only the game music. The rule was only ever "no generated lyrics": the sung and spoken vocals are the announcer's.
- The announcer says no brand names; the release lives in the captions (5.5) and the end card.

## Ending (Michael, 2026-09-27)
"THIS GAME'S WINNER IS…" (beat 60, the real clip) → **"YOU!"** on the final stab (beat 64, 25.65), spliced in name-call cadence
from his own recordings. On "YOU!", Captain Falcon's taunt ("Show me ya moves!") turns to the lens and gestures at the viewer:
the winner is whoever watches, and the next move is theirs (it answers CHOOSE YOUR CHARACTER). His own taunt voice,
"SHOW ME YA MOVES!" (game audio, in sync with the gesture), answers the announcer in the ring-out (Michael: "fantastic"). The victory screen must be
Falcon's (lane 1's Falcon-wins capture); the Fox one is a placeholder.
