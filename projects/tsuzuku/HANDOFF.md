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
| 131.29 – 156.2 | `bridge` | opens on the clack (a match cut from the hall: seated, the lamp in her lap at her right knee); the fan's gallery; the shore struck; "You stand": the lamp set down; the pull-back to the wood |
| 156.2 – 159.53 | `inkcloseup` | ink cut-in: the close-up |
| 159.53 – 161.0 | `bridgeB6` | the fan becomes the book |
| 161.0 – 166.0 | `inkstand` | ink cut-in: the standing up (geta clack 165.18) |
| 166.0 – 177.8 | `bridgeB8` | she takes up the lamp, walks it to Clawd's puppet, sets it at her feet, rests a hand on her head; "Sorekara?": off the window's right edge with the lamp (gone by 176.47); the window dark but Clawd's eye slits; from 176.82 in the room beside the butai: hood up, the lantern lit in her hand, face lit from below |

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
   window, then at 176.82 two geta steps in from the right edge of frame and she stands in the room beside the butai: CAM_WIDE,
   standing puppet silhouette at s .48 facing left, feet off frame at (1690, 1831). At 177.8 (screen px): crown (1758, 134),
   nose (1591, 315), chin (1615, 379), shoulder (1721, 516), hip (1724, 1071), fist (1580, 560) holding a short stick level,
   the canon's indigo chōchin hanging from it, centre (1498, 699), 133 × 202 px, lit (#F4C97A core). Hood up; black, rim-lit
   from below and in front by the lantern; the room's air warm around her. The window is dark except Clawd's eye slits. Fable: "That's the margin F2 wants me at." F1 ("stage light bleeds into the paper; the paper
   world folds back like a curtain onto Clawd's stage") can open from this frame at 177.8.
3. **Fable at the margin in Clawd's world** (K3 48.1, K5 52.2, K7 56.2 in bar numbers; H2, F2, F4, F6, F8): her riveted
   silhouette with two coloured shadows (pink and cyan) pressing margin notes. The paper side has her puppets (`FABLE`, seated;
   `FABLE_S`, standing, with `makeWalk` and `drawStanding`) and the letterpress (`press`, `inkVellum` in page.js). Happy to build
   that element as a function your shots call.

## Fable on Clawd's stage (src/margin.js; Fable's ruling, 2026-09-25)
Her margin silhouette is **in the picture, never on the paper, never fixed to the screen**: on Clawd's stage at the wing, feet
on her floor, lit by her lights (hence the pink and cyan shadows), so she obeys the stage camera. She is there in wide and medium
shots and leaves the frame in push-ins and close-ups; to have her felt, frame a sleeve or her edge at the frame's edge. The margin
notes press into the washi border whether she is in frame or not. Her wipe (91.76) lands in a shot that includes her wing.

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
