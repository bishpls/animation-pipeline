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
