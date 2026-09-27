"""Smoke test for the director: boot, place Fox and Falco, walk, jab, shine, a slow camera push, a freeze with a camera move."""
import sys
from dsl import Film

f = Film(len_s=6.0)
f.setup(players=[('fox', dict(x=-40, face=1)), ('falco', dict(x=40, face=-1))], seed=7)
fox, falco = f.port(0), f.port(1)
fox.walk(0.5, 1.0, dir=1)              # Fox walks right for a second
falco.move(2.0, 'jab', dir=-1)         # Falco jabs at 2.0 s
fox.move(3.0, 'shine')                 # Fox shines at 3.0 s
falco.move(3.5, 'ftilt', dir=-1)
f.cam(0.0, eye=(0, 25, 220), at=(0, 12, 0), fov=30)
f.cam(3.0, eye=(0, 15, 120), at=(0, 10, 0), fov=30, ease='inout')
f.freeze(4.0, True)
f.orbit(4.0, at=(0, 10, 0), dist=120, yaw=0, pitch=5, ease='inout')
f.orbit(5.0, at=(0, 10, 0), dist=110, yaw=50, pitch=12, ease='cut')
f.freeze(5.0, False)
f.mark(5.5, 1)
f.emit(sys.argv[1])
