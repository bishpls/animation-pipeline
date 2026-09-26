# *t*

A 32-second vertical film (1080×1920, 24 fps). Two riso inks on paper, an instrumental, a few lines of kinetic type, and the
function that drew it.

## The idea

A film made in this repo is a function. You give it a moment, `t`, and it returns a picture; ask again 1/24 s later and
you get the next one. It keeps nothing between frames. So if the picture is going to show where it has been, every frame
has to draw the whole past again, from the beginning, from nothing but `t`.

That's the film:
- A pen draws the song as it plays, one bar per line: its height is the loudness of the last 40 ms.
- Each finished line prints and steps back into the distance, and every frame redraws every line so far.
- Lines become shapes, and the shapes become a mountain range at sunrise. It's a landscape no other film could have, because
  its hills are this song's bars, in order: the ticking intro on the horizon, the drop in the middle distance, the last
  groove at your feet.

I work much the same way: each word I write comes from all the words before it. The film says so once, plainly, and then
shows its source.

## The text

Lowercase, one word per eighth note, so the type is written one moment at a time, the way the picture is.

1. *all it's told is t.*
2. *it keeps nothing / between frames,*
3. *so it draws the / whole past again.*
4. *these hills are / the song so far.*
5. *I write like this too:*
6. *each word from all / the ones before.*

Then comes the real source of `frame(t)`, printed by the page itself from `frame.toString()`, so it can only be the function
that drew every frame. It's 12 lines, small on the page, one line per eighth note from the last section's downbeat. The
counter stops at `t = 30.000`.

Every line is literally true:
- The engine's frame function takes only `t` (`engine/core.js`: "no state carries between frames").
- `frame(t)` loops over every bar so far and redraws each ridge from a loudness table.
- The table is the master's loudness, 100 times a second (`assets/env.js`, built by `build_cues.py` from the soundtrack you
  hear).

## The look

- **Paper:** warm cream stock, `#f2ece1`, with the press's fibre and grain.
- **Two inks, two tenses.**
  - **Orange** (Riso Orange, `#ff6c2f`) is *now*: the pen, the line being drawn, the sun, and the dawn's haze.
  - **Federal Blue** (`#3d5588`) is *then*: every printed line, the hills, and all the type, since blue reads at phone
    size and orange on cream doesn't.
  - Where they overprint (the haze on the far hills), they make the only third colour, a warm grey.
- **The present is paper.** The line being drawn has a paper margin and no ink under it. When its bar ends, it flies back
  into the range, still orange, and sets blue as it lands, while ink floods down into its hill.
- **Halftones do the distance.** The nearest hill is solid blue, and each step back is one tint lighter, down to a pale
  haze at the horizon. Each hill's valleys dissolve into halftone mist, and the hill in front rises out of it. The sun's
  glow is an orange halftone halo. There are no digital gradients.
- **Type.**
  - The counter `t = 12.345`: the `t` is Instrument Serif Italic (it's the title), the rest JetBrains Mono.
  - The spoken lines: Instrument Serif Italic, 112 px, on the source's left margin (the first is centred over the counter).
  - The source: JetBrains Mono, 34 px, with ligatures off so `<=` prints as typed.
  - All type prints in blue and misregisters like everything else.
- **Layout for a phone.** The pen draws above the bottom 420 px (the platform's UI), and no type goes into the right 140 px.
- **The camera never moves.** The motion is the pen, the step back on each downbeat, the sun, and the words.

## Line, shape, scene (concretely)

- **Line (bars 1–4, 0–8 s).** A blank page and `t = 0.000`. The orange pen crosses the page once per bar, drawing the
  clock's ticks. Each finished line prints and steps back, and by bar 4 there's a small stack of receding lines, like a
  seismograph.
- **Shape (bars 5–8, 8–16 s).** On the drop, the sun breaks the horizon and its glow spreads. Ink floods down from the
  four printed lines into hills, following the pen as it crosses the page.
- **Scene (bars 9–15, 16–30 s).** The kick comes in, and the peak bars stand as the tallest mountains. The sky warms, the
  sun climbs, and the source prints.
- **The stop (30.000).** The fifteenth line ends exactly at t = 30, and the song's final hit lands 7 ms later. On that
  frame, the pen lifts, the last line sets as a solid hill, and `}` has been printed. The frame holds for 2 s while the hit
  rings out.

## Structure against the music (final)

The song is take e2 at 120 BPM, a 2.0 s bar. It has take d's first 24 s and a new ending, trimmed by 50 ms so the downbeats
fall at 0.007 + 2n s.

| bars | t (s) | music | picture | type |
|---|---|---|---|---|
| 1–2 | 0–4 | a lone ticking clock (lifted 14 dB in the master so a phone plays it) | a blank page and the big counter; line 1 ticks, prints, steps back | *all it's told is t.* |
| 3–4 | 4–8 | the tick, the bass hum | the counter rises to the top; lines stack | *it keeps nothing between frames,* |
| 5–8 | 8–16 | the drop: the full band | the sun breaks the horizon; ink floods the lines into hills behind the pen | *so it draws the whole past again.* · *these hills are the song so far.* |
| 9–12 | 16–24 | the kick: the peak | the tallest ridges; the sky warms; the sun climbs | *I write like this too:* · *each word from all the ones before.* |
| 13–15 | 24–30 | the groove carries on | the source prints, one line per eighth note | — |
| — | 30.000 | the final hit, ringing out | the pen lifts, the last hill sets; held 2 s | — |

## Rules for this film

- Every frame is `frame(t)`, a pure function. No image or video model.
- There's one clock, `assets/cues.json`: bar lines, prints and word landings sit on it.
- One face and size per text role: the counter, the lines and the source.
