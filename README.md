# SO BACK

A 29-second vertical hyperpop hard edit made entirely from **Super Smash Bros. Melee**. The picture is the game, rendered
in-engine: the doldecomp decompilation, rebuilt with a director compiled into it, captured frame by frame in Dolphin. Every
sung and spoken word is the Melee announcer, cut and retuned from his own recorded clips. Every word on screen is the
game's own lettering. The one generated element is the instrumental.

**"It's so over"**: Captain Falcon's sacred combo freezes mid-Falcon-Punch. **"We're so back"**: the punch lands on the
drop. **"This game's winner is... YOU!"**

- **The making-of:** [projects/so-back/MAKING-OF.md](projects/so-back/MAKING-OF.md). It covers the game-engine work, the
  frame lab, the announcer splicing, the type extraction and the edit.
- **The storyboard and the clock:** [projects/so-back/STORYBOARD.md](projects/so-back/STORYBOARD.md).
- **The video:** see this branch's GitHub release.

*Unofficial, non-commercial fan work.* This branch holds code, choreography and documentation, never game data. The disc,
builds, captures, the decoded announcer audio and the extracted type all live outside the repo. Reproducing the film needs
a Melee disc you own (NTSC 1.02, `GALE01` rev 2).

## What's here

This is a one-film slice of [animation-pipeline](https://github.com/bishpls/animation-pipeline):

| path | what |
|---|---|
| `projects/so-back/` | the film |
| `engine/` | the parts of the animation engine it uses: time, the plain Canvas2D studio, image-sequence plates, type, the headless renderer |
| `tools/` | the song and review tools it uses: `music.py`, `audio_analyze.py`, `songmap.py`, `gemini.py` |

Inside `projects/so-back/`:

| path | what |
|---|---|
| `machinima/` | the director kit: C compiled into Melee, the choreography language, build and capture tools; `CHANGES.md` logs what this film added |
| `director/` | the choreography and the labs: the sacred combo, the KOs, the drop montage, the roster, the ending |
| `vocals/` | the announcer vocal kit: the bank decoder, the inventory, the splices, `vox.py`, the arrangement |
| `type/`, `src/meleetype.js` | Melee's own text, extracted from the disc and drawn by the engine |
| `song/` | the composition plans, take screening and `assemble.py` (seating a take on the locked grid) |
| `src/` | the edit: time-remapped plates, keyed composites, the hard-edit effects, captions, one file per section |
| `prep_plates.py`, `sfx.py`, `mix.py` | capture → plates, the game-sound stem, the mix with its tape stop |

## Requirements

- Node 18+ (`npm install`) and Google Chrome or Chromium (`CHROME_PATH`) for the renderer.
- Python 3 with numpy, scipy, soundfile, librosa, pillow, opencv-python, requests and praat-parselmouth. Add openai-whisper
  and torch for the vocal judges. ffmpeg on `PATH`.
- For captures: Dolphin and a doldecomp/melee checkout (see `projects/so-back/machinima/README.md`).
- API keys, only to regenerate songs or run the critic, go in a `.env`: `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`.

## The order of work

```bash
# 1. captures (per director script): build the director into the game, capture, prepare edit-ready plates
python projects/so-back/machinima/melee/build.py projects/so-back sacred
python projects/so-back/machinima/dolphin.py run ~/games/melee/disc/sys/main.dol ~/games/melee/plates/soback_sacred_cap --until 'DIRECTOR END' --res 4
python projects/so-back/prep_plates.py ~/games/melee/plates/soback_sacred/v --stage ~/games/melee/plates/soback_sacred_cap
ln -sfn ~/games/melee/plates projects/so-back/assets/plates
# 2. vocals: decode the announcer banks, then build the stem and the caption timings
sh projects/so-back/vocals/decode_banks.sh ~/games/melee/disc/files/audio
python projects/so-back/vocals/arrange.py
# 3. type: extract Melee's lettering (see projects/so-back/type/README.md)
# 4. sound and picture
(cd projects/so-back && python sfx.py && python mix.py)
node engine/render.mjs projects/so-back --serve                    # scrub with sound
node engine/render.mjs projects/so-back --frames --fps=60 --workers=6 && node engine/render.mjs projects/so-back --encode --fps=60 --crf=15
```

Nintendo's Game Content Guidelines cover non-commercial fan videos like this one; read them before monetizing or
redistributing anything.
