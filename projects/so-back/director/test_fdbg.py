"""Capture test: Final Destination's background over time (the fighters idle, the camera above the stage), for a timeline of
its phases. Run at --res 1 and sheet it."""
import sys
from dsl import Film

f = Film(len_s=150.0)
f.setup(players=[('fox', dict(x=-30, face=1)), ('falco', dict(x=30, face=-1))], seed=7)
f.cam(0.0, eye=(0, 30, 220), at=(0, 55, 0), fov=45, ease='cut')
f.emit(sys.argv[1])
