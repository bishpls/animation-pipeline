"""boards.py: filmstrip boards of sampled Melee poses (datkit fk), drawn as the game camera sees them plus a top view.

  .venv/bin/python tools/machinima/melee/motion/boards.py                  # the default set
  .venv/bin/python tools/machinima/melee/motion/boards.py Mr Wait1 [STEP]  # one board
Each cell: top, the side view as the camera sees a fighter facing RIGHT (screen right = model +Z, the camera on the
model's -X side; the fighter's right-side limbs, nearest the camera, are warm, the left-side ones cool); below it, a top
view with the camera at the bottom (hip line, shoulder line, head arrow; the grey arrow is pure side-on).
Boards go to ~/games/melee/work/art/motion/boards/ (game-derived; never commit them).
"""
import os, sys, math, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
import mlib

OUT = os.path.join(mlib.WORK, "boards")
BG = (246, 244, 239); INK = (40, 40, 48); NEAR = (221, 108, 40); FAR = (70, 120, 190); SPINE = (60, 60, 70)
TORSO = (220, 200, 160); GRID = (225, 222, 214); GROUND = (170, 160, 140)
try:
    FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    FONTB = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 15)
    FONTS = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 11)
except Exception:
    FONT = FONTB = FONTS = ImageFont.load_default()


def chains(s, a):
    """bone segments to draw: (joint, joint, side) with side 'r' near the camera when facing right, 'l' far, 'c' centre"""
    segs = []
    def add(x, y, side):
        if s.get(x) is not None and s.get(y) is not None: segs.append((s[x], s[y], side))
    for side in "lr":
        add("hips", side + "hip", side); add(side + "hip", side + "knee", side); add(side + "knee", side + "ank", side); add(side + "ank", side + "toe", side)
        add("chest", side + "sh", side); add(side + "sh", side + "el", side); add(side + "el", side + "wr", side)
    add("hips", "chest", "c"); add("chest", "neck", "c"); add("neck", "head", "c")
    # hands: wrist to its first child (fingers or weapon), and weapons/props: long chains under the wrists
    kids = {}
    for i, p in enumerate(a.parent): kids.setdefault(p, []).append(i)
    for side in "lr":
        w = s.get(side + "wr")
        if w is None: continue
        stack = [(c, w) for c in kids.get(w, [])]
        while stack:
            c, p = stack.pop()
            segs.append((p, c, side + "h"))
            stack += [(k, c) for k in kids.get(c, [])]
    return segs


def project_side(P):
    return np.stack([P[..., 2], P[..., 1]], -1), -P[..., 0]            # (x=forward, y=up), depth toward camera


def draw_cell(d, a, s, t, box, scale, origin, label=None, sub=None, hl=None):
    x0, y0, w, h = box
    top = 34                       # text band
    side_h = int((h - top) * 0.70)
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], fill=BG if hl is None else hl, outline=GRID)
    P = a.P[t]
    uv, depth = project_side(P)
    ox, oy = origin
    def S(p):  # side view screen coords
        return (x0 + w / 2 + (p[0] - ox) * scale, y0 + top + side_h - 8 - (p[1] - oy) * scale)
    gy = S((0, 0))[1]
    d.line([x0 + 6, gy, x0 + w - 6, gy], fill=GROUND, width=1)
    # torso quad: light when its front faces the camera (facing right), dark when the camera sees the back
    q = [s.get(k) for k in ("lsh", "rsh", "rhip", "lhip")]
    if None not in q:
        top_j = s.get("neck") if s.get("neck") is not None else s["chest"]
        L = P[s["lsh"]] - P[s["rsh"]]; up = P[top_j] - P[s["hips"]]
        f = np.cross(L, up); front = -f[0] > 0
        d.polygon([S(uv[j]) for j in q], fill=TORSO if front else (150, 140, 128))
    segs = chains(s, a)
    segs.sort(key=lambda sg: (depth[sg[0]] + depth[sg[1]]) / 2)      # far first
    for j0, j1, side in segs:
        col = NEAR if side.startswith("r") else FAR if side.startswith("l") else SPINE
        wd = 2 if side.endswith("h") else 4
        d.line([S(uv[j0]), S(uv[j1])], fill=col, width=wd)
    # head: a face disc (light = face toward the camera, dark = back of the head) and a nose along its forward axis
    hj = s.get("head")
    if hj is not None:
        c = S(uv[hj]); r = max(5, 0.09 * scale * 11)
        Rn = a.R[t, hj] / np.linalg.norm(a.R[t, hj], axis=0)
        f = Rn @ mlib.bind_axis(a, hj, (0, 0, 1))
        lat = Rn @ mlib.bind_axis(a, hj, (1, 0, 0))
        tc = lat[2]                                   # sin(yaw) toward the camera (facing right) from the ear line
        face = (255, 226, 196) if tc > 0.17 else (120, 110, 104) if tc < -0.17 else (250, 250, 250)
        d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=SPINE, width=2, fill=face)
        nose = (c[0] + f[2] * r * 1.8, c[1] - f[1] * r * 1.8)
        d.line([c, nose], fill=(200, 40, 40), width=3)
    # top view: right = forward (+Z), down = toward the camera (-X); scaled so the shoulder line is ~40% of the cell
    ty0 = y0 + top + side_h; th = h - top - side_h
    cx, cy = x0 + w / 2, ty0 + th / 2
    sw = np.linalg.norm(P[s["lsh"]] - P[s["rsh"]]) if s.get("lsh") is not None else 3.0
    ts = min(w * 0.36 / max(sw, 1e-3), th * 0.8 / max(sw, 1e-3))
    def T(p):
        return (cx + (p[2] - P[s["hips"], 2]) * ts, cy - (p[0] - P[s["hips"], 0]) * ts)
    d.line([x0 + 4, ty0, x0 + w - 4, ty0], fill=GRID)
    d.line([cx - 26, cy, cx + 26, cy], fill=(200, 200, 200), width=1)
    d.polygon([(cx + 26, cy), (cx + 19, cy - 4), (cx + 19, cy + 4)], fill=(200, 200, 200))
    for l, r_, col in (("lhip", "rhip", (150, 110, 60)), ("lsh", "rsh", (70, 70, 80))):
        if s.get(l) is not None and s.get(r_) is not None:
            pl, pr = T(P[s[l]]), T(P[s[r_]])
            d.line([pr, pl], fill=col, width=3)
            d.ellipse([pr[0] - 4, pr[1] - 4, pr[0] + 4, pr[1] + 4], fill=NEAR)
            d.ellipse([pl[0] - 4, pl[1] - 4, pl[0] + 4, pl[1] + 4], fill=FAR)
    if hj is not None:
        Rn = a.R[t, hj] / np.linalg.norm(a.R[t, hj], axis=0)
        lat = Rn @ mlib.bind_axis(a, hj, (1, 0, 0))
        f = np.array([-lat[2], 0, lat[0]]); f /= (np.linalg.norm(f) + 1e-9)
        hc = T(P[hj]); e = (hc[0] + f[2] * 22, hc[1] - f[0] * 22)
        d.line([hc, e], fill=(200, 40, 40), width=3)
    d.polygon([(cx - 6, y0 + h - 3), (cx + 6, y0 + h - 3), (cx, y0 + h - 11)], fill=(120, 120, 120))
    if label: d.text((x0 + 4, y0 + 3), label, fill=INK, font=FONT)
    if sub: d.text((x0 + 4, y0 + 18), sub, fill=(90, 90, 100), font=FONTS)


def board(code, act, step=1, frames=None, cols=10, cell=(150, 260), marks=None, title=None, out=None):
    a = mlib.load(code, act)
    s = mlib.semantic(code, a)
    frames = frames if frames is not None else list(range(0, a.nf, step))
    js = sorted(set(j for j in s.values() if j is not None) | set(j for sg in chains(s, a) for j in sg[:2]))
    pts = a.P[frames][:, js]
    zmin, zmax = pts[..., 2].min() - 1.0, pts[..., 2].max() + 1.5; ymax = pts[..., 1].max() + 1.0
    scale = min(cell[0] * 0.86 / (zmax - zmin + 1e-6), (cell[1] - 34) * 0.62 / (ymax + 1e-6))
    origin = ((zmin + zmax) / 2, 0.0)
    rows = math.ceil(len(frames) / cols)
    W, H = cols * cell[0] + 20, rows * cell[1] + 70
    im = Image.new("RGB", (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    yh, _ = mlib.seg_yaw(a, s["hips"]); yc, _ = mlib.line_yaw(a, s["lsh"], s["rsh"]); yhd, _ = mlib.seg_yaw(a, s["head"]) if s.get("head") is not None else (np.zeros(a.nf), None)
    d.text((10, 8), title or f"{mlib.NAMES[code]} {act}  ({a.frames:g} frames; side view = as seen facing right; top view: camera below)", fill=INK, font=FONTB)
    d.text((10, 30), "yaw deg (+ = turned to the fighter's left; facing right, toward the camera is -): hips / shoulders / head.  "
                     "Warm = the fighter's right-side limbs, cool = left. Light torso/head = front toward the camera, dark = back toward it, white head = profile (within 10 deg).", fill=(90, 90, 100), font=FONT)
    for k, t in enumerate(frames):
        r, c = divmod(k, cols)
        box = (10 + c * cell[0], 55 + r * cell[1], cell[0], cell[1])
        mk = marks.get(t) if marks else None
        hl = mk[1] if mk else None
        lab = f"f{t}" + (f" {mk[0]}" if mk else "")
        draw_cell(d, a, s, t, box, scale, origin, lab, f"{yh[t]:+.0f} / {yc[t]:+.0f} / {yhd[t]:+.0f}", hl)
    os.makedirs(OUT, exist_ok=True)
    out = out or os.path.join(OUT, f"{code}_{act}.png")
    im.save(out); print(out)
    return out


def attack_marks(code, act):
    """anim frame -> (label, colour) from movedata: action frame n shows anim frame n-1"""
    move = {"Attack11": "jab1", "AttackS4S": "fsmash", "AttackHi4": "usmash", "AttackLw4": "dsmash"}.get(act)
    md = mlib.movedata(code).get(move)
    if not md: return None
    m = {}
    ch = md.get("charge", -1)
    for f in range(md["startup"] - 1, md["last_active"]):
        m[f] = ("HIT", (255, 226, 214))
    if ch is not None and ch > 0: m[ch - 1] = ("charge", (226, 236, 255))
    if md.get("iasa"): m[md["iasa"] - 1] = ("IASA", (222, 244, 222))
    return m


def cast_board(action="Wait1", chars=None, out=None, frame=0):
    chars = chars or mlib.CORE
    cell = (170, 300); cols = 8
    rows = math.ceil(len(chars) / cols)
    im = Image.new("RGB", (cols * cell[0] + 20, rows * cell[1] + 70), (255, 255, 255)); d = ImageDraw.Draw(im)
    d.text((10, 8), f"The cast in {action} frame {frame}, as the camera sees each facing RIGHT (top) and from above (camera below)", fill=INK, font=FONTB)
    d.text((10, 30), "yaw deg hips / shoulders / head (+ = turned to the fighter's left). Facing LEFT the camera sees the other side: negate the sign.", fill=(90, 90, 100), font=FONT)
    for k, code in enumerate(chars):
        a = mlib.load(code, action)
        if a is None: continue
        s = mlib.semantic(code, a)
        js = sorted(set(j for j in s.values() if j is not None) | set(j for sg in chains(s, a) for j in sg[:2]))
        pts = a.P[[frame]][:, js]
        zmin, zmax = pts[..., 2].min() - 1.0, pts[..., 2].max() + 1.5; ymax = pts[..., 1].max() + 1.0
        scale = min(cell[0] * 0.86 / (zmax - zmin + 1e-6), (cell[1] - 34) * 0.62 / (ymax + 1e-6))
        yh, _ = mlib.seg_yaw(a, s["hips"]); yc, _ = mlib.line_yaw(a, s["lsh"], s["rsh"])
        yhd = mlib.seg_yaw(a, s["head"])[0] if s.get("head") is not None else np.zeros(a.nf)
        r, c = divmod(k, cols)
        draw_cell(d, a, s, frame, (10 + c * cell[0], 55 + r * cell[1], cell[0], cell[1]), scale, ((zmin + zmax) / 2, 0),
                  mlib.NAMES[code], f"{yh[frame]:+.0f} / {yc[frame]:+.0f} / {yhd[frame]:+.0f}")
    os.makedirs(OUT, exist_ok=True)
    out = out or os.path.join(OUT, f"cast_{action}.png")
    im.save(out); print(out)


def curves(code, act, out=None):
    """timing chart: striking-wrist forward travel, hips height, and angular speeds per segment, with the hit window"""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    a = mlib.load(code, act); s = mlib.semantic(code, a)
    move = {"Attack11": "jab1", "AttackS4S": "fsmash", "AttackHi4": "usmash", "AttackLw4": "dsmash"}.get(act)
    md = mlib.movedata(code).get(move, {})
    t = np.arange(a.nf)
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for k, lab in (("lwr", "L wrist"), ("rwr", "R wrist"), ("lank", "L ankle"), ("rank", "R ankle")):
        if s.get(k) is not None: ax[0].plot(t, a.P[:, s[k], 2], label=lab + " fwd (Z)")
    ax[0].plot(t, a.P[:, s["hips"], 1], "k--", label="hips height")
    ax[0].set_ylabel("model units"); ax[0].legend(fontsize=8, ncol=3)
    import analyze
    for k in ("hips", "chest", "head", "rsh", "rel", "rwr", "lsh", "lel", "lwr"):
        if s.get(k) is not None: ax[1].plot(t, analyze.ang_speed(a, s[k]), label=k)
    ax[1].set_ylabel("angular speed deg/frame"); ax[1].set_xlabel("anim frame (action frame - 1)"); ax[1].legend(fontsize=8, ncol=5)
    for x in ax:
        if md: x.axvspan(md["startup"] - 1, md["last_active"] - 1, color="#f4c7b0", alpha=0.5)
        if md.get("charge", -1) and md.get("charge", -1) > 0: x.axvline(md["charge"] - 1, color="#6a8fd0", ls=":")
        if md.get("iasa"): x.axvline(md["iasa"] - 1, color="#5a5", ls=":")
    fig.suptitle(f"{mlib.NAMES[code]} {act}: hit window shaded, charge (blue), IASA (green)")
    fig.tight_layout()
    out = out or os.path.join(OUT, f"{code}_{act}_curves.png")
    fig.savefig(out, dpi=110); plt.close(fig); print(out)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        board(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1)
        sys.exit()
    board("Mr", "Wait1", 2)
    board("Mr", "Run", 1)
    board("Mr", "AttackS4S", 1, marks=attack_marks("Mr", "AttackS4S"), cols=11)
    board("Mr", "Attack11", 1, marks=attack_marks("Mr", "Attack11"), cols=8)
    board("Ms", "Wait1", 3)
    board("Ms", "Run", 1)
    board("Ms", "AttackS4S", 1, marks=attack_marks("Ms", "AttackS4S"), cols=10)
    board("Mr", "Turn", 1, cols=13); board("Ms", "Turn", 1, cols=13)
    cast_board("Wait1"); cast_board("Run", frame=0); cast_board("Wait1", mlib.EXTRA + ["Ge"], os.path.join(OUT, "cast_Wait1_extra.png"))
    curves("Mr", "AttackS4S"); curves("Mr", "Attack11"); curves("Ms", "AttackS4S")
