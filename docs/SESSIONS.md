# Sessions: building one film with several agents

TSUZUKU was built by two long-running sessions in one checkout (Fable's paper world and Clawd's stage), with section agents, forks
and character reviewers around them; HELLO, WORLD! by one lead with a section agent per file. These are the conventions that held.
The lessons behind them are in `docs/CRAFT.md` §11 ("Parallel agents"), §13 ("Working alongside another session") and §14.

## Ownership
- **One owner per file.** Pre-create the stub files and their `<script>` tags so nobody edits `index.html` mid-flight; each session
  keeps its own script block in it.
- **Shared engine and tools:** report bugs to the lead rather than fixing them in place; the lead batches the fixes. Never rewrite a
  shared file wholesale: re-read it and make surgical edits.
- **Stage by explicit path, never a directory** (`git add src/verse.js`, not `git add src/` or `-A`): each TSUZUKU session once swept
  the other's work in progress into its own commit.
- **Separate output paths** per session and reviewer (`--out=P/board/<session>/...`); the shared default `board/sheet.jpg` gets
  overwritten.
- **Budget the machine:** `--workers` 4 or fewer when another session renders; eight parallel full-song mixes stalled everything.

## The clock and the seams
- One cue sheet (`assets/cues.json`) for everyone. Each section is its own loop; a film-level loop dispatches them on the song clock
  and hands each either local seconds or song seconds (`projects/tsuzuku/src/film.js`: `[loop, start, end, clock]`).
- **Keep a HANDOFF.md** (`projects/tsuzuku/HANDOFF.md` is the model): what exists (a table of song times and loops), each seam with
  its times and screen coordinates, the cameras, shared rulings with dates, and the chains of recurring props (where the lantern is
  at every cut).
- **Match on measured numbers:** at a cut, publish the exact screen coordinates of what matches; the other side confirms by measuring
  its own frame at that time, and both re-publish after any restaging.
- **Announce shared-asset changes with their exact extent** (the master changed only between 203.93 and 205.03 s, verified sample
  by sample), and prove a rebuild is bit-identical before swapping anything into it.

## Interfaces between sessions
- Deliver a cross-session piece as a **function with a stable signature and a demo loop**, and write the contract down: units
  (world or screen px), the clock (song or local seconds), who draws what order, and the size contract (TSUZUKU's
  `FABLESTAGE.stage(X, tt, FW, P)`: `FW.h` is her standing height in world px; `projects/tsuzuku/RIGGING.md` §1).
- **Registries instead of shared edits:** each module pushes its own entries (TSUZUKU's `PAPER_SFX.push(() => [[t, name, dB], ...])`),
  and one tool reads them all (`tools/sfxmix.py --eval='JSON.stringify(paperSfx())'`).
- Every loop renders correctly cold, at any t: never depend on another loop's lazily built state.

## Subagents
- **Forks** get one-line tasks with explicit scope, their own branch or output paths, and report once. They don't re-delegate.
- **Section agents** get a brief: the shots, the key sung times, the seams, the quality bar, and review their own sheets and strips
  at least three times before reporting.
- **A character's reviewer is persistent** (one per character, the same agent all film) and gets the design docs and the rulings so
  far. Relay rulings between reviewers verbatim; put conflicts to the user and record them with a date.
- When the user changes a shared asset mid-flight, message every running agent.
