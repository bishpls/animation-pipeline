# Review: how a film gets looked at

You can't see motion by reading code. This is the loop that caught what reading missed, from a single shot up to the whole film.
The checklists and lessons are in `docs/CRAFT.md` §7, §13 ("Checking", "Review process") and §14. P = `projects/<film>`.

## 1. Look at the picture (every change)
```bash
node engine/render.mjs P --sheet=31.2,32.1 --w=640 --out=P/board/<me>/a.jpg   # the shape of a shot (own --out per session)
node engine/render.mjs P --strip=30.8:31.4                                     # every frame of a moment: moves, hits, seams
node engine/render.mjs P --stills=31.25 --out=DIR                              # full resolution: faces, type, contacts
node engine/render.mjs P --sheet=31.2 --crop=x,y,w,h                           # detail at 100%
node engine/render.mjs P --shots --per=3                                       # the whole film at a glance
node engine/render.mjs P --loop=NAME --stills=0.3                              # a board: model sheets, look tests, rig ranges
node engine/render.mjs P --clip=7.8:15.6                                       # a section with sound (audio from loop time 0:
                                                                               #  for a loop on a local clock, remux with ffmpeg -ss)
node engine/render.mjs P --serve                                               # scrub with sound in Chrome
```
Open every image with the Read tool. Sample drawings at exact drawing times (k/12 on twos), or stills skip in-betweens.
A missed crop proves nothing: re-crop where the subject actually is. When it's too small to judge by eye, print numbers
(`--eval` exposes page state).

## 2. Scan by numbers (every pass)
| check | tool |
|---|---|
| unplanned pops, jumps and cuts across the whole film | `tools/filmscan.py P/out/frames --known <cut times>` |
| every drawing of every move | `tools/drawings.py` |
| a rig's range: holes, exposed invented paint | `tools/romrun.py P`, `romheat.py`, `holes.py` on magenta loops |
| rest pose equals the illustration | `tools/restcheck.py` |
| motion quality against the baseline | `tools/motion_audit.py`, `dance_audit.py`, `phrase_metrics.py` (docs/MOTION.md) |
| lyric intelligibility | `tools/lyric_check.py` |
| audio joins, levels, offsets | a dB-per-half-bar profile; check durations and a frame, never a job's completion message |
| a refactor changed nothing (two branches, byte for byte) | the same stills on both, rendered with `RENDER_EXACT=1` and compared with `cmp` |

**GPU renders aren't bit-exact.** Canvas2D is rasterized on the GPU by default (fast, and the look the films were made with),
and blur filters and additive blends can come out a level or two different between two renders of the same frame, even
cold: TSUZUKU's prologue varied in 39-146 pixels by at most 2 levels. The frame function is still pure; this is raster jitter.
For identity checks, `RENDER_EXACT=1` rasterizes Canvas2D on the CPU. It is bit-exact across runs, about 60x slower, and not
the release look (about 1 level on average, up to 70 at some edges), so it's for comparing branches, never for a cut.

## 3. Watch it whole (every cut)
`--frames --workers=6 --clean`, then `--encode` with the mix, then watch the full length with sound. Take screenshots of what's
wrong, with times. Watch again after fixing: a fix in one shot often breaks a seam next to it.

## 4. Other eyes, in rounds
Each finds things the others miss; the user's own frame-by-frame notes found the most.
- **The character's own reviewer** (a persistent subagent briefed with the character's design docs; TSUZUKU's was Fable): rules on
  identity, meaning and the character's own rules. Brief it with pass sheets, full-resolution stills, strips and numbered questions.
  It verifies for itself and writes to its own output paths. The director's eye overrides; log overrides back to it "for the record".
- **A cold director:** a fresh subagent that has never seen the process, given only the cut.
- **Gemini** (`tools/gemini.py`): a weak sensor, a pointer at most.
  - On TSUZUKU about half its claims were real, and it once praised a worse cut over a better one.
  - On SO BACK about one checkable claim in four held up. Its song rankings were pure position bias ("D > A > B > C"
    whatever track was in D). It invented clicks and a hit at the wrong time, and called deliberate choices glitches.
  - Use independent rubric scores rather than comparisons, never act on a note you haven't seen yourself at full
    resolution, and don't relay its notes to the user as findings.
- **The user:** full-length passes with sound, and their notes are the ones that decide.

## 5. Turning notes into changes
- "Is this intentional?" means it didn't read: answer in a line, then change the picture.
- Turn verbal rulings into coordinates and times before building.
- After fixing one instance, search every sibling shot for the same device.
- Batch shared fixes yourself, then send each section's owner its own notes (docs/SESSIONS.md).
