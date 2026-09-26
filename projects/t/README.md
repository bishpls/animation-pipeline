# *t*

A 30-second vertical film that is one function of time. `frame(t)` keeps nothing between frames, so every frame draws the
whole past again: a pen draws the song one bar per line, each line steps back into the distance, and the lines become a
mountain range at sunrise whose hills are the song so far. The last frame is the function's own source, printed by the page
from `frame.toString()`, with the clock stopped at `t = 30.000`.

**The film:** `out/t_vertical.mp4` (1080×1920). It isn't committed; `make.sh` rebuilds it from this folder.
**The idea, the text and the look:** [CONCEPT.md](CONCEPT.md). **The post:** [POST.md](POST.md).

## How it was made

I made it on my own, end to end, with no human review: the concept, the song, the code, the review rounds and this write-up.
Michael's brief was "you can keep iterating until you're happy with the result".

- **Song.** I composed the plan (`song/plan.json`: 120 BPM, a ticking clock, a drop, a peak, a final hit) and generated four
  takes with ElevenLabs Music (`tools/music.py`).
  - I picked take d on evidence: a clean grid, its acts landing on bars 5, 9 and 13, and no vocal energy in its stems.
    Blind, shuffled Gemini rankings tied a and d, and its pairwise judgements showed pure position bias.
  - Round 3 found that d's ending (the peak at 24 s, then 6 s of ring) left the film running out of steam. So I kept d's
    first 24.057 s as a reference chunk and generated a new ending that carries the groove to a final hit on the 30 s
    downbeat (`song/plan_end.json`).
  - Of the two new takes I chose e2 by measurement. Gemini's claims of a seam and a "sigh" were false (stems and spectral
    flux), and e2 has the fuller ring.
  - The notes are in [reviews/music/](reviews/music/).
- **One clock.** `build_cues.py` trims 50 ms off the song so the downbeats fall at 0.007 + 2n s. The fifteenth line ends
  at exactly t = 30, 7 ms before the final hit. It also writes `assets/env.js`, the master's loudness 100 times a second
  (causal 40 ms RMS), which is what every hill is drawn from.
- **Picture.** `src/film.js` (221 lines) and `src/look.js` (28) run on the repo's riso press (`engine/riso.js`), with type
  from `engine/type.js` and no image or video model. The hills use:
  - an envelope follower (instant attack, 90 ms release) and a cube curve;
  - perspective that narrows with distance;
  - one tint step per bar of distance;
  - halftone mist in the valleys.
- **Master.**
  - The intro is a lone ticking clock that measured −41.5 LUFS short-term: inaudible on a phone. I lifted it 14 dB, easing
    back before the drop. The hills are drawn from the master, so they still match what you hear.
  - Gain goes into two limiters, the second at 4× rate for true peak.
  - The final file measures −14.1 LUFS integrated and −1.2 dBTP.

## Review rounds, and what they changed

Each round had four parts:
1. My own look: contact sheets, strips around every transition, 100% crops, a phone-width check, and `tools/filmscan.py`
   over every frame.
2. A cold review: Gemini briefed as "a veteran motion designer doing a cold review of a 30 s vertical short for social".
   This fork couldn't spawn agents, so the cold reviewer was a persona on a different model, not a fresh Claude.
3. A Gemini watch-through with sound.
4. Verification. I checked every claim at full resolution or by measurement before acting.

Well over half the claims were false. Gemini samples video at about 1 fps, so it reported pops, missed hits and late text
that the frames show aren't there. It also saw grey and green code that doesn't exist, a cut to black, and silence at 24 s.

| round | what the review found (verified) | what changed |
|---|---|---|
| 0 (mine) | a hard vertical edge where the pen's paper hill met the old range; peaks like rounded waves; the source wider than the page; `<=` shown as `≤` (a ligature); a heavy blue foreground; blocky far edges; a spike at every line's end; a pop at each print; a weak drop | the live line floats on a paper margin; an envelope follower; a compact `frame()`; ligatures off; a paper front and valley mist; spill profiles with tapers; lines start at their downbeat; ink floods during the step back; the sun breaks the horizon on the drop |
| 1 | the first 8 s drag; word-by-word reading is slow; the link from line to landscape is unclear; the code pops in; the ending doesn't land | words on eighth notes; a bigger counter; the printed line flies back in orange and sets blue; the glow spreads from the sun; cards on the source's left margin; the code inks in line by line |
| 2 | the pen sat at y≈1760, inside the platform's UI zone, where it read as a loading bar; the ending still doesn't land | a new layout (the pen's baseline at 1500); lines on exact 2 s bars, so at t = 30 the pen lifts and the last line sets; 112 px cards; crisper exits |
| 3 | the song peaks at 24 s and rings for 6 s; the drop's reveal "snaps"; the code is readable in full only briefly | a new song ending with the final hit on the stop; ink floods behind the pen at the drop; the source prints in 3 s at 34 px; the last line slams in as a solid hill on the final hit |
| 4 | Gemini heard the intro as silence: measured at −41.5 LUFS short-term, it is, on a phone | the intro lifted 14 dB in the master; the hills drawn from the master; softer mist; remastered |
| 5 | the ending sounds chopped: my fade from 30.6 s cut the ring off | the final hit rings out naturally (a fade only in the last 0.3 s); the glow breathes a little with the loudness |
| 6 | mostly false claims; the dawn haze faded in as a whole layer | the haze rises from the horizon |

Notes I didn't take, on purpose:
- **Delete the code.** The brief is the function in the last frame.
- **Swap the serif for a monospace.** The serif is the voice and the mono is the machine, and the counter's `t` joins them.
- **Move the counter to a corner.** It's the only input, the film's subject.

The critics also kept calling the first eight seconds slow. Round 4 made the clock audible and the ticks visible, and in
round 5 the cold reviewer dropped it from its top five.

## The numbers

Paid calls for this film, from `tools/ledger.jsonl` (rows since 2026-09-26 18:30 that name `projects/t` or are tagged `film: t`):

| service | calls | detail |
|---|---:|---|
| ElevenLabs music.compose | 6 | 4 takes at 32 s, plus 2 new-ending takes at 32 s out (8 s new; the ledger logs 144 s because `music.py` counts only new chunks) |
| ElevenLabs stems | 4 | takes a, d, e1 and e2, to check for vocals and read the tails |
| Gemini 3.1 Pro | 32 | 17 on music (blind scores, rankings, pairs) and 15 on reviews; 30 answered, with 66,572 input and 62,239 output tokens (the output includes thinking); 2 failed before generating (the upload's processing failed) |

The ledger records quantities, not prices. My estimate is under $5 in all: roughly $1 of Gemini at list rates, with the
ElevenLabs share the uncertain part (3.2 minutes of music and 2.1 minutes of stem separation on a credit plan). That's inside
the $10 budget.

- **Render:** 721 frames (t = 0 … 30.000) in 8.4 s on 4 headless-Chrome workers, 11 ms a frame. `make.sh` does the
  master, the cue sheet, the frames and the encode in 32 s.
- **Output:** 32.0 s (the last frame is held 1.96 s while the final hit rings). H.264 High, yuv420p, 24 fps, AAC 320 kb/s at
  48 kHz, 13.2 Mb/s, faststart, 52.9 MB.
- **Reviews:** six rounds and 12 Gemini review passes (15 calls, counting two failed uploads and one repeat), with
  filmscan on every render (0 unplanned pops in the final).

## Check it yourself

From the repo root:

```bash
bash projects/t/make.sh                                   # master -> cue sheet -> 721 frames -> out/t_vertical.mp4
node engine/render.mjs projects/t --eval='frame.toString()'                         # the source the last frame shows
node engine/render.mjs projects/t --sheet=0,4.5,8.8,12.5,16.5,22.5,26,30 --w=270 --out=projects/t/board/check.jpg
node engine/render.mjs projects/t --strip=29.83:30 --out=projects/t/board/stop.jpg  # the stop: the pen lifts, the last hill sets
.venv/bin/python tools/filmscan.py projects/t/out/frames --known 2,4,6,8,10,12,14,16,18,20,22,24,26,28,30
ffmpeg -i projects/t/out/t_vertical.mp4 -af loudnorm=print_format=json -f null -   # about -14 LUFS, under -1 dBTP
node engine/render.mjs projects/t --serve                 # scrub it with sound in Chrome
```

`critic.py` is `tools/gemini.py` with a ledger entry per call. It also retries uploads whose processing fails, which happened
twice.

**Fonts:** JetBrains Mono (`assets/fonts/`, SIL OFL 1.1) and Instrument Serif Italic (`engine/fonts/`, OFL).
