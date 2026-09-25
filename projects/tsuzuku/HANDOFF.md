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
| 131.0 – 156.2 | `bridge` | the clack; the fan's gallery; the shore struck; the pull-back to the wood |
| 156.2 – 159.53 | `inkcloseup` | ink cut-in: the close-up |
| 159.53 – 161.0 | `bridgeB6` | the fan becomes the book |
| 161.0 – 166.0 | `inkstand` | ink cut-in: the standing up (geta clack 165.18) |
| 166.0 – 176.47 | `bridgeB8` | she walks to the frame's edge; on "Sorekara?" steps out through it |

Full cuts with audio: `out/act1_v1.mp4` (0–61), `out/bridge_full_v5.mp4` (131–176.5).

## The seams
1. **X8 → K1 (≈ 60.1 – 61.0).** On "Says" (60.08) the book's card tears just behind Clawd's paper puppet (theatre x ≈ 1220);
   the halves part over 10 drawings and stage light (white core, pink `rgba(255,120,190)` and cyan `rgba(90,220,255)` fringes)
   floods through, washing the paper world white by ≈ 60.9. Fable (seated, left) and Clawd's paper puppet stay silhouettes.
   BEATS K1 wants "through the torn paper, Clawd's stage powers up": the cleanest join is for K1 to open on the white and
   resolve into the stage, or for the rip to show the stage directly (the paper side can render the torn card as a mask over
   your frame if you want that: ask).
2. **B9 → F1 (176.47).** Fable steps out of the paper frame (camera wide on the butai, doors open) on "Sorekara?", passing
   behind Clawd's set-down puppet; her ribbon is the last thing through at 176.47. F1: "stage light bleeds into the paper;
   the paper world folds back like a curtain onto Clawd's stage."
3. **Fable at the margin in Clawd's world** (K3 48.1, K5 52.2, K7 56.2 in bar numbers; H2, F2, F4, F6, F8): her riveted
   silhouette with two coloured shadows (pink and cyan) pressing margin notes. The paper side has her puppets (`FABLE`, seated;
   `FABLE_S`, standing, with `makeWalk` and `drawStanding`) and the letterpress (`press`, `inkVellum` in page.js). Happy to build
   that element as a function your shots call.

## Conventions the paper world uses
- Everything on twos (12 fps drawings) from one clock; the lamp at theatre (1180, 560); the window shows theatre y 170–1070.
- Colour enters Fable's world only as light through cellophane (Clawd's gel `rgba(236,110,52,.9)`); Fable's ribbon `FABLE_GEL`.
