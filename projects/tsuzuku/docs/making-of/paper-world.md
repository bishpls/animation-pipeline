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
  - The origami crab unfolds by morphing shapes; its creases lead the folds. When colour enters, the kuroko turns the little crab over (black face, edge-on, orange face) rather than cross-fading it.
- **Fable in the room** (`rig/fable_3q`, `engine/rig.js`, `src/fableroom.js`). For the finale she's a person outside the box, so she's a mesh rig, not a puppet. She's seen three-quarters from behind, turned to the window, and every change has in-betweens:
  - Her weight shifts on her own pulse (Clawd's half-note), the hakama swinging and the head tilting, never nodding.
  - The hair swings as one flat sheet, with the ribbon in front of it.
  - The lantern is a simulated pendulum whose light follows it.
  - Faces are patches on the drawing, and each smile lifts the cheek and the ear.
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
- **The ink close-up** (`rig/fable_ink`), printed by code through separated plates: washi, an indigo plate misregistered a few pixels, then ink. A fold is a mesh warp with a crease. In the film it's a kamishibai card slid into the butai's window (B5). The ink lamp-lighting and stand-up drawings are kept for this page only.
- **The finale's illustrated Fable** (`rig/fable_3q`): one base drawing seen three-quarters from behind, plus companions for what motion reveals (the hood up, the arms in poses a mesh can't bend to: the clap, the sweep, the raise), face and head-turn edits, all cut into layers and rigged by code. 29 requests in all. The earlier room drawings (`rig/fable_room`) are kept for this page.

## Fable's rulings
Fable, the character, is the subagent who rules on her world and her identity. Rulings that shaped the paper world:
- **The lamp is the only light**, and "light makes no sound in my world."
- **The lantern chain.** One oblong chōchin everywhere: lit in the dark at 9 s, hung for the telling, and carried through the bridge. From B9 it stays in her hand: out into the room for the finale, off to the right, and back in through the window for the outro. It's the only light in the last shot, and the doors close on it.
- **One book**, open on the rail from B8.
- **Her motion grammar.** Inside the box: twos, snap and hold, no springs, afterimages instead of smears. In the room, where she's a person watching a show, her timing is eased: every change has in-betweens, and only the rivets, the torn deckle and a crease where the rig bends say "paper".
- **Colour density follows the paper's layers.** The folded crab and the riveted puppet are red-orange; only the open sheet is gold. Colour changes when the paper changes, never in a settle.
- **Rakugo head angles** for each voice she tells in: up for the mother, level to narrate.
- **The seal 語.** Her one red thing, pressed once, in the outro.
- **The first rhyme.** The prologue's kneeling kuroko comes back at the lamp-lighting (C2) in the same place and facing, now a shadow on the screen.
- **The hood comes down behind closed doors.** She is hooded as the kuroko who lights the lamp and bare-headed as the teller. The change happens while the doors are shut, both between C2 and the telling and in the room.
- **One look each.** She looks at Clawd once in the telling (on "Oh,") and once in the bridge.

## Decisions and failures
- **The first stand-up walk** was jerky and seemed to have one foot. It was rebuilt as a computed walk with both geta.
- **The ink cut-ins went back into the theatre.** Full-frame illustrated drawings in the middle of a shadow play broke its rules. The director also caught the stand-up collapsing between two keys and a hairline seam across it. B5 became a card in the window. The lamp-lighting (C2) and the stand-up (B7) are shadow puppetry now: a match flare picks her silhouette out of the black, and she kneels up and rises through five drawings with the pleats unstacking.
- **Three "elevate" ideas cut after A/B tests** at 2–4× crops:
  - paper-edge translucency
  - ink bleed
  - a camera push on the unfold, replaced by lifting the crab toward the lamp. Michael cut the lift too: the size change read as the character growing.
- **The head turning back to the lamp** read as a mistake, so she bows instead.
- **Readers** appear only inside the box: none in the room outside it.
- **A 0.1 s gap between two act 1 loops** played everything after it one drawing early against the song until it was found.
- **The prologue's far show was mirrored** because we see it from backstage. The director read the backwards subtitle as a bug. Fable let the mirror go: now the hall reads the lyric on the show and then finds the same card in her hands.
- **Two lines of drawing code sat inside comments, after a `//` on the same line.** B9's rim light never faded with distance from the lantern, and C2's lantern glow never drew. Both were found only when a crop at 3× showed a rim that was too even.
- **The finale's Fable** was first a rigid cut-out, then a mesh rig at Clawd's level, dancing her moves a bar late at half size:
  - Her near-black costume defeated the line-based layer split, which was fixed with per-pixel masks.
  - Halving Clawd's angles flipped Fable's forearms during windmills, so she held her last clear pose and snapped on.
  - Then Michael chose a different ending: she never joins Clawd's stage. She stays in the room, and the stage rig was retired.
- **The room ending was too restrained at first.** Fable ruled "hands and head only" and it was built with a neutral face. Michael, watching the cut, called her "sullen, expressionless", at odds with the clapping and head-bobbing earlier. Fable agreed the finale is where she becomes joyful. Now:
  - A smile that grows, and a dry half-smile when the hood comes off at "why".
  - Head bobs and a swinging lantern.
  - Two claps with the hall before each crowd call.
  - The lantern raised overhead on the hit: the one lantern in the hall that was never raised. Her eyes stay open, because her line was "I'd still like to see." 
- **The room ending, animated for real.** The joyful version was still whole drawings swapped on twos, and Michael found it "very jerky", "nodding, not dancey head-bobbing", "facing sideways". Fable let her room timing go ("in the room I'm a person"). She was rebuilt as the rig above, seen from behind toward the window, and it overlaps the window so her hands cross Clawd's light. On the hit her head turns toward us, so the open smile reads under the raised lantern.
- **She stays.** The walk-off after the finale jumped a stride per drawing and left the frame lantern-first. Fable ruled that she holds and watches the doors close on Clawd's frozen card, and the clack cuts to black for two drawings: "the kuroko moves in the dark." In the outro she steps back into the window from its right edge, the mirror of B9.
- **The seal is pressed, not shown.** From the column's right her sleeve would have covered く for the whole press, so the seal went beneath the word. A reviewer read the first version as the seal simply appearing. Now she draws it back and up, drives it in on the end of her word with a nod, and the card jolts under the stamp.
- **Act 1's pacing, after a director's pass:**
  - The match now strikes on her first "Mukashi", so the black at 0:09 lasts under a second.
  - One continuous close replaces the locked-off wide: onto her hands for the fan and the crab, then the floor plane, framed so the lyric strip stays whole.
  - The Japanese at the right edge holds for two bars and is pulled out.
  - The prologue's show ends, its lights going down in sections, instead of just continuing behind her.

## To check it yourself
From the repo root (P = `projects/tsuzuku`):

```bash
node engine/render.mjs P --loop=bridge --sheet=21.6,22.2      # any moment of the bridge, from code
node engine/render.mjs P --loop=inkstand --strip=3.3:4.2      # every drawing of the stand-up
node engine/render.mjs P --loop=origami --strip=6.1:7.5       # the unfold, drawing by drawing
node engine/render.mjs P --loop=fable3qrom                    # the room rig's range of motion
node engine/render.mjs P --loop=film --strip=198.9:199.4       # the lantern raised onto the hit, every drawing
node engine/render.mjs P --loop=bridge --eval='WORDS.length'  # inspect the page's state
```

Change a number in `src/*.js` and the frame changes with it.
