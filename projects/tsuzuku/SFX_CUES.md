# つづく: picture-driven sound cues (for the final mix; the song is locked, these sit quietly on top)

From Fable's reviews. Times are song seconds; "on the lute triplet" = snapped to the nearest 6/8 eighth (85 BPM).

| Where | Cue | Notes |
|---|---|---|
| C2, ~10.25 | a match strikes | then the flame's small hiss under "Mukashi"; nothing on the lantern bloom (the crowd call is the sound) |
| Verse 1, the crab | dry paper scuttles | tiny, on the lute triplets while it side-steps |
| The unfold, 30.4-31.2 | dry paper, one per fold (crab -> base -> square) | on the lute's triplet; SILENCE on the held square; ONE snip on the cut; ONE "tk" as every rivet punches at once |
| Fan morphs | a soft paper fold per morph | the fan opening: one flick |
| B7, ~164.5 | the geta: one clack as she stands | "Sound: the geta only" (Fable) |
| Margin notes | soft type thuds | already in the song mix (press.mp3) |

## Built (2026-09-25): the paper world's sound stem
- **Library:** `sound/lib/` (ElevenLabs sound effects via `sound/sfx_lib.py`, logged): match, paper fold, fan flick and snap,
  paper tap, card slide, the tear, snip, rivet, geta, butai doors open and shut, the seal stamp, the lantern's handle, the lantern
  set down, the card in the rack, the LED card going dark, cloth, the puppet hop.
- **Cues:** registered by each picture module (`PAPER_SFX` in paper.js, one clock with the picture); dumped to `sound/cues.json`
  by `sound/mix.py`, 101 events: prologue (the card racked, its lamps out, the kneel), C2 (the match; the lantern's handle as she
  raises it), the doors, the fan and each noun, the crab's hops and scuttles, the mother's stiff steps (straight: fading toward
  the lamp; sideways: scuttling off, quiet before "Hm."), the row stepping into the light, the unfold (two folds, silence on the
  square, one snip, one tk), the hiki-nuki, Clawd's hops, the tear, Clawd set down, the gallery and its put-back, each plane
  struck, B6's fan-to-book, B7's geta (the loudest thing: "the geta only"), B8's lantern and geta, the room's clack-clack, the
  outro's card, the seal drawn from her collar (cloth), steps, the seal and Clawd's peek, the doors closing.
- **Levels:** each cue's peak is set relative to the song's own level around it; no ducking. The stem is `assets/sfx_paper.wav`
  (not committed; rebuild with `sound/mix.py`); the paper-world cuts carry `out/paper_mix.wav` (song + stem). `song.mp3` is untouched.
