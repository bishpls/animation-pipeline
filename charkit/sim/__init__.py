"""charkit.sim: our own cloth and spring solvers (docs/ROADMAP.md, "To hand-roll" item 1; docs/workstreams/xpbd.md).

    xpbd       XPBD cloth: distance, dihedral bending, hold (the template as a rest target), layers, capsule and
               signed-distance colliders with friction; fixed timestep, substeps, deterministic (numba, one thread)
    settings   the solver's settings from a style profile's physics section; the departures from physics as named dials
    springbone VRMC_springBone-style chains (the rig's spring bones), for comparison and tuning
    rig        venv-side posing: the skeleton's skinning matrices from the build's joints and motion QA's poses, capsule
               colliders fitted to the skin
    drape      the pilots: a garment's rest drape, and garments in motion, measured against the templates

A pilot behind a setting: no garment is simulated unless its spec asks (`drape: {"solver": "xpbd"}`); the templates stay
the default until the measurements say otherwise.
"""
