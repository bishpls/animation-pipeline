"""Camera keys for the drop montage shots, by orbit: key = (frame, at, yaw, pitch, dist, fov, ease). yaw 0 looks at the stage
from the front, positive swings to the right. Writes drop_<shot>_cam.json with keys [frame, eye, at, fov, roll, ease, track].
    .venv/bin/python projects/so-back/director/drop_cam.py SHOT"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))

SHOTS = {
    'waveshine': [                                   # T0 = 46: shines on 46 and 68, the JC up-smash on 81 (Falco's spawn landing ends ~40)
        (0,   (-9.0, 9.0, 0), 18, 4, 64, 30, 'in'),
        (44,  (-8.0, 9.0, 0), 20, 4, 56, 30, 'linear'),
        (68,  (8.0, 9.0, 0), 24, 4, 54, 30, 'linear'),
        (82,  (23.0, 12.0, 0), 22, 2, 58, 30, 'in'),     # the up-smash, then a whip up after Falco
        (96,  (40.0, 46.0, 0), 16, -8, 70, 30, 'out'),
        (123, (46.0, 64.0, 0), 14, -10, 80, 32, 'cut'),
    ],
    'tipper': [                                      # Marth WD back 36-51 (x 20.7 -> -3.6), Fox SHFFL lands 59 at x 31;
        (0,   (16.0, 11.0, 0), 62, 4, 76, 30, 'in'),   # the tipper lands 63 (hitlag to ~71); Fox is launched up-right,
        (50,  (16.0, 11.0, 0), 64, 4, 70, 30, 'linear'),   # toward and past this camera (it watches from Fox's side)
        (63,  (17.0, 12.0, 0), 64, 4, 70, 30, 'out'),
        (72,  (17.0, 13.0, 0), 64, 4, 70, 30, 'in'),
        (119, (8.0, 16.0, 0), 60, 0, 60, 32, 'cut'),
    ],
    'rest': [                                        # the drill 47-81 (Puff crosses over Fox at x 0), fast fall 75, lands 84
        (0,   (-5.0, 8.0, 0), 30, 8, 60, 30, 'in'),     # (L-cancelled), Rest on 99 hits on 100; Fox flies up-left; Puff sleeps
        (46,  (-5.0, 9.0, 0), 28, 10, 54, 30, 'linear'),
        (84,  (0.5, 7.0, 0), 25, 6, 46, 30, 'linear'),
        (100, (1.0, 7.0, 0), 22, 4, 42, 30, 'out'),
        (106, (0.0, 10.0, 0), 22, 5, 48, 30, 'linear'),
        (155, (3.0, 6.0, 0), 20, 3, 38, 30, 'cut'),
    ],
    'lasers': [                                      # Falco (x -44) short-hop lasers hit Fox (x 0) on 72 and 124 (the second
        (0,   (-30.0, 12.0, 0), -66, 6, 60, 30, 'in'),  # from x -20 after a short dash), then walks in and forward smashes on
        (60,  (-30.0, 12.0, 0), -68, 6, 56, 30, 'linear'),   # 180; over his shoulder, down the laser line
        (126, (-22.0, 12.0, 0), -64, 5, 58, 30, 'linear'),
        (150, (-12.0, 12.0, 0), -52, 5, 56, 30, 'linear'),
        (172, (-2.0, 12.0, 0), -10, 4, 66, 30, 'linear'),   # swing round to the front: at the smash they are 7 apart
        (180, (0.0, 12.0, 0), 0, 4, 68, 30, 'out'),
        (203, (10.0, 16.0, 0), 5, 2, 72, 32, 'cut'),
    ],
    'thunder': [                                     # grab 47 (caught 53), up-throw hits 76/85, Fox peaks y 28 at ~100 and lands
        (0,   (-2.0, 12.0, 0), 14, 3, 60, 30, 'in'),    # (knocked down) at 137; Thunder on 109: the bolt falls from 127 and the
        (53,  (-2.0, 12.0, 0), 14, 3, 56, 30, 'linear'),     # strike on Pikachu hits Fox (17%) at 149, launching him up
        (85,  (-2.0, 22.0, 0), 10, -4, 80, 30, 'linear'),
        (110, (-2.0, 23.0, 0), 8, -6, 88, 30, 'linear'),
        (149, (-2.0, 18.0, 0), 8, -6, 80, 30, 'out'),
        (179, (0.0, 36.0, 0), 6, -10, 96, 32, 'cut'),
    ],
}


def keys(shot):
    out = []
    for fr, at, yaw, pitch, dist, fov, ease in SHOTS[shot]:
        y, p = math.radians(yaw), math.radians(pitch)
        eye = [at[0] + dist * math.sin(y) * math.cos(p), at[1] + dist * math.sin(p), at[2] + dist * math.cos(y) * math.cos(p)]
        out.append([fr, [round(v, 3) for v in eye], list(at), fov, 0.0, ease, None])
    return out


if __name__ == '__main__':
    s = sys.argv[1]
    json.dump({'keys': keys(s)}, open(os.path.join(HERE, f'drop_{s}_cam.json'), 'w'), indent=1)
    print('wrote', f'drop_{s}_cam.json')
