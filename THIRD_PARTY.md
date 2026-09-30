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
- `charkit/assets/base_anime/`: charkit's anime base mesh, derived from the MakeHuman CC0 assets above by `charkit/base_anime.py`; CC0 1.0 (`charkit/assets/base_anime/LICENSE.md`).
- `charkit/geom/` (the geometry kernel, docs/GEOM.md) runs on these Python packages in the venv. They are installed
  with pip and not vendored; `charkit/geom/requirements.txt` pins them. All are permissive and commercial use is fine:
  [manifold3d](https://github.com/elalish/manifold) 3.5.4 (Apache-2.0; its wheel builds on oneTBB, Apache-2.0, and
  Clipper2, BSL-1.0) for exact booleans; [scikit-image](https://scikit-image.org) 0.26 (BSD-3-Clause) for marching
  cubes; [SciPy](https://scipy.org) 1.18 (BSD-3-Clause) for sparse graphs, KD-trees and distance transforms;
  [Numba](https://numba.pydata.org) 0.67 (BSD-2-Clause) with llvmlite 0.49 (BSD-2-Clause and Apache-2.0 with the LLVM
  exception) for the BVH, remeshing and rasteriser kernels; [Pillow](https://python-pillow.org) 12.3 (MIT-CMU) to
  decode glTF textures; and, for tests only, [pytest](https://pytest.org) 9.1 (MIT) with pluggy (MIT) and iniconfig
  (MIT). The Blender side (`charkit/geom/io.py`, `charkit/geom/blender.py`) needs only numpy.
- `charkit/render/` (the toon renderer, docs/workstreams/toonrender.md) runs on [wgpu-py](https://github.com/pygfx/wgpu-py)
  0.32 (BSD-2-Clause), which bundles [wgpu-native](https://github.com/gfx-rs/wgpu-native) (MIT OR Apache-2.0), with cffi
  (MIT), rendercanvas (BSD-2-Clause) and, on macOS, rubicon-objc (BSD-3-Clause); installed with pip, not vendored
  (`charkit/render/requirements.txt`). Without a GPU it uses the system's Mesa (MIT: llvmpipe, lavapipe).
