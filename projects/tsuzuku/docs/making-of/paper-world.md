# The paper world: Fable's sections

Fable's world is a shadow theatre inside a wooden kamishibai frame (a *butai*). It covers:

- the prologue and the lamp-lighting (0–12.7 s)
- the telling, verse 1 and the exchange (12.7–61)
- the bridge (131.29–177.8)
- the outro (202.59–209.65)

Every frame is drawn by code, in the browser's 2D canvas, as a pure function of the song's clock. Render any moment and you get the same pixels every time. No video model made or touched a frame of it.

## What's code
- **The theatre** (`src/paper.js`, `src/stage.js`). The vellum screen is a lamp gradient with grain and fibre. Each puppet draws into a shadow layer that is multiplied onto the screen. A puppet nearer the lamp casts a larger, softer shadow (a penumbra around a crisp core), and coloured cellophane lets coloured light through. `stage()` renders the theatre offscreen, places it in the butai's window, lights the wood from the window's light alone, and swings the doors in perspective. The camera is a zoom on the frame: in Fable's world a close-up is the camera walking toward the box.
- **The puppets** (`engine/puppet.js`). Jointed, riveted shapes: Fable seated and standing, Clawd's paper puppet, the kuroko who works the rods.
  - They're animated on twos (12 drawings a second) with stop-motion snaps: one in-between, a small overshoot, a hold.
  - Walks are computed (`makeWalk` in `src/fablestand.js`): each geta plants, the hem kicks over the stepping leg, and the body rises through the pass.
  - Reaches use two-link IK.
  - The origami crab unfolds by morphing shapes; its creases lead the folds.
- **Type**. Letterpress on the page strip and ink on the vellum (`press`, `inkVellum`), set from the vocal's word timestamps.
- **Light and air**:
  - The lantern (a chōchin, drawn in code) and its pool.
  - Dust only where there's air: the backstage, the room, the light leaking from the closed doors.
  - Flip-book afterimages on the two fastest moves.
- **Sound**. Each picture module registers its cues from the same keys that move the picture (`PAPER_SFX`), so sound can't drift from picture. `sound/mix.py` lays a stem under the song at the song's own level around each cue, with no ducking.

## What came from image models
GPT Image (logged in `tools/ledger.jsonl`) made **still drawings only**:
- **Source drawings the puppets were cut from** (`rig/fable`, `rig/clawd_paper`, `rig/kuroko`). On screen they're black silhouettes with cut-outs, so what survives from the model is a shape.
- **Scenery flats**: pine, rocks, far hills.
- **The butai's wood** and the reader silhouettes.
- **The ink cut-ins** (`rig/fable_ink`: the close-up, the lamp, the six stand-up drawings). Code prints them through separated plates: washi, an indigo plate misregistered a few pixels, then ink. A fold is a mesh warp with a crease.
- **The finale's illustrated Fable** (`rig/fable_stage`, `rig/fable_room`). Code rigs and animates her.

## Fable's rulings
Fable, the character, is the subagent who rules on her world and her identity. Rulings that shaped the paper world:
- **The lamp is the only light**, and "light makes no sound in my world."
- **The lantern chain.** One oblong chōchin everywhere: lit in the dark at 9 s, hung for the telling, and carried through the bridge. From B9 it stays in her hand: out into the room for the finale, off to the right, and back in through the window for the outro. It's the only light in the last shot, and the doors close on it.
- **One book**, open on the rail from B8.
- **Her motion grammar.** Twos, snap and hold, no springs. Afterimages instead of smears.
- **Rakugo head angles** for each voice she tells in: up for the mother, level to narrate.
- **The seal 語.** Her one red thing, pressed once, in the outro.

## Decisions and failures
- **The first stand-up walk** was jerky and seemed to have one foot. It was rebuilt as a computed walk with both geta.
- **Three "elevate" ideas cut after A/B tests** at 2–4× crops:
  - paper-edge translucency
  - ink bleed
  - a camera push on the unfold, replaced by lifting the crab toward the lamp. Michael cut the lift too: the size change read as the character growing.
- **The head turning back to the lamp** read as a mistake, so she bows instead.
- **Readers** appear only inside the box: none in the room outside it.
- **A 0.1 s gap between two act 1 loops** played everything after it one drawing early against the song until it was found.
- **The prologue's far show was mirrored** because we see it from backstage. The director read the backwards subtitle as a bug. Fable let the mirror go: now the hall reads the lyric on the show and then finds the same card in her hands.
- **Two lines of drawing code sat inside comments, after a `//` on the same line.** B9's rim light never faded with distance from the lantern, and C2's lantern glow never drew. Both were found only when a crop at 3× showed a rim that was too even.
- **The finale's Fable** was first a rigid cut-out. She's now a mesh rig at Clawd's level:
  - Her near-black costume defeated the line-based layer split, which was fixed with per-pixel masks.
  - Halving Clawd's angles flipped Fable's forearms during windmills, so she holds her last clear pose and snaps on.

## To check it yourself
From the repo root (P = `projects/tsuzuku`):

```bash
node engine/render.mjs P --loop=bridge --sheet=21.6,22.2      # any moment of the bridge, from code
node engine/render.mjs P --loop=inkstand --strip=3.9:4.3      # every drawing of the ink stand-up
node engine/render.mjs P --loop=origami --strip=6.1:7.5       # the unfold, drawing by drawing
node engine/render.mjs P --loop=fablerom                      # the finale rig's range of motion
node engine/render.mjs P --loop=bridge --eval='WORDS.length'  # inspect the page's state
```

Change a number in `src/*.js` and the frame changes with it.
