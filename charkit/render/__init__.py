"""charkit's own toon renderer (docs/workstreams/toonrender.md): the look's cel shading drawn from a build's export on the
GPU through wgpu, headless, with no Blender in the loop. It draws the boards as EEVEE does (the same cameras, light,
screen-width lines, face shadow, streaks, features through the hair, film filter), about a hundred times faster.

    python -m charkit.render compare charkit/out/NAME --open     # NAME's EEVEE boards against ours, the review page
    python -m charkit.render boards charkit/out/NAME/clawd.vrm --out DIR
    python -m charkit.render bench charkit/out/NAME/clawd.vrm    # seconds per board on this machine
    python -m charkit.render probe                               # the adapters here

    from charkit.render import model, views, gpu
    M = model.load('charkit/out/NAME/clawd.vrm')                # our export read back (numpy, Pillow)
    R = gpu.Renderer(M)                                          # a GPU if there is one, else Mesa's CPU drivers
    for v in views.board_views(M, eye_z=..., L=...):             # scene.boards' views
        img = R.render(v)                                        # (H, W, 3) uint8

Modules: model (the GLB reader), views (the board cameras; the look per view through charkit.shade), normals (the
shading normals Blender gives an outlined object at a line width), gpu (wgpu: the passes), toon.wgsl (the look's
shader, a port of shade.py / faceshade.py's node graphs), resolve.wgsl (EEVEE's film filter, the sRGB curve, the
features pass), compare (per-board measures against EEVEE), page (the review page).
Requirements: charkit/render/requirements.txt.
"""
