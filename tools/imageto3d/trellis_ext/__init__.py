"""Our extensions to TRELLIS.2 (microsoft/TRELLIS.2, MIT), kept as our own modules: nothing in the upstream clone is edited.

Box side (torch, the TRELLIS.2 clone on sys.path):
    pipeline.py   a staged run: multi-view conditioning, seeds, per-stage timing and VRAM, the texture stage optional, and the
                  decoded voxel fields kept (not only the fused mesh)
Anywhere (numpy; scipy and scikit-image where noted):
    field.py      the field file (<tag>_field.npz): writer, reader, dense solid / signed distance, the raw mesh, previews
    parts.py      per-voxel part labels (hair / skin / garment / other) and per-part surfaces (marching cubes) as PLY

Nothing here imports torch at package import, so field.py and parts.py run on the laptop.
"""
