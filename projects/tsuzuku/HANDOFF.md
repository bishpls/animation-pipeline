# Handoff: Fable's paper world ↔ Clawd's stage

Two sessions build this film: one builds Fable's paper world (prologue, verse 1, the exchange, the bridge, the outro) and
one builds Clawd's idol rig and stage. This file records where the two worlds meet, so the cuts line up. Times are song seconds.
The paper-world loops are all on the song clock (`LOOPS.<name>`, t = 0 at the time given).

## What exists (paper world)
| Song time | Loop | Content |
|---|---|---|
| 0.0 – 9.0 | `prologue` (t = song) | HELLO, WORLD! from backstage; the kuroko; black on the first hyoshigi clack (8.41) |
| 9.0 – 12.7 | `inklamp` | ink cut-in: the match, the lamp |
| 12.7 – 24.0 | `telling` | the doors open; the crab, the mother, the ruler; the little one lights orange |
| 24.0 – 36.0 | `verse1` | the row walks into the light; the unfold into Clawd's paper puppet; "Show me how!" |
| 36.0 – 61.0 | `exchange` | the mother goes sideways; "Hm."; hiki-nuki; "Sorekara?!"; the card tears on "Says who?" |
| 131.29 – 156.2 | `bridge` | opens on the clack (a match cut from the hall: seated; the lamp on the floor beside her, image-left, behind her back; Michael moved it off her lap); the fan's gallery; the shore struck; the pull-back to the wood |
| 156.2 – 159.53 | `inkcloseup` | ink cut-in: the close-up |
| 159.53 – 161.0 | `bridgeB6` | the fan becomes the book |
| 161.0 – 166.0 | `inkstand` | ink cut-in: the standing up (geta clack 165.18) |
| 166.0 – 177.8 | `bridgeB8` | she takes up the lamp, walks it to Clawd's puppet, sets it at her feet, rests a hand on her head; "Sorekara?": off the window's right edge with the lamp (gone by 176.47); the window dark but Clawd's eye slits; from 176.82 in the room at her world-A place beside the butai, at her cushion: hood up, the lantern lit in her hand at her hip |

Full cuts with audio: `out/act1_v1.mp4` (0–61), `out/bridge_full_v5.mp4` (131–176.5).

## The seams
1. **X8 → K1 (≈ 60.1 – 61.0).** On "Says" (60.08) the book's card (pulled most of the way out since "Every time.") tears in
   what's left of it in the window, right beside Clawd's paper puppet (theatre x ≈ 1540);
   the halves part over 10 drawings and stage light (white core, pink `rgba(255,120,190)` and cyan `rgba(90,220,255)` fringes)
   floods through, washing the paper world white by ≈ 60.9. Fable (seated, left) and Clawd's paper puppet stay silhouettes.
   BEATS K1 wants "through the torn paper, Clawd's stage powers up": the cleanest join is for K1 to open on the white and
   resolve into the stage, or for the rip to show the stage directly (the paper side can render the torn card as a mask over
   your frame if you want that: ask).
2. **B9 → F1 (176.47 – 177.8).** Fable walks off the window's right edge on "Sorekara?" (gone by 176.47), one beat of empty
   window, then at 176.82 two geta steps in from the right edge of frame (from x 2080) and she stands at her place in the room,
   world A's seat point (butai (3309, 2105)), planted by 177.46. At 177.8, CAM_WIDE, screen px: the standing puppet silhouette at
   s .2297 facing left, feet (1654, 1002), crown ≈ y 190; her fist at her hip ≈ (1589, 615) with a short stick, the lantern
   hanging from it, centre ≈ (1555, 675), sc 1.10, lit gold, indigo ribs. At her toes her cushion (the seated rig's zabuton,
   s .147, x 1504, spanning ≈ 1425–1675, top ≈ 983), bare (the one book is open on the rail). Hood
   up; black, rim-lit by the lantern; the room's air warm around her; the readers' row has a gap at x 1360–1880. The window is
   dark except Clawd's eye slits. F1 (the other session, Fable's ruling "no curtain: the push-in is the fold"): the window
   blazes, her silhouette becomes the illustrated rig in the same place, the readers leave with the flood; she sets the lantern
   on the cushion (178–179.2) and the camera pushes through the window.
   **The outro's room (202.59 on):** her cushion, empty, black, its edges catching only the window's spill and then the doors'
   leak (butai px: cushion (3008, 2104) s .294; `SEAT` in outro.js); the readers' gap as in B9. The freeze just before (other
   session) shows the lantern lit on it.
3. **Fable at the margin in Clawd's world** (K3 48.1, K5 52.2, K7 56.2 in bar numbers; H2, F2, F4, F6, F8): her riveted
   silhouette with two coloured shadows (pink and cyan) pressing margin notes. The paper side has her puppets (`FABLE`, seated;
   `FABLE_S`, standing, with `makeWalk` and `drawStanding`) and the letterpress (`press`, `inkVellum` in page.js). Happy to build
   that element as a function your shots call.

## Fable on Clawd's stage (src/margin.js; Fable's ruling, 2026-09-25)
Her margin silhouette is **in the picture, never on the paper, never fixed to the screen**: on Clawd's stage at the wing, feet
on her floor, lit by her lights (hence the pink and cyan shadows), so she obeys the stage camera. She is there in wide and medium
shots and leaves the frame in push-ins and close-ups; to have her felt, frame a sleeve or her edge at the frame's edge. The margin
notes press into the washi border whether she is in frame or not. Her wipe (91.76) lands in a shot that includes her wing.

## The lantern chain (Fable's ruling, 2026-09-25; one object everywhere: her oblong chōchin, gold paper, indigo ribs and caps)
C2 lights it and ends with her raising it out of the top of frame -> C3: its glow rises behind the vellum and settles (act 1's
light is the hung lantern) -> the flood at 60-61 covers her taking it -> world A: lit on the floor at her left in every room shot
-> 131.29: black but that lantern at the room end camera's (1376, 903), 156 px, which glides to the bridge's floor spot beside
her (B1 fades in around it) -> B8: taken up, set at Clawd's feet, carried out of the window -> 176.82: lit in her hand in the room
-> F1: set on her cushion (178–179.2), where it stays, lit, through the final chorus ("what steps in has empty hands"); at the
outro's clack it is inside the window again, on the rail (a kuroko's cut); the cushion is empty (Fable: "the empty cushion is the
audience's arithmetic"). One book, too: the open one she left face-up on the rail in B8 ("it's the readers' now"); the cushion
carries the lantern during F and nothing else. When it stands on its own in the paper world it has a puppeteer's rod; never in the room.

## Sound
The paper world's sound effects are a stem under the song (song.mp3 untouched): each picture module registers its cues with
`PAPER_SFX.push(() => [[song s, name, gain dB], ...])` (src/paper.js; names from sound/lib/), `sound/mix.py` dumps them via
`paperSfx()`, builds `assets/sfx_paper.wav` (levels relative to the song around each cue, no ducking) and `out/paper_mix.wav`.
Clawd's world can register into the same list (its own names, added to sound/sfx_lib.py) and get one stem for the film.

## Sharing the tree
Both sessions work in one checkout. **Stage files by name** (never `git add <dir>` or `-A`): each side has swept the other's
work-in-progress into a commit once (my `src/prologue`-era commit took `rom.js`; d9cadcd took `outro.js`). Paper-world files:
`src/{paper,page,puppet-based *.js: fable*, clawdpaper, origami, verse, exchange, bridge, prologue, outro, ink, stage, scenery,
audience, mother}`, `rig/{fable,fable_ink,kuroko,clawd_paper,audience,butai,scenery}`, `engine/{puppet,warp}.js`.

## Cameras (src/stage.js, butai px)
CAM_WIDE { x 1920, y 1180, zoom .5 } (the whole butai); CAM_WINDOW { x 1920, y 1445, zoom .8 } (Michael + Fable, 2026-09-25: the
window, the lyric strip pinned on the rail under it, and the readers' heads). The readers are placed from the camera by
`readers(ts, cam)` (src/audience.js).

## Conventions the paper world uses
- Everything on twos (12 fps drawings) from one clock; the lamp at theatre (1180, 560); the window shows theatre y 170–1070.
- Colour enters Fable's world only as light through cellophane (Clawd's gel `rgba(236,110,52,.9)`); Fable's ribbon `FABLE_GEL`.
