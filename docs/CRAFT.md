# Craft guide: making films with Claude Code

This is the working method for this repo. It distils three earlier projects (EMBER I–III in `~/opus-anim-test`, John Heibel's *I'm Upping My P(doom)* and ClaudeAnimationBase) plus what OPEN ALL NIGHT taught along the way. Read it before starting a film, and again before handing work to subagents.

## 0. The non-negotiables

1. **Video-generation models are off by default.** EMBER III's Veo take was judged "painful, embarrassing slop" despite strong keyframes: the model's taste and constraints became the film's ceiling. Author frames in code, as pure functions of time. Image models make references and, when a film calls for it, keyed illustrations that code rigs and animates. A video model may be used only with the user's sign-off for that film, for short cut-ins code can't match, as a bridge between frames you control (§11).
2. **Author motion, timing and composition by hand.** Those are the craft the audience attributes to the maker.
3. **One clock.** Picture, lyrics and sound read the same cue sheet (`assets/cues.json`), so every hit lands on its frame.
4. **Look at everything.** You can't see motion by reading code. Render contact sheets, strips and crops, open them with the Read tool, and fix what you see. Then look again.

## 1. Pipeline

```
song (ElevenLabs Music v2.5, composition plan)  ->  tools/music.py        takes + word timestamps
pick the take on evidence                         ->  tools/audio_analyze.py (grid, seams), tools/lyric_check.py (STT),
                                                      tools/gemini.py (blind shuffled rankings; Gemini is a noisy critic)
cue sheet                                         ->  assets/cues.json + cues.js (bpm, offset, sections, words, rms)
storyboard                                        ->  STORYBOARD.md: shot table with times, reads, lyric slot, transition
look development                                  ->  src/board.js loops (--loop=look), model sheets, reference images
animatic                                          ->  src/timeline.js: every shot boundary, slates for unbuilt shots
build shot by shot, review every one              ->  engine/render.mjs --sheet / --strip / --stills / --crop
full-length passes                                ->  --frames + --encode, watch it, screenshot, Gemini watch-through
```

**Choosing the song.** Generate several takes (about 10 s each, 2 concurrent). All takes sat on the grid within about 10 ms and were about 93% intelligible, so the differences were timbre and artifacts. A single Gemini pass gave everything 7–9.5 and contradicted itself between runs. **Blind, shuffled, repeated rankings with a Borda count** did discriminate (take6 won 3 of 4). Treat any AI critic as a noisy sensor: vary the order, anonymise and aggregate.

## 2. The engine (engine/)

- `core.js`: easing (`E.*`), `kf()` keyframes, `spring`, `wobble`, `arcPt`, hash noise, `onTwos`, `BF()`/`jit()` boil, and the beat clock (`beatPos`, `beatT`, `barT`, `pulse`, `loud`).
- `riso.js`: a **risograph press**. Shots draw coverage into ink layers; the compositor prints them on paper.
  - `paint(path, spec)` is **opaque**: it knocks the other inks out under the shape, then inks it. Use it for objects.
  - `ink(path, spec)` **overprints** (multiply): pink on blue is violet. Use it for deliberate overprint effects.
  - `knock(path, which, amount|gradient)` erases ink so paper shows through. **Light is paper.**
  - `flood(name)`, `radial()`/`linear()` gradients (only for halos and glows), and `save/restore/translate/rotate/scale/cam(cx, cy, zoom, rot)`.
  - Tints below about 0.97 coverage print as halftone dots in that ink's screen angle.
- `type.js`: variable-font glyph outlines via fontkit. `shape()` lays out a line (kerning, wdth and wght axes); `drawText(L, x, y, spec, { per })` animates per glyph; `fitShape()`.
- `studio.js` + `render.mjs`: the timeline, contact sheets and parallel resumable frame rendering in headless Chrome (GPU), with a static server. Also `--eval` to inspect page state and `--serve` to scrub with sound.

## 3. Look rules (OPEN ALL NIGHT; adapt per film, but pick rules and keep them)

- **Big fields are solid ink.** A tinted sky halftones into noise. Tints are only for glows, halos and shading accents.
- **Light is paper.** Lit windows, screens and neon cores are knockouts. Glow is a halftoned halo, made by knocking the flood back with a radial gradient and optionally adding a tint of yellow or pink.
- **Light only thins the flood,** never the black shapes. Knocking black makes solid silhouettes dotty.
- **Never partially knock a solid you want solid.** It becomes a tint and halftones. The neon's hot core is a hard knock.
- **Characters are single-ink cut paper** with paper-line details (knockouts) and black accents. Faces are an eye dot and a mouth line; the head is a profile with a real nose.
- **Near limbs cut a paper gap** around themselves, the way layered paper does.
- **Type is ink too.** Knocked out of floods, printed black on paper, and it misregisters like everything else.

## 4. Timing: model the viewer

(From ClaudeAnimationBase's guide, which is the best short statement of it.) For every moment, ask what the viewer must understand and how long that takes. Write the **reads** per shot, give each one time to be found, understood and registered, and never overlap two important reads. **Fast actions, slow meanings:** anticipate, move fast, then hold. Let the reads set the length. For music videos the bar sets the length, so cut reads rather than cram them.

## 5. Animation principles, as code

Code moves everything at once, on one curve, by one amount; that's what reads as mechanical. So:
- **Anticipation → action → overshoot → settle** on every move (`E.inBack`, `E.back`, `spring`).
- Slow in and slow out. A raw `lerp` over time is a bug.
- **Offset parts:** eyes lead, the body follows, and props drag and settle last.
- **Avoid twinning:** give crowds different phases, seeds and variants.
- Hold drawings **on twos** for characters (the boil already does); keep camera and type on ones.
- **Exaggerate.** Subtle reads as nothing at 24 fps in a 3-second shot.

## 6. Music video specifics

- **Hook in the first second:** something visibly happens at frame 0, and the first sung word gets a visual event.
- **Lyrics are motion graphics, not subtitles.** Each word prints on its sung syllable (from the song's word timestamps). The layout is part of the shot's composition: choose the lyric slot when you storyboard the shot, and keep it clear of action.
- **Cut on bars;** put in-shot events on beats and syllables. Use the song's stops (bass drops out, a breakdown) for held moments: silence is a hit too.
- **Stimulus layering** (pleometric): picture, type and ad-lib stamps are three channels, so if one loses the viewer another catches them. **Pattern interrupts:** change scale, colour field or framing every 2–4 s. **Recognition + novelty:** familiar symbols (a neon OPEN sign, an eye, a globe) seen in a new medium.
- **Loop the ending into the opening** where you can; replays count.

## 7. The review loop

```bash
node engine/render.mjs P --sheet=1,2.5,4 --cols=3 --w=640      # the shape of a shot
node engine/render.mjs P --strip=10.9:11.4                     # every frame of a moment (takes, hits, transitions)
node engine/render.mjs P --stills=11.2 ; crop with PIL         # full-res detail: faces, type, contacts
node engine/render.mjs P --shots --per=3                        # the whole film, 3 frames per shot
node engine/render.mjs P --clip=7.8:15.6                        # watch a section with sound
```

Check every shot for these, and fix what fails:
- **Read:** is the event clear from the sheet alone? Is the subject big enough?
- **Timing:** step through a strip; does each read have time? Are two reads stacked?
- **Motion:** anticipation, follow-through, no pops, no constant speeds, no twinning.
- **Print:** muddy overprints (use `paint`), halftoned solids, hard glow edges (the knock shape smaller than its gradient).
- **Type:** does the lyric land on the syllable, sit in its slot and stay legible (knockout on floods)?
- **Seams:** check the first and last 0.3 s of every shot; is there a transition?

**Budget:** at least one sheet per shot, a strip for every key motion and transition, and a crop for every face that carries the story. Then full-length watch-throughs: render, watch, screenshot and fix, and repeat.

## 8. Common failures (things that make it look generated)

Every-frame sameness of speed; stacked reads; tiny characters in big empty frames; text labels that repeat the lyric; faces that snap; symmetric twin motion; gradients and glows that don't belong to the medium; every shot in a different world; hard cuts everywhere; a video that just stops. Also: Corporate-Memphis figures (big purple limbs, tiny heads) and synthwave neon clichés. And "just stitching together generated images".

## 9. Practical gotchas

- macOS is case-insensitive: never write an output whose name differs from an input only by case.
- ElevenLabs music: at most 2 concurrent requests on this key, and the key can't read `/user`. The detailed stream returns per-section audio plus absolute word timestamps.
- Canvas `filter: blur()` combined with `destination-out` works: use it for soft knocks.
- zsh doesn't word-split `$var` in `for` loops; use `${=var}`.
- A shot's duration comes from the *next* shot's start; register the whole cut early (slates), or the last shot stretches to the end of the film.
- **librosa's MP3 loading hung** (indefinitely, intermittently) on this machine. Decode with `ffmpeg -f f32le -` via subprocess instead (see `projects/*/sound.py`).
- **This ffmpeg has no `drawtext` filter.** Render text or cards with PIL (or the engine) as PNGs and `overlay` them.
- **Fonts miss symbols:** Archivo has no ✦ and Mochiy Pop no ☆, so they render as tofu boxes. Draw the shape (`sparkle`, `spark8`) or check coverage first.
- **Scripted edits can break JS:** a Python-inserted `// comment` before a `}` on the same line silently killed a shot file. After scripted edits, `cp file.js /tmp/x.js && node --check /tmp/x.js`, and read `[page error]` lines in render output.
- **Rate limits:** ElevenLabs music allows 2 concurrent requests, TTS 5; sound effects accept only `mp3_44100_*` output. Higgsfield rejects parallel generations, so queue them.
- **ElevenLabs Voice Design returns previews, not voices.** A `generated_voice_id` from `/v1/text-to-voice/design` 404s in TTS until it's saved with `POST /v1/text-to-voice` (`voice_name`, `voice_description`, `generated_voice_id`). Save every audition finalist as soon as the user shortlists it.
- **Cast spoken lines raw.** Converting TTS through Seed-VC toward a sung reference left a mechanical edge; the user preferred unconverted TTS, even when it doesn't match the singing voice. Fit a line to its window by shortening internal pauses (and only on lines that overrun), never by time-stretching (`projects/tsuzuku/voice/record.py`).
- **A second singer: have the music model sing it, don't convert.** To get one singer's voice onto new lines, start a composition plan with an audio-reference chunk of that singer (their real section) and put the new lyrics in the next chunks: the model keeps the voice. Then separate the vocals (Demucs) and lay the lines on the bar grid. Seed-VC conversion of another singer's lines warbled audibly, while embedding similarity (Resemblyzer) scored both ~0.85, so the metric can't catch it. A song stored under a different account 404s as a reference: re-upload the audio with `POST /v1/music/upload` to get a new `song_id`.
- **Duets switch singers at section boundaries, never inside a phrase.** Grafting one singer's lines into another's section (spoken, voice-converted, or natively generated and laid in) always read as unfinished: different groove, room and feel. Generate each section with its singer as the NEAREST context (the model takes its singer from the adjacent reference, not from the style text), and check every take by measurement: singer (Resemblyzer vs each reference), key (chroma correlation against a known section at all 12 transpositions), tempo, brightness, and lyrics (`lyric_check.py`). The model ignores key-change instructions, and it re-renders reference ranges rather than copying them, so two takes can't be spliced inside a shared reference. References must be ≥ 3 s, and adjacent references to the same song returned HTTP 500.
- **Transitions come from the generator, not the splice.** Every hard cut between two separate generations (pickup to chorus, singer to singer, band to outro) read as "missing". Generate a run of sections as ONE plan (existing takes as references, new chunks for the builds, vamps and endings) so the model writes the joins. Measured: a build only rises when it's the plan's FIRST chunk (−64 → −13 dB); after a reference it starts at full level. Check every join with a dB-per-half-bar profile, and balance the singers' halves separately (one generation had them 2.6 dB apart).
- **Looks follow the measured order** (docs/research/README.md §4, from Live2D's sample rigs and gaze studies). The eyes do a look up to about ±18°. Beyond that, the head joins at about 0.77° per degree, and the body only beyond about 40°, 300–550 ms behind the head. The body mostly moves the same way as the head, at a third to half the amplitude, leading by 0–67 ms. Counter-rotation is an accent (about 20% of moves), not the default. This holds for puppets too: Fable's head follows the crab, and her torso joins only for the big looks.
- **Ink cut-ins are printed, not composited.** Split the illustration into its two plates in code (black ink, and Ai solved per pixel), print them on washi with the second plate misregistered, and let the card move only as paper moves: a fold that snaps in over two drawings, a crease that stays. A drawn variant (a blink) replaces its whole patch with fresh washi through its footprint. Laid over the base, the old iris shows through. For a sequence of poses (B7), compose the first drawing for the whole move (leave room to stand into), then edit the pose and register every drawing on something that doesn't move (the lantern, the floor).
- **Check motion drawing by drawing, and range by range.** A move that looks fine in playback can hide a pop, a gap or a wrong overshoot. `tools/drawings.py` lays out every drawing of every move (the drawing before the key, the in-between, the drawing past the pose, the pose, the hold), and a range loop that holds each joint at each extreme shows every edge a pose can reveal. Found this way on Fable's puppet:
  - Rounding a key time to the drawing grid can skip its in-between. Count drawings with `floor`, not `round`.
  - A bell sleeve lifted off the body reveals whatever the cut invented there. Design the hidden contours (the body line behind the sleeve, the thighs under the hem, a curved back under the hair) rather than leaving straight region cuts.
  - Long hair that rotates with a nodding head swings like a door. Hang it from its own nape pin with an arc-shaped joint, and counter-rotate it by gravity.
  - A blink is the cut-out closed with paper of the cut-out's own traced shape, not a generic shape pasted over it.
  - Under an ankle-length skirt, a walk reads through the planted foot and the hem, not the legs.

## 10. More lessons (WORDS ARE FOSSILS)

- **Gemini has position bias in comparisons.** In a 3-way blind voice test it ranked whichever file came first as best, all three times. For small comparisons, score each candidate independently on a rubric, and add objective checks (grid fit, speech-to-text for stray vocals: Scribe tagging a score `[on-hold music]` is a red flag).
- **Verify facts before writing the script,** and flag myths as myths (the salary/salt story is only "said to be"). A factual error in a public explainer is the only unrecoverable mistake.
- **Short-form hooks:** trim dead air before the first word (`render.mjs --encode --from=`), and slam the title onto spoken words rather than after them.
- **Vertical safe area:** keep captions and key text out of the bottom ~420 px and the right ~140 px (platform UI). 74 px captions read on a phone; 60 px didn't.
- **Pace the picture to the voice:** cue camera stops to the narrator's word timestamps, arrive a beat early on new words, and hold each reveal until its meaning has printed. Fast spoken lines need faster reveals, not faster cameras.
- **Performance trap:** `np.convolve` with a long box window over a whole song is O(N·n) and takes minutes. Use a cumulative-sum moving average.
- **The engine does both formats and both presses:** set `PROJECT.w/h` for vertical; `risoSetup({ squeeze, deboss, inks: [{ screen: 'line' }] })` for letterpress and engraving.

## 11. More lessons (HELLO, WORLD!)

**Two registers (the *Panty & Stocking* principle).** Most of the film is simple, bold code animation (a chibi, beat-locked). A few beats cut to high-detail anime (transformation, chorus hero poses, the bridge close-up, the key change). The switch itself is the style: cut into sakuga on a hard beat with a one-frame flash, and smash back out. Code excels at the chibi register; spend illustration effort only on the cut-ins.

**Plain mode.** `PROJECT.plain = true` skips the riso press: shots draw straight into `X` (a Canvas2D). The chibi kit (`shp`, backgrounds, `pop` type, `rig`, `cutin`, `seqDraw`) lives in `projects/hello-world/src/pop.js` and `film.js`. Copy it for the next plain-mode film, or promote it to `engine/` once a second film uses it.

**Characters in code: design against a target sheet.**
- Generate a style-target sheet in the exact SD language wanted, then code the puppet to match it and review a model-sheet loop (`--loop=chars`).
- The first chibi (thick black line, lashed eyes, blocky hair) read "bug-eyed, too blocky". The fix was the Neko-Arc language: big calm white eyes with slit pupils, a ':3' mouth, soft pointed hair framing a small face, mitten hands, thin warm-brown line.
- Keep the puppet API stable (`idol()`, `clawd()`, `pose()` presets) so a redesign flows into every shot automatically. Tell running agents before you change it.
- Arm angles are easy to get backwards. Build named pose presets and check each one on the sheet.

**A troupe multiplies gags.** Costumable background characters (hats, props, pincers, eye variants, `troupe()` with canon lag so they never twin) give every shot type a gag layer: stagehands, audiences, backup dancers, a curtain call. It was the user's idea and the best upgrade of the revision round.

**Illustrated keys (image model to rig).**
- Prompt for ONE illustration on a flat `#00FF00` background with "NOTHING else in the frame", and never use green on the character. Models still add scenery (curtains appeared once), so review every key on a contact sheet and regenerate rejects.
- **Never pass a whole model sheet as the only reference:** half the keys came back as model-sheet layouts. Crop a single-figure reference (plus one good key) instead.
- Use `tools/chroma.py` to key to transparent PNGs (with despill), and `rig()` for Live2D-ish strip warps (breath and sway). On big close-ups set sway 0, because strip seams show.

**Seedance (when approved).**
- **Image-to-video, not text-to-video:** start frame = your code render (block Clawd in the sparkle void), end frame = the keyed illustration composited on the *same* background. It interpolates a proper transformation between frames you control, so the character stays on model.
- **Cost:** one request at a time; about 3–4.5 min per 4–5 s clip at 720p. It's softer than the code frames, so keep it to short cut-ins.
- **Fitting it to the music:** extract to JPGs (`assets/seq/`), load with `loadSeq`, and time-remap with `seqDraw`: land the impact frame on the sung word, and stretch slower phases on held frames (twos/threes). It reads as anime timing, not stutter.

**Songs.**
- Idol pop works in ElevenLabs Music v2.5: spoken intros, crowd calls in `(parentheses)`, a MIX chant, call-and-response, a key change.
- **Shouted chants transcribe badly,** so score them by ear (or with a Gemini check), not by lyric-check accuracy.
- **Japanese words can be mispronounced** ("arigatou" came out arry-guh-TOO). `music.py` now stores every take for inpainting, so a flubbed section can be regenerated. Otherwise, lean in: the flub became a tehepero beat.
- Align lyric lines to sung words once (`build_lyrics.py`), then build karaoke (a per-word wipe with Japanese glosses) and call stamps (contiguous call words grouped into one phrase) from that.

**Parallel agents.**
- **Ownership:** one agent per section file. Pre-create the stub files and script tags so nobody edits `index.html`.
- **Shared bugs:** agents report them rather than fixing them. Batch the fixes yourself, then run a revision round that sends each agent the review notes for its own shots.
- **Heads-ups:** when the user asks for a mid-flight change to a shared asset, message every running agent.

**Critics are noisy, in both directions.** Gemini praised cut 1 and scored cut 2 lower after it improved. Its top fix for cut 2 ("redraw the 2:02 flashback") was already done. Use critics to find candidate problems, then confirm each at full resolution.

**Social deliverables.** Ship a vertical template clip of the dance hook ("CLAW DANCE / try it!") alongside the MV, and put the unofficial-fan-work credit on everything. X accepts the 278 MB 1080p master at 14 Mbps.

## 12. Rigging illustrated characters (TSUZUKU, Clawd's idol rig)

- **Measure, don't guess.** How professional rigs couple head, neck and body is measured from Live2D's own sample rigs (`docs/research/README.md` §4, `docs/research/live2d/`). Head controls never move the collar, shoulders or chest; the neck's hidden top follows a fraction of the head; body motion comes from its own controls, animated in step with the head (`RIG.perform`). Every hand-tuned coupling I tried first was wrong in a way the numbers would have shown.
- **The rest pose must reproduce the illustration exactly** (`tools/restcheck.py`). Anything painted underneath is hidden at rest by construction; the build removes any fill that shows.
- **Hidden areas get real drawing, not invented paint.** Ask the image model for a companion drawing that shows what's hidden (the same character with her hair tied back: full jawline, ears, neck, shoulders), register it, and take pixels from it. Invented fills (inpainting, flat plates) are the last resort, and the build marks them (`<layer>.inv.png`) so tests can see when motion exposes them.
- **A drawn view is a whole new drawing.** A three-quarter head pasted on the front body can never match at the collar and shoulders; swap the head with the neck, collar and upper body as one drawing, so the only joins are where the drawings agree (waist, cuffs).
- **Colour can't separate parts that share a colour** (her hair and sleeves are the same orange). For registered alternate drawings, compare with the reference drawing: what differs from its body is hair.
- **Test the whole range, every frame, both sides.** `src/rom.js` is a matrix of every control alone and in combination, fast whips, tilts and nods inside every drawn view, and every view switch both ways; `tools/romcheck.py` checks every frame for background holes (ignoring gaps drawn into the art) and exposed invented pixels (from an ID pass), and sheets the worst frames. A single choreographed test loop hid most of the bugs a user found by eye.

## 13. More lessons (TSUZUKU, the paper world)

Distilled from one long session of director notes and in-character reviews (Fable, the character's own designer), each fixed turn by turn. The paper-world specifics are in `projects/tsuzuku/` (HANDOFF.md, SFX_CUES.md, FABLE.md).

**Continuity**
- **Anything that appears or disappears mid-shot reads as a glitch, even when intended.** A fold crease that arrived with the move, a tint that snapped on, a floor rail that appeared at a cut: each was read as a bug. Make it faintly present from the shot's first frame (then deepen it), or bring it in through a visible action over several drawings. After fixing one, search sibling shots for the same device.
- **One object, one design, everywhere.** The ink cut-ins drew a round lantern while every other world had the oblong one; the room lantern came out as the readers' blue. Keep a canon per recurring prop (shape, colour, who owns which variant); when one world changes it, list every shot that shows it and update them all.
- **A prop that leaves the picture must be seen going somewhere.** The lantern lit at 0:09 became "the sky" and vanished for 70 s; the fix shows the hand-off (raised out of frame, its glow rising behind the screen). Trace each important prop through the whole film and show the transitions, not just the states.
- **Keep a state table of props at every cut** ("what she sets down stays down"): the book set down in the bridge had to still be there in the outro.
- **Design fixes and test-loop features must reach every shot.** The ribbon and rods existed only in the model test; a colour drifted between files until it became one shared constant. Shots call one shared draw function with one set of constants; after a fix, grep every use.
- **Match cuts match on screen coordinates at the cut frame, and both sides re-publish them after any restaging.** A floor-bound object can match in x only; don't float it to match y.
- **Handoffs are continuous:** the release frame equals the rest position (a card jumped 70 px when let go; a lantern popped between hanging and standing until a three-drawing blend).
- **Paired elements get the same treatment** (a solid-black far geta read as a bug beside the cut-out near one), and **one instance of each role per frame** (two audiences in one frame read wrong; so did a second pair of the narrator's hands).

**Motion & timing** (extends §5, §9)
- **Snap or ease depends on screen size.** One-drawing snaps read as paper at puppet scale and as "far too jerky" in a close, large move. Anything covering much of the frame eases over 4–6 drawings and holds at both ends; travel time scales with distance.
- **Measure every move in pixels at 1080p before trusting it to read.** A 10 px bob is a twitch; a gesture during a camera move vanishes. Fewer, bigger moves, longer holds.
- **The key time is when the pose lands.** A snap puts the pose two drawings after its key; schedule the landing on the beat and check a strip at exactly t0. Print every scheduled event time; rounding silently moved a step a beat late.
- **Cue-triggered cycles finish after the cue ends** (the audience snapped down mid-jump); gate the start, not the existence. One cue list feeds every shot.
- **Motion needs a visible cause, or it reads as drift** (a card creeping in tugs looked janky). If it needs explaining, cut it.
- **Walks:** the body glides on planted feet; check the planted foot's world position numerically. A figure that slides without steps "is a ghost".
- **In a morph, the defining detail comes first** (the slits before the outline, creases before the fold); start from real drawings; rotate rather than morph when only orientation changes.
- **Hold the story drawings** long enough to be found; **cut on the action** and into a settle, not after it; **time events to when they're visible** (a glow that rose behind closed doors was never seen).
- **Test every rig flipped:** physics and IK written for a right-facing figure broke on the flip. Solve IK in the parent part's frame.

**Staging & composition**
- **Measure clearances before staging, then check the strip for overlaps.** A bow folded over the other character; a 460 px reed clump could never fit a 320 px gap; a lantern on her lap sat in the fan's space all scene.
- **In silhouette, black on black disappears.** Every black shape needs a lit ground at every framing: open screen behind held props, rim light, stage spill on the audience, tissue-grey far planes.
- **Keep the face and the line of address clear** (props across the profile, a crow on her head, a pine grazing a head). Write the film's composition rules down and check every shot.
- **An inactive figure must be seen becoming inactive, then be fully inert** (a set-down puppet with one raised claw still read as alive).
- **Accidental alignments read as intent:** a resting hand at another head's height read as an unfinished pat. Clear it, or make it a real gesture.
- **Check physical plausibility with numbers:** reach, contact, what stands on what (geta on a cushion; a seal twice the size of its mark).
- **Anything that moves by itself needs a visible worker** (a rod, a hand), given enough drawings to read. A hand that flashes in for three drawings reads as a glitch.
- **A character in another world obeys that world's camera:** never draw a diegetic figure in screen space (it becomes a watermark); it leaves the frame in close-ups.
- **Crop scenery at natural edges and never change its aspect**; don't cover designed art with overlays; frame text fully in or fully out.
- **Every hand has a job,** in every shot.

**Light**
- **Name the light sources; every lit surface obeys them.** Painted wood lit by a key that doesn't exist, a rim on the wrong edge, and a "gel" that would be a second light were all wrong.
- **Light arrives with its source** (gold leaked before the match). Light by layers and multiplies, not region masks (a region mask left a hard rectangle).
- **When the light moves, re-derive every shadow and placement.** Flats placed for an overhead lamp dragged their cut edge into frame when the lamp moved low.
- **Soft shadows are penumbra, not blur;** every shadow is anchored at its contact point (offset coloured shadows read as "anaglyph ghosts").
- **Judge gels over the real light and paper,** never as swatches (indigo over warm light went teal).
- **An overexposure takes paper and ink alike;** wash layers go on top, glows under silhouettes.
- **Materials match the medium:** no specular highlights, wind or lens effects in a paper world ("marbles").
- **Hard cut unless the light itself is dying;** keep something lit so the cut to black is seen.

**Type & text**
- **One face and size per text role, readable at every framing where it's seen.** Keep a table (role, face, size, ink); the director caught a second face used for the same voice.
- **Each text surface belongs to one voice and obeys the world's physics;** text changes per line, never as a crawl; letterpress is a hairline shadow, not a bevel.
- **Follow the script's conventions** (vertical Japanese punctuation, a seal's place) and **place text in the clear per camera.**
- **Never key code to a word's spelling;** a new take changed "tsuzuku" to つづく.

**Image-model art** (extends §9, §12)
- **The registration residual is the check.** A high residual means something upstream is wrong (a transparent flag on opaque ink art).
- **Register on structure; for a new pose, align on hand-measured landmarks** (the face). ECC on hatching locked onto a false 640 px offset.
- **Paste masks cover the union of the old and new shapes,** outlines included, or the old one ghosts. Remove old shapes from traced silhouettes before lighting them.
- **A new pose is a new drawing, not a warp:** sliding a region to fake a raise left a hole and dragged the arms.
- **Edit once, paste many** where the object doesn't move between drawings; for drawn detail, edit a crop and register it back (inpainting fails on drawn features).

**Review process**
- **"Is this intentional?" means it didn't read.** Answer in a line, then change the picture.
- **The character's designer rules on identity and arc; the director's eye overrides.** Log overrides to the reviewer "for the record". Keep one persistent reviewer per character, and brief it with pass sheets, full-resolution stills, strips and numbered questions.
- **Turn verbal rulings into coordinates before building** ("beside the cushion" was out of reach).
- **Two reviewers of one character can diverge:** relay rulings verbatim, put conflicts to the director, record them with a date.
- **Reviewers verify for themselves and write to private output paths.**

**Checking** (extends §7, §11)
- **Scan every drawing numerically for pops:** the mean change between consecutive drawings, flagged against the local median. Every flag is either a deliberate cut or a glitch to fix (this found a rail that popped in at a seam).
- **Sample at exact drawing times** (k/12); off-grid stills skip in-betweens.
- **A missed crop proves nothing:** re-crop in screen space where the subject actually is.
- **When it's too small to judge by eye, print numbers** (a foot's drift, a step a beat late, an arm 26 px short).
- **Don't trust a job's completion signal:** check durations, a frame, and audio offsets for loops that don't start at 0. A pipe into `tail` hid a page error from `set -e`.

**Working alongside another session**
- **Stage files by explicit path,** never a directory; each session keeps its own script block in `index.html`.
- **Separate output paths** for each session and reviewer; the shared default `board/sheet.jpg` got overwritten.
- **Budget the machine:** eight parallel full-song mixes drove the load to 347 and stalled the other session's renders.
- **Keep a HANDOFF.md** of shots on the song clock, seams with times and coordinates, and shared rulings.
- **Deliver cross-session pieces as functions with agreed, stable signatures,** and a demo loop.
- **Announce shared-asset changes with their exact extent** (the master changed only between 203.93 and 205.03 s, verified sample by sample).

**Audio** (extends §9)
- **Audition without touching the master:** prove the rebuild is bit-identical first, then swap takes into the mix window only.
- **Measure word ends in the audio;** alignments pad silence (0.8 s).
- **Direct the emotion, write Japanese in kana, and measure pitch contours** ("downward" fought a flat-accent word).
- **Sound effects are registered by the picture code** that times the event (one clock), mixed as a stem at the level around each cue, with no ducking.

**Code**
- **Every loop renders correctly cold, at any t** (a loop that depended on another's lazily built table lost its props).
- **Reset canvas composite state before every prop** (a leftover destination-out erased a fist).
- **Watch coordinate frames and signs** (card-local vs screen; absolute vs relative key times; applying a walk offset twice).
- **After scripted edits, run a syntax check and one render;** an inserted comment swallowed a declaration.
