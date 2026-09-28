# Melee's own type

Melee's text extracted from a vanilla disc, for films that want the game's own lettering: its word graphics, its menu font,
its HUD digits and its name plates. The engine side is `engine/meleetype.js` (`MT.load`, `mword`, `mtext`, `mname`, `mdigits`).
First used by SO BACK, which wraps these scripts with its own paths (`projects/so-back/type/`).

Everything extracted is game-derived: it lives outside the repo (default `~/games/melee/type/`), and a film serves it through
its gitignored `assets/plates` link.

```bash
.venv/bin/python tools/machinima/melee/type/dumpall.py IfAll.usd GmGover.dat GmRegClr.dat IfComSn.usd GmPause.usd GmRst.usd MnSlChr.usd
.venv/bin/python tools/machinima/melee/type/sisfont.py [DOL] [OUT]        # the menu font straight from main.dol
.venv/bin/python tools/machinima/melee/type/build_type.py [--dump D] [--out O]   # words/, hud/, names/, sis/atlas_hi.png, manifest.js
```

`dumpall.py` runs `datkit` (`mscan`, `mdump`): a small HSD `.dat` texture and model dumper built on HSDRaw. Point `DATKIT` at
your build; the extracted disc comes from `MELEE_DISC`.

| what | where in the game | output |
|---|---|---|
| Word graphics: Game!, Go!, Ready, Time!, Success!, Complete!, Failure, Sudden + Death | `IfAll.usd`, `ScInfCnt_scene_models` #0–7 (CI8 textures on quads, up to 536×184) | `words/*.png` |
| GAME OVER, CONTINUE?, COMING SOON, Pause | `GmGover.dat` (serif capitals, 56 px, I4), `IfComSn.usd`, `GmPause.usd` | `words/*.png` (tint the white ones) |
| Menu font (SIS): full ASCII, kana, 14 kanji, 287 glyphs | `main.dol`: atlas at `0x8040CD40` (32×32 I4); char map at `0x8040C8C0` plus glyph codes at `0x8040C680` (0x2000 + atlas index); margins at `0x8040CB00` (by atlas index) | `sis/atlas.png`, `sis/atlas_hi.png` (128 px cells), `sis/metrics.json` |
| HUD damage digits 0–9, %, HP; P1–P4 and CP tags | `IfAll.usd`: `DmgNum`, `ScInfPnm` | `hud/*.png`, plus `dmg_*_hi.png` (8×, crisp) |
| Name plates: 26 characters, plus the teams and NO CONTEST | `GmRst.usd` `pnlsce#0`: j10 (winner banner, outlined serif), j33 (name label, bold sans) | `names/{banner,label}/*.png` |

The word graphics' own fills (measured per row inside their letters) become `swatches/` and the `styles` in `manifest.js`, so
new words set in the menu font can wear the game's dress: black outline, white inner stroke, a gradient fill with diagonal
streaks, a drop shadow.
