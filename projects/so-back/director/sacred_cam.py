"""The sacred combo's camera, authored in world space from the fighters' deterministic paths (a lab run of the same script
with SOBACK_LAB=1 traces both every frame). The director's own tracking lags a running Falcon by ~19 units, too much for a
portrait close-up, so every key here is world-space, sampled every 2 frames (linear between samples).
    .venv/bin/python projects/so-back/director/sacred_cam.py LAB_OSREPORT OUT.json
Portrait: DirSetup.aspect = 9/16, fov is vertical. Frame times are FILM frames (script = film + PRE)."""
import json, math, sys

PRE = 60
log, out = sys.argv[1], sys.argv[2]
P = {}
for line in open(log):
    w = line.split()
    if w and w[0] == 'POS' and len(w) >= 6:
        P[(int(w[1]), int(w[2]))] = (float(w[3]), float(w[4]))


def pos(port, f):                                 # fighter position at film frame f (nearest traced frame)
    s = int(round(f)) + PRE
    for d in range(0, 400):
        for k in (s - d, s + d):
            if (k, port) in P:
                return P[(k, port)]
    raise KeyError(f)


def smooth(port, f, r):                           # centred moving average over +-r frames (no lag: the path is known)
    xs = [pos(port, f + k) for k in range(-r, r + 1)]
    return (sum(p[0] for p in xs) / len(xs), sum(p[1] for p in xs) / len(xs))


def lerp(a, b, u): return a + (b - a) * u
def lerp3(a, b, u): return tuple(lerp(x, y, u) for x, y in zip(a, b))
def ease(u): u = min(max(u, 0.0), 1.0); return u * u * (3 - 2 * u)
def seg(f, f0, f1): return ease((f - f0) / (f1 - f0))


def orbit(at, dist, yaw, pitch):                  # yaw 0: camera in front (+z); +90: on the +x side
    y, p = math.radians(yaw), math.radians(pitch)
    return (at[0] + dist * math.sin(y) * math.cos(p), at[1] + dist * math.sin(p), at[2] + dist * math.cos(y) * math.cos(p))


FRZ, UNF, HIT = 174, 736, 771                      # film frames: freeze, unfreeze, the punch
F0 = pos(0, FRZ); X0 = pos(1, FRZ)                 # the frozen pair
HEAD = (F0[0] + 2, F0[1] + 13, 0.0)                # Falcon's head in the windup (tuned on the frames)
FIST = (F0[0] - 4, F0[1] + 10, 0.0)
# measured on the frozen pose (hurtbox capsules logged by the shield cue at film 300): the face, the cocked fist pulled back
# behind him, and the open forward hand
FACE = (F0[0] - 3.0, F0[1] + 14.2, 1.4)
COCK = (F0[0] - 8.4, F0[1] + 8.6, -0.6)
OPEN = (F0[0] + 3.9, F0[1] + 11.7, 4.2)
HERO = (0.45 * FACE[0] + 0.55 * COCK[0], 0.55 * FACE[1] + 0.45 * COCK[1] + 0.5, 0.4)   # between the face and the cocked fist
TEST_ROLLS = __import__('os').environ.get('SOBACK_TEST_ROLLS') == '1'
TAUNT_TEST = __import__('os').environ.get('SOBACK_TAUNT_TEST') == '1'
HERO_ROLL = float(__import__('os').environ.get('SOBACK_HERO_ROLL', '-40'))   # a dutch angle: fist-to-face runs up the frame
IMP = (153.5, -4.0, 0.0)                         # the punch's impact (its hitboxes on the hit frame)
LOCK_W = (18, -8, 140)                           # yaw, pitch (dist unused): nearly side-on, a touch from Fox's front, low.
# From beyond Fox (yaw 65) his Firefox flare, a column of light, stood between the lens and the punch and hid the bird
LOCK_T = (65, -18, 78)                           # the push-in: all in frame from film 756, impact at centre
# compositions solved against screen targets (Falcon's head, feet and Fox's middle) with screen() below:
OTS_A = (F0[0] + 0.25 * (X0[0] - F0[0]), F0[1] + 8 + 0.25 * (X0[1] - F0[1] - 2), 0.0)   # over the shoulder: yaw -80
OTS_E = (33.2 + (F0[0] - 87.5), 44.8 + (F0[1] - 38.2), 12.9)                          # pitch 8, dist 75, fov 40
OTS_EYE = (OTS_E[0] - F0[0], OTS_E[1] - F0[1], OTS_E[2]); OTS_AT = (OTS_A[0] - F0[0], OTS_A[1] - F0[1])
TWO_A = (F0[0] + 0.65 * (X0[0] - F0[0]), F0[1] + 8 + 0.65 * (X0[1] - F0[1] - 2), 0.0)    # READY?: from beyond Fox, low:
TWO_E = orbit(TWO_A, 96, 80, -10)                                                     # yaw 80, pitch -10, fov 36


def cam(f):
    """(eye, at, fov, roll) at film frame f."""
    if f < 24:                                    # the knee: close and low; eases back as Fox launches
        at = (-56.0, 14.0, 0.0)
        u = seg(f, 8, 24)
        return orbit(at, lerp(62, 92, u), lerp(12, 6, u), lerp(-4, 0, u)), lerp3(at, (-48.0, 16.0, 0.0), u), 30.0, 0.0
    if f < 152:                                   # the chase: side-on, tracking Falcon's dash and dash dance
        fx, _ = smooth(0, f, 10 if f < 70 else 18)
        u = seg(f, 24, 40); v = seg(f, 60, 90)
        at = (fx + lerp(lerp(8, 10, u), 3, v), lerp(16, 14, u), 0.0)
        return orbit(at, lerp(92, 100, u), lerp(6, 0, u), 2.0), at, 30.0, 0.0
    if f < FRZ:                                   # CUT as he leaves the ground: over his shoulder as he flies out
        fx, fy = smooth(0, f, 3)
        u = seg(f, 152, 172)
        ots_eye = (fx + OTS_EYE[0], fy + OTS_EYE[1], OTS_EYE[2])
        ots_at = (fx + OTS_AT[0], fy + OTS_AT[1], 0.0)
        return lerp3((ots_eye[0] - 8, ots_eye[1] - 4, ots_eye[2] + 6), ots_eye, u), ots_at, 40.0, 0.0
    if f < UNF:                                   # the freeze: one slow orbit round the suspended pair
        if f < 300:                               # over the shoulder, down to Fox and the abyss; a slow push
            u = seg(f, FRZ, 300)
            return lerp3(OTS_E, lerp3(OTS_E, OTS_A, 0.1), u), OTS_A, 40.0, 0.0
        e300 = lerp3(OTS_E, OTS_A, 0.1)
        if f < 579:                               # round him to his face by 9.65 s (CONTINUE?)
            u = seg(f, 300, 579)
            piv = lerp3(OTS_A, HEAD, seg(f, 300, 400))
            d0 = math.dist(e300, OTS_A)
            yaw0 = math.degrees(math.atan2(e300[0] - OTS_A[0], e300[2] - OTS_A[2]))
            pitch0 = math.degrees(math.asin((e300[1] - OTS_A[1]) / d0))
            return orbit(piv, lerp(d0, 36, u), lerp(yaw0, 78, u), lerp(pitch0, 6, u)), piv, lerp(40, 30, u), 0.0
        if f < 606:                               # swing round and down to the hero shot: face and cocked fist (from 10.1 s)
            u = seg(f, 579, 606)
            return lerp3(orbit(HEAD, 36, 78, 6), orbit(HERO, 36, 18, -8), u), lerp3(HEAD, HERO, u), 30.0, lerp(0, HERO_ROLL, u)
        if f < 656:                               # hold the hero shot through FIVE (10.45) and FIVE (10.85): a slow push
            u = (f - 606) / 50
            roll = HERO_ROLL if not TEST_ROLLS or f < 630 else -HERO_ROLL
            return orbit(HERO, lerp(36, 31, u), 18, -8), HERO, 30.0, roll
        if f < 699:                               # out to the two-shot by READY? (11.65 s): Falcon's face over Fox's back
            u = seg(f, 656, 699)
            return lerp3(orbit(HERO, 31, 18, -8), TWO_E, u), lerp3(HERO, TWO_A, u), lerp(30, 36, u), lerp(HERO_ROLL, 0, u)
        u = seg(f, 699, UNF)
        return lerp3(TWO_E, lerp3(TWO_E, TWO_A, 0.08), u), TWO_A, 36.0, 0.0
    TWO = TWO_A
    hitp = (148.0, 0.0, 0.0)
    if f < HIT + 5:                               # the windup resumes: a 3/4 from beyond Fox, low, the punch coming at the lens;
        yaw, pitch, dist, at = dive(f)            # the tightest frame that holds Falcon's dive, Fox and the impact
        if f < UNF + 12:                          # out of the READY? two-shot: turn the orbit itself, so both stay framed
            u = seg(f, UNF, UNF + 12)
            at = lerp3(TWO_A, at, u)
            return orbit(at, lerp(96, dist, u), lerp(80, yaw, u), lerp(-10, pitch, u)), at, lerp(36, 34, u), 0.0
        return orbit(at, dist, yaw, pitch), at, 34.0, 0.0
    if f < 818:                                   # then after Fox to the blast line and its explosion
        u = seg(f, HIT + 5, 800)
        y5, p5, d5, a5 = dive(HIT + 5)
        at = lerp3(a5, (228.0, 124.0, 0.0), u)
        return lerp3(orbit(a5, d5, y5, p5), orbit(at, 250, 0, 0), u), at, 34.0, 0.0
    if f < 880:                                   # Falcon falls out of the punch, double-jumps and dives for the ledge
        fx, fy = smooth(0, f, 10)
        at = (fx - 8, fy + 8, 0.0)
        return orbit(at, 110, -10, 4), at, 32.0, 0.0
    if f < 940:                                   # the revival platform brings Fox back
        xp = pos(1, f)
        at = (xp[0], max(xp[1], 45.0) + 6, 0.0)
        return orbit(at, lerp(90, 80, seg(f, 880, 940)), 10, 0), at, 30.0, 0.0
    fx, fy = smooth(0, f, 8)                      # Falcon gets up from the ledge and taunts
    if f < 960:
        at = (fx - 2, fy + 12, 0.0)
        return orbit(at, lerp(70, 62, seg(f, 940, 1100)), -34, 4), at, 32.0, 0.0
    if TAUNT_TEST:                                # which way does he face in the taunt? front, then behind
        at = (78.3, 15.0, 0.0)
        return orbit(at, 40, 0 if f < 1000 else 180, 0), at, 32.0, 0.0
    # the taunt ("Show me ya moves!") turns him to the -z side, away from the game's own camera, so the lens goes round
    # behind the stage to meet him front-on: chest-up, his beckoning hand in frame (screen-left: world +x)
    at = (79.4, 15.2, 0.0)
    return orbit(at, lerp(38, 33, seg(f, 960, 1030)), 180, 2), at, 32.0, 0.0

def screen(eye, at, fov, p, aspect=0.5625):
    """normalized screen position of world point p (x, y in -1..1 inside the frame; roll ignored)."""
    fw = [a - e for a, e in zip(at, eye)]; n = math.sqrt(sum(v * v for v in fw)); fw = [v / n for v in fw]
    up = (0.0, 1.0, 0.0)
    rt = (fw[1] * up[2] - fw[2] * up[1], fw[2] * up[0] - fw[0] * up[2], fw[0] * up[1] - fw[1] * up[0])
    n = math.sqrt(sum(v * v for v in rt)); rt = [v / n for v in rt]
    u2 = (rt[1] * fw[2] - rt[2] * fw[1], rt[2] * fw[0] - rt[0] * fw[2], rt[0] * fw[1] - rt[1] * fw[0])
    v = [a - e for a, e in zip(p, eye)]
    z = sum(a * b for a, b in zip(v, fw)); t = math.tan(math.radians(fov) / 2)
    if z <= 0: return None
    return (sum(a * b for a, b in zip(v, rt)) / (z * t * aspect), sum(a * b for a, b in zip(v, u2)) / (z * t))



_DIVE = {}
def dive(f):
    """(yaw, pitch, dist, at) from the unfreeze to just after the impact: a fixed 3/4 direction (beyond Fox, low), the
    aim between Falcon and the impact, pushed in as far as the frame still holds Falcon's body, Fox's and the impact
    (screen() at |x| < 0.82, |y| < 0.85), then smoothed so the push only ever moves in."""
    if not _DIVE:
        yaw, pitch = LOCK_W[0], LOCK_W[1]
        raw = {}
        for g in range(UNF, HIT + 6):
            F = pos(0, g); X = pos(1, min(g, HIT))
            w = 0.5 if g < HIT - 6 else lerp(0.5, 0.0, seg(g, HIT - 6, HIT))
            at = lerp3(IMP, (F[0] + 1, F[1] + 8, 0.0), w)
            pts = [(F[0] + dx, F[1] + dy, 0.0) for dx, dy in ((0, 0), (0, 16), (-7, 8), (9, 8))]
            pts += [(X[0] + dx, X[1] + dy, 0.0) for dx, dy in ((0, -5), (0, 10), (-5, 2), (5, 2))] + [IMP]
            if g >= HIT - 4:                      # the fire bird: it trails back from the fist over Falcon (film 769 on)
                pts += [(IMP[0] + dx, IMP[1] + dy, 0.0) for dx, dy in ((-26, 4), (-14, 14), (-14, -10), (8, 0))]
            lo, hi = 30.0, 400.0
            for _ in range(30):
                d = (lo + hi) / 2
                eye = orbit(at, d, yaw, pitch)
                ok = all((q := screen(eye, at, 34.0, p)) is not None and abs(q[0]) < 0.82 and abs(q[1]) < 0.85 for p in pts)
                hi, lo = (d, lo) if ok else (hi, d)
            raw[g] = (hi, at)
        best = 1e9
        for g in range(UNF, HIT + 6):             # only ever push in; the last frames hold the impact framing
            best = min(best, raw[g][0]); _DIVE[g] = (yaw, pitch, best, raw[g][1])
    return _DIVE[min(max(int(round(f)), UNF), HIT + 5)]


CUTS = {152, 818, 880, 940, 960}
keys = []
last = int(sys.argv[3]) if len(sys.argv) > 3 else 1110
for f in range(-PRE, last + 1, 2):
    eye, at, fov, roll = cam(f)
    how = 'cut' if (f + 2) in CUTS or (f + 1) in CUTS else 'linear'
    keys.append([f, [round(v, 3) for v in eye], [round(v, 3) for v in at], round(fov, 3), round(roll, 3), how])
    if (f + 1) in CUTS:                           # land the cut on its exact frame
        e2, a2, fv2, r2 = cam(f + 1)
        keys.append([f + 1, [round(v, 3) for v in e2], [round(v, 3) for v in a2], round(fv2, 3), round(r2, 3), 'linear'])
json.dump({'pre': PRE, 'keys': keys}, open(out, 'w'))
print(f'{len(keys)} camera keys -> {out}')

if '--check' in sys.argv:                         # where the fighters land on screen, every 6 frames
    for f in range(-PRE, last + 1, 6):
        eye, at, fov, roll = cam(f)
        row = []
        for port in (0, 1):
            x, y = pos(port, f)
            pts = [screen(eye, at, fov, (x, y + h, 0.0)) for h in (0, 8, 16 if port == 0 else 12)]
            ok = all(q is not None and abs(q[0]) < 1 and abs(q[1]) < 1 for q in pts)
            q = pts[1]
            row.append(f"{'FX'[port]}{'.' if ok else '!'}({q[0]:+.2f},{q[1]:+.2f})" if q else f"{'FX'[port]}- behind")
        print(f, ' '.join(row))
