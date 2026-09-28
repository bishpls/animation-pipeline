# SO BACK's type: Melee's own text

Everything is extracted from the vanilla disc, and is game-derived: it lives in `~/games/melee/plates/soback_type/`, never in git.
The film serves it as `assets/plates/soback_type`.

```bash
.venv/bin/python projects/so-back/type/dumpall.py IfAll.usd GmGover.dat GmRegClr.dat IfComSn.usd GmPause.usd GmRst.usd MnSlChr.usd
.venv/bin/python projects/so-back/type/sisfont.py            # the menu font straight from main.dol
.venv/bin/python projects/so-back/type/build_type.py         # words/, hud/, names/, sis/atlas_hi.png, manifest.js
```

`dumpall.py` runs `datkit` (`mdump`, `mscan`): a small HSD `.dat` texture and model dumper built on HSDRaw, not included here; point it at your own build (`~/games/melee/work/soback/type/datkit_bin`).

| what | where in the game | output |
|---|---|---|
| Word graphics: Game!, Go!, Ready, Time!, Success!, Complete!, Failure, Sudden + Death | `IfAll.usd`, `ScInfCnt_scene_models` #0–7 (CI8 textures on quads, up to 536×184) | `words/*.png` |
| GAME OVER, CONTINUE?, COMING SOON, Pause | `GmGover.dat` (serif capitals, 56 px, I4), `IfComSn.usd`, `GmPause.usd` | `words/*.png` (tint the white ones) |
| Menu font (SIS): full ASCII, kana, 14 kanji, 287 glyphs | `main.dol`: atlas at `0x8040CD40` (32×32 I4); char map at `0x8040C8C0` + glyph codes at `0x8040C680` (0x2000 + atlas index); margins at `0x8040CB00` (indexed by atlas index) | `sis/atlas.png`, `sis/atlas_hi.png` (128 px cells), `sis/metrics.json` |
| HUD damage digits 0–9, %, HP; P1–P4 and CP tags | `IfAll.usd`: `DmgNum`, `ScInfPnm` | `hud/*.png`, plus `dmg_*_hi.png` (8×, crisp) |
| Name plates: 26 characters, plus the teams and NO CONTEST | `GmRst.usd` `pnlsce#0`: j10 (winner banner, outlined serif), j33 (name label, bold sans) | `names/{banner,label}/*.png` |

The engine side is `src/meleetype.js` (`MT.load`, `mword`, `mtext`, `mname`, `mdigits`). The test page is `typeboard/`:
`node engine/render.mjs projects/so-back/typeboard --loop=dark|hot --stills=0.1`.
