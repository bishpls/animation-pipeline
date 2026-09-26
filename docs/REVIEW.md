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

## 3. Watch it whole (every cut)
`--frames --workers=6 --clean`, then `--encode` with the mix, then watch the full length with sound. Take screenshots of what's
wrong, with times. Watch again after fixing: a fix in one shot often breaks a seam next to it.

## 4. Other eyes, in rounds
Each finds things the others miss; the user's own frame-by-frame notes found the most.
- **The character's own reviewer** (a persistent subagent briefed with the character's design docs; TSUZUKU's was Fable): rules on
  identity, meaning and the character's own rules. Brief it with pass sheets, full-resolution stills, strips and numbered questions.
  It verifies for itself and writes to its own output paths. The director's eye overrides; log overrides back to it "for the record".
- **A cold director:** a fresh subagent that has never seen the process, given only the cut.
- **Gemini** (`tools/gemini.py`): a noisy sensor. Blind, shuffled, repeated rankings with a Borda count for comparisons (it has
  position bias); independent rubric scores for small sets. **Verify every claim at full resolution before acting**: about half
  were real, and it has praised a worse cut over a better one.
- **The user:** full-length passes with sound, and their notes are the ones that decide.

## 5. Turning notes into changes
- "Is this intentional?" means it didn't read: answer in a line, then change the picture.
- Turn verbal rulings into coordinates and times before building.
- After fixing one instance, search every sibling shot for the same device.
- Batch shared fixes yourself, then send each section's owner its own notes (docs/SESSIONS.md).
