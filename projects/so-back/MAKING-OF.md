# SO BACK: making-of

A 29-second vertical hyperpop "hard edit" in which everything you see is Super Smash Bros. Melee and every sung or spoken
word is the Melee announcer. The concept is "it's so over / we're so back". Captain Falcon's sacred combo is frozen
mid-Falcon-Punch through "it's so over", and the punch lands on the drop. Then the announcer tells the viewer "This game's
winner is... YOU!", and Falcon turns to the lens: "Show me ya moves!"

- **Picture.** Rendered by the game itself: the doldecomp/melee decompilation, rebuilt with a director compiled into it,
  captured frame by frame in Dolphin. No video or image model made a frame.
- **Vocals.** Cut from the announcer's own recorded clips on the disc and hard-tuned to the song. No TTS, voice cloning or
  voice conversion.
- **Text.** Melee's own: its word graphics, its menu font and its HUD digits, extracted from the disc.
- **Song.** The one generated element: an ElevenLabs Music instrumental.

*Unofficial, non-commercial fan work.*

The idea draws on pleometric's [brief practical advice for short-form brainrot](https://pleometric.net/articles/brief-practical-advice-for-short-form-brainrot/):
- **Recognition:** Melee, its announcer, its UI.
- **Sensation:** a hyperpop edit.
- **Novelty:** the announcer "singing" lines he never said.
- The article's production recipe is a character on a solid colour, keyed and composited. Here the game engine does that
  itself (below), with no video model involved.

## How it works

```
song (ElevenLabs Music, 150 BPM, C minor)  ──>  the one clock: beat b at 0.05 + 0.4·b s; the drop on bar 9 (12.85 s)
                                                   │
choreography (Python) ─> director tables (C) ─> Melee rebuilt from the decomp ─> Dolphin, headless, one PNG per game frame
      ^                                                                              │
      └───── labs: frame data, momentum, hit logs read back from the game ◄──────────┤
                                                                                     v
    plates: portrait 1080x1920, two-pass keyed mattes, the game's own audio  ─>  the edit (engine, a pure function of t)
announcer clips (disc) ─> spliced, hard-tuned vocal stem ─┐                          │
Melee's text (disc)    ─> word graphics, menu font ───────┴──> captions on the vocal build's own timings ──> mp4
```

## The game engine: custom work in Melee

The director is C compiled into the game (`machinima/melee/director/`, hooked into the decomp behind `#ifndef MUST_MATCH`, so
the same tree still builds the byte-identical original). Every frame it writes the scripted controller states, flies a free
camera, fires cues (freeze, stage visibility, clear colour, reset, percent...) and logs hits, action states and positions
back through OSReport. FRAME PERFECT introduced it; SO BACK added the following.

**Portrait rendering.**
- The film is 9:16, and Melee renders 4:3. Setting the director's projection aspect to 9/16 makes the game's own camera
  portrait.
- At internal resolution 4 the 2560x1920 dump is the portrait view stretched to 4:3. Squeezing it to 1080x1920 gives
  2.37x horizontal supersampling at 1:1 vertically, for about 0.33 s per frame.
- A 90° camera roll is cheaper but rotates the game's camera-facing effects (the shine's flash, hit sparks) against the
  world. A Melee player would see it.

**Keying without a chroma key.**
- Every keyed plate is two captures of one deterministic script: stage hidden, clear colour black, then clear colour grey
  96. The passes are identical except for the background (the colour gap agrees to 2 levels on 99.99% of pixels).
- The difference solves coverage exactly: transmission = (grey − black) / 96, from the channels that didn't clip.
- The black pass is the premultiplied colour, additive glows included. The composite is out = black + (1 − a)·background.
- This keeps the shine's glow, laser streaks and Phantasm afterimages with no spill. A green key dropped the glows and
  turned lasers yellow.
- One catch: on big hits Melee lays a translucent full-frame flash (alpha 0.125 decaying over ~10 frames). Over a bright
  field it reads as a white wash, so the edit inverts most of it per frame, measured per plate.

**The freeze.**
- The sacred combo is one continuous capture on the film clock. The director freezes fighters, items and effects from film
  2.90 to 12.27 s while its camera keeps flying: a slow orbit around the suspended moment.
- Sounds already playing continue through a freeze. Falcon's "FALCON..." starts 10 frames before the freeze (the tape stop
  drags it down), and "...PUNCH!" fires on the punch's own action frame, one frame before the impact on 12.85.

**The screen KO's camera** (cue `DIR_GLASS`).
- A top-blast screen KO places the fighter in the view space of a camera the game refreshes only in its standard and fixed
  modes. Under the director's free camera, Falcon hit the glass of the stale match-start camera.
- The cue syncs that camera to the director's.
- He lands back-first. We checked: a second cue (`DIR_GAMECAM`) hands the camera back to the game, and the vanilla game
  shows him back-first too. The decomp sets his rotation to (0, π, 0), facing away from the lens; only his position lives
  in camera space.

**Victory poses.** The victory screen picks the winner's pose from the button held on his port as it sets up (B, Y or X;
none is random). The kit grew a `menu_hold` to hold it; the ending uses B, Falcon's flying kick into a palm-out guard
facing the viewer.

**A lost frame, found.** Captures lost one image deterministically (script frame 7 of every run, and 2 of 600 in a long
test), with no lag. Two XFB copies landed inside one screen refresh, and Dolphin presented only the second. Immediate XFB
fixed it: every capture since has exactly its script's frame count between the slates.

**Parallel capture lanes.**
- Four scenes were captured at once. Each lane has its own disc folder (its own `sys/` holding its `main.dol`, with `files/`
  symlinked) and its own Dolphin profile.
- An exclusive lock around the 20–30 s build serialises builds while captures run concurrently.
- The kit was shared, so every director change had to be additive (new cues and methods, never struct or behaviour
  changes). Each is logged in `machinima/CHANGES.md`.

**Logs added for the labs:**
- per-frame velocities, knockback, jumps used and percent on the position trace;
- every active hitbox (`HB`);
- the fighters' air-mobility attributes read from the disc (`ATTR2`);
- a reset that also restarts the collision sweep: a reset fighter falling far offstage had been swept across the stage onto
  the far ledge.

## The frame lab: measuring before choreographing

Michael is a Melee expert and reads tech from the logs and frames, so nothing was choreographed from folklore. Each move was
measured in the game first (`director/lab_*.py`, `director/SACRED.md`).

**The sacred combo** (knee, chase offstage, Falcon Punch), per Michael's notes:

*The knee is SHFFL'd:*
- short hop, fair on air frame 3, fast fall on the first descending frame;
- L-cancel: the fair's landing lag drops from 19 to 9 frames (the state log shows 9 frames of LandingAirF);
- Falcon dashes on his first actionable frame.

*The sweetspot:* the knee's hitbox data is 18% at angle 32 on fair frames 14–16 (the sourspot is 6%). The log confirms 18.0.

*The victim:* Fox at 90% holding DI up and in (135°), swept for the highest percent that doesn't kill from that spot. He
flies over the stage and recovers: a double jump, then Firefox.

*The chase is a dash jump, never a double jump* (Michael: Falcon's air speed is middling, and his mobility is carried
ground momentum). The lab confirmed it from Falcon's attributes and the decomp:
- a dash jump leaves at 2.09 and decays 0.01 per frame for 34 frames;
- entering Fall clamps horizontal speed to his air speed, 1.12 (`ClampAirDrift`);
- a double jump resets 1.91 to 1.02;
- running off the ledge drops 2.3 to 1.12 at once.

*The punch:*
- The aerial Falcon Punch's hitboxes start on action frame 51, and a punch started in the jump keeps the momentum, carrying
  him about 90 units.
- Firefox charges for 42 frames and the windup is 51, so the punch lands on charge frame 40: after the fire hitboxes
  (frames 20–32), before the launch (43). A clean hit, no trade.

*After the punch:* Falcon recovers with the double jump and up-B he saved.

**The drop montage:**
- *Waveshine:* Falco crouch-cancels (the chain only holds with the crouch); Fox jump-cancels, wavedashes back with no
  airborne frames and shines again, then a jump-cancelled up-smash inside jumpsquat.
- *Marth's tipper:* the lab found the tip-only zone for a standing Fox at 32–34 units (the blade's 14% wins closer; it
  whiffs past 35). A dashing Fox always ate the blade (his hurtbox leans in), so the tipper punishes an L-cancelled nair
  landing instead.
- *Puff's drill into Rest:* the director's closed-loop fast fall and L-cancel fail on multi-hit aerials (their presses land
  inside the attacker's hitlag), so the drill is hand-scripted: fast fall on 75, L-cancel on 79, Rest on 99 while Fox is
  still in hitstun.
- *Falco's lasers:* B on the 8th airborne frame of a short hop, so the laser spawns at standing height (y 14.96) and hits.
- *Pikachu's Thunder:* on the first actionable frame after the up-throw, catching Fox lying after a missed tech.

**The KOs.** Top-blast KOs pick star, screen or plain by the game's RNG. With the director's seed fixed, attempts 1 and 3
star-KO and attempt 5 screen-KOs. The screen KO needs about 33 s of pre-roll to reach its attempt.

**The roster.**
- All 26 characters in their own taunts, two-pass keyed, one camera per character.
- The camera was solved from measured bounding boxes over 8 lab iterations, so every pose is centred at about 70% of frame
  height (wide poses fill the width instead).
- 14 capture passes at res 4 took 80 minutes.

**Hit timing.** Every scripted hit is checked against the game's HIT log. The director logs hits one frame after they're
drawn, so the delivery records the drawn frame: the knee on film frame 3 (0.05 s), the punch on 771 (12.85 s).

## Vocals: the announcer, cut and retuned

All 152 announcer clips on the disc were decoded from the sound banks and inventoried:
- words and phones by forced alignment (Whisper word stamps refined by a wav2vec2 phoneme model);
- per-syllable pitch from a harmonic-sum tracker (standard trackers octave-jump on his shouted, reverberant voice);
- level, and where each reverb tail ends.

Most of the song uses whole clips as recorded: GAME OVER, CONTINUE, FIVE, READY, SUCCESS, COMPLETE, A NEW RECORD, CHOOSE
YOUR CHARACTER, WOW INCREDIBLE, THIS GAME'S WINNER IS. The words he never said are spliced from his phones:
- **"it's so over":** "it's" from "winner **is**" plus the "s" of "target**s**"; "so" from the "S" of "Sudden" and the soft "O"
  of "Game **O**ver"; "over" from "Game over".
- **"we're so back":** "we're" from "**WI**NS" plus "mast**er**"; "so" from "**S**urvival" plus the "O" of "**No** contest";
  "back" from the "B" of "**B**reak the targets", the "a" of "Master H**a**nd" and the "k" of "**C**omplete".
  The word-final k's on the disc are buried in reverb, so a word-initial one is used.
- **"YOU!":** the "you" inside his own "**Mew**two!" name call (the m cut), crossfaded into that call's falling
  reverberant tail. It keeps the name-call cadence.

Each candidate was judged by three Whisper sizes, alone and in context, plus forced choice against near misses ("we're so
bad", "it's sober") and the spectral step at each seam. The edits are cuts, Praat PSOLA pitch and duration changes, gains
and crossfades.

What the numbers and Michael's ear taught:
- **Keep every syllable within about 5–7 semitones of where it was recorded.** Pushed further, the words stop reading
  ("It's song over").
- **Intelligibility isn't pleasantness.** The first hook was sung high (G4 C5 E♭5) with an octave-up double and a harmonic
  exciter, because speech-to-text liked it. Michael: "very shrill... unpleasant". The hook is now his own spoken words, each
  hard-tuned to the nearest C-minor tone (E♭3, F4, C3: his chest register, ending on the tonic). Energy above 3 kHz fell
  from 7.6% to 3.3%. A low *sung* "back" failed in every form ("glad", "bad", "blood"), so the hook stays close to speech.
- **The mix can erase a consonant.** Over the final song, "back" read as "bad" until its "k" was spliced at its source level
  rather than 4 dB down.
- **Game sound stays in.** Every game sound effect is kept, fighter voices included ("FALCON... PUNCH!", "Show me ya
  moves!"); only the game's music is stripped. The rule was only ever "no generated lyrics".

## The song

The one generated element is an ElevenLabs Music v2.5 instrumental. It was written as a composition plan whose section
lengths are the film's skeleton:
- a cold open that hits on the first beat and tape-stops;
- a sparse, sad music box ("it's so over");
- a riser with a silent beat;
- the drop on bar 9;
- a bigger second drop;
- a final stab.

It took 22 takes. The first choice, c4, was prompted "distorted, bitcrushed". Michael heard its opening as "very harsh",
and "the weakest piece". The next batch was prompted glossy, bright and clean instead, and Michael picked f3: "by far the
best".

The new takes put their drop a bar late (their music box runs a bar longer), so the take is **seated** on the locked grid
(`song/assemble.py`):
- 1.59 s of music box is removed at the CONTINUE? downbeat, where a change is natural;
- the drop's own downbeat then lands on 12.85 s, and the knee, every vocal and every cut stay where they were.

Takes were screened by measurement (grid phase per section, drop onset, key, and a harshness proxy for the cold open).

## Type: Melee's own letters

Michael's note on an earlier cut: "an awful lot of different fonts... if at all possible, use actual SSBM font/text
aesthetics." Every word on screen is now the game's own:

| what | from the disc |
|---|---|
| **Word graphics:** Game!, Go!, Ready, Success!, Complete!, Failure, Time!, Sudden Death | `IfAll.usd` (textured quads) |
| **GAME OVER** | the 1P screen's serif capitals (`GmGover.dat`) |
| **The menu font**, for our own words | read straight out of `main.dol`: a 287-glyph atlas of 32x32 4-bit glyphs, its character map, glyph codes and per-glyph margins |
| **HUD damage digits** (the 5 / 5.5) | `IfAll.usd` |
| **Name plates** (all 26, both sets) | the results screen (`GmRst.usd`) |

- Where the announcer says a word the game draws, the caption is that graphic.
- Everything else is the menu font in the word graphics' dress: outline, white inner stroke, a gradient fill with the
  game's diagonal streaks, a drop shadow. Colour does the section work: the "Game!" red for the hook, the "Time!" violet
  for "it's so over", the "Success!" gold for "YOU!".
- The extraction code is `type/`; the engine module is `engine/meleetype.js`.

## The edit

The picture is a pure function of time in plain Canvas2D (`src/`), rendered headless.
- **Plates play through time maps:** velocity ramps into hits, the knee's triple take, a stutter on the drum fill, and the
  tape stop's deceleration (speed 1 → 0 as (1 − u)², the same curve as the audio's).
- **Preloading follows what is drawn:** before each frame, the frame runs once in record mode, noting which plate frames it
  would draw. Only those are loaded, however the time maps bend.
- **The frozen stretch is bullet time:** jump cuts between the orbit's distinct angles every two beats, each pushing in.
  The grey grade lifts the fighters over the background through the keyed pass's matte, and the KO flashes cut to the
  sung words (the glass on "GAME", the star's twinkle on "OVER").
- **Impact frames:** each big hit's contact frame is left clean so the game's own spark reads, then one negative frame.
- **Text behind the subject:** CHOOSE YOUR CHARACTER! is drawn on the field, behind each keyed fighter.
- **One clock for words and sound:**
  - the captions come from the vocal build's own event list, each word on its syllable;
  - game sound is cut from each plate's own audio at the picture's times and levelled against the song around it.
- **A plain ending:** the game's own GAME! on "YOU!", the taunt, the victory screen, a white frame, and the loop back to
  the knee on frame 0. No end card.

## Review

What moved the film most was Michael's notes:
- the sacred combo, the dash-jump correction, and the SHFFL;
- keep all game sound;
- the shrill hook;
- "YOU!" and "Show me ya moves!";
- the fonts;
- the song.

Frame-level sheets and strips caught the rest, along with objective checks (speech-to-text on the full mix, grid fit,
signal measures).

We also used Gemini as a critic. Its song rankings were pure position bias ("D > A > B > C" three times out of four,
whatever track was in slot D). On the cuts, about one checkable claim in four held up. It invented clicks and a hit at
the wrong time, and called deliberate choices (GAME OVER, the 5.5, Melee's own loser icon) glitches. Treat it as a pointer
at most, and verify everything at full resolution.

## Who did what

**Michael Bishop (human).** Chose the brief, the source article and the Melee canvas, and directed from Melee expertise:
- the sacred combo, the dash jump instead of a double jump, the SHFFL'd knee;
- keeping every game sound;
- the "YOU!" ending and loving "Show me ya moves!";
- no end card;
- the note that the fonts should be Melee's own;
- the ear that rejected the shrill hook and the harsh song and picked f3.

**Claude (Opus 5.5, Claude Code).** Planning, the arrangement, the edit, the mix and this document. Seven subagents
worked in parallel:
- capture setup and the sacred-combo lane;
- the vocal kit;
- the "over" KOs and roster lane;
- the drop-montage lane;
- the drop and ending edits;
- the typography extraction.

**Third parties:**
- the doldecomp/melee contributors;
- Dolphin;
- ElevenLabs Music (the instrumental);
- OpenAI Whisper and a wav2vec2 phoneme model, as judges only;
- Praat through parselmouth (PSOLA);
- Google Gemini, as a critic.

## Numbers

- **Wall time:** about 6 hours of session time, from the brief to the 60 fps master.
- **Claude:** 1,160 API turns across the main session and 7 subagents (1.31 M output tokens), measured from the session
  transcripts.
- **Paid calls:** ElevenLabs Music: 22 takes, 634 s of audio (logged in `tools/ledger.jsonl`). Gemini: about 40 review
  calls (not logged).
- **Captures:** 56 plate sets, 53 GB of game captures (outside the repo).
- **Code:** about 9,400 lines:
  - the edit: 1,150 (plus the engine);
  - the director kit: 1,970;
  - choreography and labs: 3,700;
  - vocals: 2,260;
  - type, song and mix tools: about 570.
- **Render:** 1,728 frames at 60 fps, about 11 ms per frame effective with 6 workers. Review cuts at 24 fps took about 20 s.

## Game data

This repo holds tools, choreography, the edit and documentation, never game data. The disc image, the extracted disc, the
decomp's copy of the game's executable, builds, captured plates, the decoded announcer audio and the extracted type all live
outside it.

To reproduce the film:
1. Dump a disc you own: NTSC 1.02, `GALE01` revision 2.
2. Set up the decomp and Dolphin as in `machinima/README.md`.
3. Build and capture each `director/*.py` script, then prepare the plates (`prep_plates.py`).
4. Decode the announcer banks and build the vocals (`vocals/`).
5. Extract the type (`type/`).
6. Mix (`sfx.py`, `mix.py`) and render (`node engine/render.mjs projects/so-back --frames` and `--encode`).

The kit is self-contained:
- `machinima/melee/build.py` applies every director hook to a stock checkout of doldecomp/melee itself, behind
  `#ifndef MUST_MATCH`, and adds the director to the build. That includes the one addition the menu tests need: the
  character-select token positions.
- Verified on upstream commit `64e41ca`, plus the macOS transcode described in the README. A fresh build ran the sacred
  combo in 1,188 frames and logged the knee (18%) on frame 64 and the punch (27%) on frame 832, the same as the film's
  capture.

This is a non-commercial fan video, the kind Nintendo's Game Content Guidelines are written to allow. Read them before
monetizing or redistributing anything.
