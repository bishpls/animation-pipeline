# Third-party components

- `engine/vendor/fontkit.js`: a browser bundle of [fontkit](https://github.com/foliojs/fontkit) (MIT).
- `engine/fonts/`: Google Fonts, SIL Open Font License 1.1 (see `engine/fonts/`).
- `engine/vendor/three-vrm.js`: a browser bundle (esbuild; the recipe is `engine/vendor/three-vrm.entry.mjs`) of
  [three.js](https://github.com/mrdoob/three.js) 0.186.1 (MIT) and [@pixiv/three-vrm](https://github.com/pixiv/three-vrm) 3.5.5 with
  its packages (MIT); both licence texts in `engine/vendor/three-vrm.LICENSE.txt`.
- `vendor/blender_addons/io_scene_vrm/` (gitignored, fetched and checksummed by `charkit/export.py`, not redistributed):
  [VRM Add-on for Blender](https://github.com/saturday06/VRM-Addon-for-Blender) 4.7.2 by saturday06 and iCyP, dual-licensed
  MIT OR GPL-3.0-or-later, used under MIT.
- `engine/render.mjs`: adapted from [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) (MIT, `docs/references/ClaudeAnimationBase_LICENSE`).
- `docs/references/ClaudeAnimationBase_ANIMATION_GUIDE.md`: © John Heibel, MIT.
- `projects/open-all-night/assets/song.mp3`: generated with ElevenLabs Music from original lyrics; subject to ElevenLabs' terms.
- `charkit/assets/makehuman/`: the MakeHuman base mesh (hm08), default skeleton and weights, and modelling targets from [MakeHuman](https://github.com/makehumancommunity) assets, CC0 1.0 (`charkit/assets/makehuman/LICENSE.md`). Only the CC0 assets are used; none of MakeHuman's AGPL code.
