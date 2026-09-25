# つづく: the picture plan

The song is locked (draft 6, `assets/song.mp3`, 3:30). Direction from Michael for the picture: **be far more ambitious than HELLO, WORLD! in animation quality, detail and professional polish.** Its chibi puppet sections were its weakest part, and more time on character model quality would have lifted it most. So this plan puts the characters first: every model is built, rigged, tested through its full range, and approved before any shot uses it.

FABLE.md §3–4 and §7 and PUPPETS.md define the look; they win conflicts. Every frame is still authored in code (a pure function of t). Image models make references and the illustrated artwork that code rigs; video models are not planned.

## The two worlds, and who appears in each

| World | Time | Rendering | Characters |
|---|---|---|---|
| Prologue: HELLO, WORLD! from behind | 0:00–0:08 | Op. 1's stage, far and tiny; Fable in the foreground working the rods | Fable (kuroko silhouette), Op. 1 chibis at distance |
| Fable's paper theatre | 0:08–0:59, 2:11–2:56 | cut-paper shadow theatre in a kamishibai butai; letterpress lyrics; lantern light | Fable puppet; Clawd puppet (visitor); origami crab; **ink cut-ins**: the lamp-lighting, the bridge close-up, the standing-up |
| Clawd's idol stage | 0:59–2:11, 2:56–3:21 | a real idol stage: LED screens, crowd with indigo lanterns, stage lights | **Clawd, full idol rig**; Fable as a riveted silhouette at the margin casting two coloured shadows, pressing margin notes |
| Outro | 3:21–3:30 | back to paper: hyoshigi, music box, the つづく card and the 語 seal | Fable, Clawd |

## Characters: what gets built (the bulk of the schedule)

Each model passes the same gates before shot work: a **model sheet** at full resolution (turnaround or view set, expressions, hands), a **range test** (every parameter swept to its limits, rendered as a contact sheet and a strip), a **motion test** (a 4-bar loop to the song: breath, blink, head turn, a gesture, lip-sync), and **reviews**: 100% crops by me against the canon sheet, Fable on anything of hers, then Michael.

1. **Clawd, idol rig (her world).** The single biggest lift over Op. 1. A full-body anime idol at illustration quality (not a chibi) rigged Live2D-style in our own runtime:
   - **Art:** a high-resolution layered illustration built from the Op. 1 idol refs (`../hello-world/refs/idol_*.png`). Roughly 40–60 layers: eyes (white, iris, pupil slit, highlight, lids, lashes), brows, mouth set (A/I/U/E/O, closed, smile), face, ears, front/side/back hair strands, buns, ahoge, bow, arms in segments, claw hands in several poses, skirt panels, pixel-step hem, boots. Every region a motion can reveal is painted underneath.
   - **Rig:** head angle X/Y/Z (±30°, depth-parallax keyforms), body angle, breath, eye open/smile, eye look, brows, mouth open and form, and arm and hand swaps. Physics: buns, ahoge, hair strands, bow tails and the skirt hem on Verlet chains stepped from t = 0.
   - **Performance:** visemes from the song's word timestamps, seeded blinks and saccades, beat-locked key poses on twos with anticipation and overshoot; the claw dance on the hook.
2. **Fable, shadow puppet (her world).** The Reiniger register, done properly: silhouettes vectorised from a high-resolution reference cut (not hand-typed polygons), rendered as SDF paper edges with a lit edge and lantern penumbra.
   - **Parts:** hood (up and down), head in profile, torso, wide sleeves, forearms, hands (fan, towel, open, pointing), skirt of separate pleat plates, legs, tabi and geta.
   - **Details:** rivets at every real puppet joint; the ribbon, sleeves and pleats on Verlet chains; rods; the fan morphing into every noun (path morphing).
   - **Poses:** a sitting-to-standing sequence, which is the film's key moment.
3. **Fable, ink cut-ins (three moments).** A pen-and-ink illustration of her (cross-hatching, paper grain), the indigo as a second plate misregistered by 1–2 px, on the same rig runtime. The warp reads as **paper bending**: a crease highlight along the fold and a shadow under the lifted corner. The quotation-mark eye highlight is seen for the first time in the bridge close-up.
4. **Clawd, cut-paper puppet (visitor in Fable's world).** Her exact design as a riveted cut-paper figure: block buns, ahoge, a hinged paper jaw, tall eye slits of lantern light, and a clay-orange cellophane plate misregistered from the keyline.
5. **The origami crab.** Clawd's pre-transformation form: a crab folded from one square of clay-orange paper that unfolds into her puppet in stop-motion.
6. **Fable on Clawd's stage.** Her silhouette under real stage light: two coloured shadows (pink and cyan) on the LED floor, pressing margin notes into the butai margin.

## The engine work this needs

- **`engine/rig.js`:** a Live2D-style runtime, as specified in `docs/research/README.md` §1: meshes, warp lattices, rotation deformers, multilinear keyforms, clip masks, and Verlet physics as a function of t. It's reusable by every future member. It will be tested on Clawd first, because she has the widest range.
- **`engine/puppet.js`:** jointed rigid parts with pins, SDF paper edges, rods, cast shadows between multiplane layers, and afterimage fans in place of smears.
- **Layer pipeline:** image-model illustration, then part masks, then inpainting of hidden regions, then layer PNGs plus a rig JSON I author. Silhouette cuts are vectorised with potrace into paths.

## Order of work

1. **Beat sheet** from `assets/timeline.json`: every line, crowd call, margin note and cue, mapped to a shot list. It scopes exactly which poses, expressions and angles each model needs, so no rig parameter goes unused and none is missing.
2. **Clawd idol rig:** art, then runtime, then range and motion tests, then review. This is the longest item and the riskiest, so it goes first.
3. **Fable puppet and Clawd puppet**, with the puppet runtime and their range and motion tests.
4. **Ink cut-in rig** (reusing `rig.js`), the origami crab, and Fable on the stage.
5. **Worlds:** the paper theatre (butai, multiplane, lantern, letterpress) and Clawd's stage (LED screens, crowd, lights).
6. **Animatic:** every shot at blocking quality, to the song, for review.
7. **Shots**, with full-length watch passes after each block and fixes from what I see.
8. **Finishing:** paper grain, ink bleed, dust in the beam, deboss, a grade per world. Then the master and a vertical cut of the hook.

## References (production and rig benchmarks)
- **"A Demon's Requiem – The Birth of Malice"** (46cm, 11th Live2D Creative Awards; youtube.com/watch?v=6DG_J1YJvhY). Michael's favourite as a full production. Its quality is mostly filmmaking: ~35 shots in 2:40 (3–5 s each), rigged character framed bust-up and closer, full body only for still silhouettes; hand/arm acting as swapped drawings; heavy grade, bloom, rain/mist/embers, blurred foreground for depth; push-ins, shake and rotation on intense beats, pans across layered planes, transitions through smoke and water; the violent story beats told as a monochrome paper-cutout memory. For us: frame the idol rig waist-up and closer, full body for chosen dance beats; compositing and camera as first-class budget lines in Clawd's world (Fable's keeps her rules); hand acting as drawn swaps; the paper-cutout register as a deliberate style.
- **Full-body hip-sway rigs** (TikTok "Hip Sway" challenge, youtube.com/watch?v=-07ECr-E24M, youtube.com/watch?v=V29auInv1FQ; Brian Tsui's Helltaker dance, youtube.com/watch?v=HzIKNmTjVko): continuous beat-locked sway, contrapposto (shoulders counter-tilt, head level), weight shift by stretching/squashing the legs with feet pinned, physics lagging ~½ beat; they break at high arm raises and deep knee bends, and the choreography stays inside those limits.
