"""gait.py: how Melee's cast walks, runs and dashes, measured from `datkit fk` samples (the legs, pelvis, arms and head).

  .venv/bin/python tools/machinima/melee/motion/gait.py                       # the core cast: markdown tables to stdout
  .venv/bin/python tools/machinima/melee/motion/gait.py --codes Mr,Ss --csv OUT.csv
  .venv/bin/python tools/machinima/melee/motion/gait.py --fk DIR --codes Ge --skel DIR/skel   # a build of his own

Every length is in world units (model units x ModelScale) and normalised by the leg length L (hip socket to knee to
ankle in the bind pose, x ModelScale), so fighters of any size compare. Angles are degrees. Conventions (mlib): +Z forward,
+Y up, +X the fighter's left. A foot is in contact while the lower of its ankle and toe joints sits within a small band
of its lowest point (clip(15% of its lift, 2-6% of L)); that threshold is the only heuristic, so read single-frame
duties as +-1 frame. The walks and the run play at rate |v| / attribute (ftwalkcommon.c, ftCo_Run.c), so a stance foot
that stays planted slides back at exactly the attribute speed per animation frame; `slip` is its residual in world units
per frame, `slide` the net drift of the contact point over each stance phase.
"""
import argparse, csv, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mlib

SPEED = {"WalkSlow": "WalkAnimationSpeed", "WalkMiddle": "MidWalkPoint", "WalkFast": "FastWalkSpeed", "Run": "RunAnimationScale"}
CYCLES = ["WalkSlow", "WalkMiddle", "WalkFast", "Run"]
ONESHOT = ["Dash", "TurnRun", "RunBrake"]
INTERNAL = {"Mr": "Mario", "Lg": "Luigi", "Dr": "Drmario", "Ms": "Mars", "Fe": "Emblem", "Fx": "Fox", "Fc": "Falco", "Lk": "Link",
            "Cl": "Clink", "Sk": "Seak", "Ca": "Captain", "Ns": "Ness", "Pe": "Peach", "Ss": "Samus", "Gn": "Ganon", "Kp": "Koopa",
            "Dk": "Donkey", "Ys": "Yoshi", "Zd": "Zelda", "Mt": "Mewtwo", "Pk": "Pikachu", "Pc": "Pichu", "Pr": "Purin", "Kb": "Kirby",
            "Gw": "Gamewatch", "Pp": "Popo", "Ge": "Geno"}
# the distinct core animators (near-copies left out: Luigi, Dr. Mario, Roy, Falco, Young Link)
DISTINCT = ["Mr", "Ms", "Fx", "Lk", "Sk", "Ca", "Ns", "Pe", "Ss", "Gn"]


def ang(u, v):
    """angle between vectors, per frame (deg)"""
    c = (u * v).sum(-1) / (np.linalg.norm(u, axis=-1) * np.linalg.norm(v, axis=-1) + 1e-9)
    return np.degrees(np.arccos(np.clip(c, -1, 1)))


def sag(v):
    """a vector's angle in the side (Y-Z) plane, 0 = straight down, positive = swung forward (+Z)"""
    return np.degrees(np.arctan2(v[..., 2], -v[..., 1]))


def leg_length(a, s, side):
    Rw, T = a.rest_world()
    h, k, an = s[side + "hip"], s[side + "knee"], s[side + "ank"]
    return float(np.linalg.norm(T[k] - T[h]) + np.linalg.norm(T[an] - T[k]))


def contacts(a, s, side, L):
    n = a.nf - 1
    pts = [s[side + "ank"]] + ([s[side + "toe"]] if s.get(side + "toe") is not None else [])
    Y = np.stack([a.P[:n, j, 1] for j in pts])
    low = np.argmin(Y, axis=0)
    y = Y.min(axis=0)
    g = y.min()
    thr = float(np.clip(0.15 * (y.max() - g), 0.02 * L, 0.06 * L))
    return (y - g) < thr, low, pts


def runs(mask):
    """cyclic runs of True: list of index arrays"""
    n = len(mask)
    if mask.all(): return [np.arange(n)]
    if not mask.any(): return []
    start = int(np.argmin(mask))                       # a False frame: unroll from there
    out, cur = [], []
    for k in range(1, n + 1):
        i = (start + k) % n
        if mask[i]: cur.append(i)
        elif cur: out.append(np.array(cur)); cur = []
    if cur: out.append(np.array(cur))
    return out


def half_range(x):
    return float((np.max(x) - np.min(x)) / 2)


def unwrap(deg):
    return np.degrees(np.unwrap(np.radians(deg)))


def phase_lag(ref, x, n):
    """frames by which x trails ref (cyclic cross-correlation peak), in -n/2..n/2"""
    a, b = ref - ref.mean(), x - x.mean()
    c = [np.dot(a, np.roll(b, -k)) for k in range(n)]
    k = int(np.argmax(c))
    return k if k <= n // 2 else k - n


def cycle(code, act, a, s, at, sc):
    n = a.nf - 1
    v = at.get(SPEED[act])
    L = 0.5 * (leg_length(a, s, "l") + leg_length(a, s, "r")) * sc
    row = {"char": code, "action": act, "frames": n, "speed": v, "L": round(L, 2)}
    if v: row["stride_L"] = v * n / L
    P = a.P[:n] * sc
    duty, strikes = {}, {}
    for side in "lr":
        st, low, pts = contacts(a, s, side, L)
        duty[side] = st.mean()
        hip, knee, ank = s[side + "hip"], s[side + "knee"], s[side + "ank"]
        flex = 180 - ang(P[:, hip] - P[:, knee], P[:, ank] - P[:, knee])     # 0 = straight
        rs = runs(st)
        if not rs: continue
        main = max(rs, key=len)
        strikes[side] = main[0] / n
        row[f"{side}_duty"] = st.mean()
        row[f"{side}_knee_strike"] = flex[main[0]]
        row[f"{side}_knee_stance_max"] = flex[main].max()
        row[f"{side}_knee_stance_min"] = flex[main].min()
        row[f"{side}_knee_swing_max"] = flex[~st].max() if (~st).any() else float("nan")
        ay = P[:, ank, 1]
        row[f"{side}_lift_L"] = (ay.max() - ay.min()) / L
        if s.get(side + "toe") is not None:
            f = P[:, s[side + "toe"]] - P[:, ank]
            pitch = np.degrees(np.arctan2(f[:, 1], np.hypot(f[:, 0], f[:, 2])))
            flat = np.median(pitch[main])
            row[f"{side}_pitch_strike"] = pitch[main[0]] - flat          # + = toe up (heel strike)
            row[f"{side}_pitch_off"] = pitch[main[-1]] - flat            # - = heel up (toe off)
            row[f"{side}_pitch_swing_min"] = (pitch - flat).min()
        # the planted point: residual slip, net slide per stance
        if v:
            Z = np.stack([a.P[:, j, 2] for j in pts]) * sc
            dz = (Z[:, 1:] - Z[:, :-1])[low, np.arange(n)]
            slip = dz + v
            row[f"{side}_slip"] = float(np.abs(slip[main[:-1]]).mean()) if len(main) > 1 else float("nan")
            row[f"{side}_ratio"] = float(-dz[main[:-1]].mean() / v) if len(main) > 1 else float("nan")
            row[f"{side}_slide"] = float(slip[main[:-1]].sum()) if len(main) > 1 else float("nan")
        # the ankle's path relative to the hip: fore-aft reach
        rel = P[:, ank] - P[:, hip]
        row[f"{side}_reach_fwd_L"] = rel[:, 2].max() / L
        row[f"{side}_reach_back_L"] = -rel[:, 2].min() / L
    if "l" in strikes and "r" in strikes:
        row["strike_l"], row["strike_r"] = strikes["l"], strikes["r"]
    hy = P[:, s["hips"], 1]
    row["bob_L"] = (hy.max() - hy.min()) / L
    # bob cycles: local minima of the (cyclic) hip height
    d = np.diff(np.r_[hy, hy[:1]])
    row["bob_cycles"] = int(np.sum((np.roll(d, 1) < 0) & (d >= 0)))
    if strikes:
        lo = int(np.argmin(hy))
        row["bob_low_after_strike"] = ((lo / n - min(strikes.values())) % 0.5) * n    # frames after a foot strike
    if s.get("lhip") is not None:
        yaw, roll = mlib.line_yaw(a, s["lhip"], s["rhip"])
        yaw = unwrap(yaw)[:n]; roll = roll[:n]
        row["hip_yaw_mean"], row["hip_yaw_half"], row["hip_roll_half"] = float(yaw.mean()), half_range(yaw), half_range(roll)
    if s.get("lsh") is not None and s.get("rsh") is not None:
        syaw, sroll = mlib.line_yaw(a, s["lsh"], s["rsh"])
        syaw = unwrap(syaw)[:n]
        row["sh_yaw_mean"], row["sh_yaw_half"] = float(syaw.mean()), half_range(syaw)
        if s.get("lhip") is not None:
            c = np.corrcoef(yaw - yaw.mean(), syaw - syaw.mean())[0, 1]
            row["sh_vs_hip_corr"] = float(c)                              # -1 = full counter-rotation
    for side in "lr":
        sh, el, wr = s.get(side + "sh"), s.get(side + "el"), s.get(side + "wr")
        if sh is None or el is None or wr is None: continue
        up = P[:, el] - P[:, sh]; fo = P[:, wr] - P[:, el]
        sw = sag(up)
        row[f"{side}_arm_swing_half"] = half_range(sw)
        row[f"{side}_arm_swing_mean"] = float(sw.mean())
        eb = 180 - ang(-up, fo)
        row[f"{side}_elbow_mean"], row[f"{side}_elbow_half"] = float(eb.mean()), half_range(eb)
        row[f"{side}_forearm_lag"] = phase_lag(sw, sag(fo), n)
        # arm swing phase against the same-side leg (thigh angle): ~n/2 = opposite
        th = sag(P[:, s[side + "knee"]] - P[:, s[side + "hip"]])
        row[f"{side}_arm_vs_leg_lag"] = phase_lag(th, sw, n)
        row[f"{side}_thigh_half"] = half_range(th)
    head, neck = s.get("head"), s.get("neck")
    if s.get("chest") is not None and neck is not None:
        t = P[:, neck] - P[:, s["hips"]]
        lean = np.degrees(np.arctan2(t[:, 2], t[:, 1]))
        row["lean_mean"], row["lean_half"] = float(lean.mean()), half_range(lean)
    if head is not None:
        row["head_bob_vs_hips"] = float((P[:, head, 1].max() - P[:, head, 1].min()) / max(1e-6, hy.max() - hy.min()))
        _, hp = mlib.seg_yaw(a, head)
        row["head_pitch_half"] = half_range(hp[:n])
    return row


def oneshot(code, act, a, s, at, sc):
    n = a.nf - 1
    L = 0.5 * (leg_length(a, s, "l") + leg_length(a, s, "r")) * sc
    P = a.P * sc
    row = {"char": code, "action": act, "frames": n, "L": round(L, 2)}
    tz = P[:, 1, 2]                                             # TransN: the root motion these actions carry
    row["transn_total"] = float(tz[-1] - tz[0])
    row["transn_f0_4"] = float(tz[min(4, n)] - tz[0])
    hy = P[:, s["hips"], 1]
    row["hips_min_L"], row["hips_min_at"] = float((hy.min() - hy[0]) / L), int(np.argmin(hy))
    neck = s.get("neck")
    if neck is not None:
        t = P[:, neck] - P[:, s["hips"]]
        lean = np.degrees(np.arctan2(t[:, 2], t[:, 1]))
        row["lean_f0"], row["lean_max"], row["lean_max_at"] = float(lean[0]), float(lean.max()), int(np.argmax(lean))
        row["lean_min"], row["lean_min_at"] = float(lean.min()), int(np.argmin(lean))
    for side in "lr":
        hip, knee, ank = s[side + "hip"], s[side + "knee"], s[side + "ank"]
        flex = 180 - ang(P[:, hip] - P[:, knee], P[:, ank] - P[:, knee])
        row[f"{side}_knee_max"], row[f"{side}_knee_max_at"] = float(flex.max()), int(np.argmax(flex))
    spread = (P[:, s["lank"], 2] - P[:, s["rank"], 2]) / L
    row["spread_f0"], row["spread_f2"], row["spread_f4"] = float(spread[0]), float(spread[min(2, n)]), float(spread[min(4, n)])
    row["spread_max"], row["spread_max_at"] = float(np.abs(spread).max()), int(np.argmax(np.abs(spread)))
    if s.get("lhip") is not None:
        yaw, _ = mlib.line_yaw(a, s["lhip"], s["rhip"]); yaw = unwrap(yaw)
        row["hip_yaw_f0"], row["hip_yaw_f3"], row["hip_yaw_end"] = float(yaw[0]), float(yaw[min(3, n)]), float(yaw[-1])
    return row


def load(fk, code, act):
    p = os.path.join(fk, code, act + ".json")
    return mlib.Anim(p) if os.path.exists(p) else None


def med(rows, key):
    v = [r[key] for r in rows if key in r and r[key] is not None and not (isinstance(r[key], float) and math.isnan(r[key]))]
    return (float(np.median(v)), float(np.percentile(v, 25)), float(np.percentile(v, 75))) if v else None


def both(r, k):
    vals = [r.get(f"{s}_{k}") for s in "lr" if r.get(f"{s}_{k}") is not None and not math.isnan(r.get(f"{s}_{k}"))]
    return float(np.mean(vals)) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fk", default=mlib.FK)
    ap.add_argument("--codes", default=",".join(DISTINCT))
    ap.add_argument("--csv")
    ap.add_argument("--scale", type=float, help="ModelScale override (a fighter not in attrs.csv)")
    ap.add_argument("--speeds", help="attribute speeds override, e.g. 0.18,0.44,0.7,1.45")
    ap.add_argument("--skel", help="a folder with <code>.txt part maps (a fighter whose skeleton changed since the study)")
    o = ap.parse_args()
    if o.skel:
        mlib.WORK_SKEL = o.skel
    at_all = mlib.attrs()
    rows = []
    for code in o.codes.split(","):
        at = dict(at_all.get(INTERNAL.get(code, code), {}))
        if o.speeds:
            for k, v in zip(CYCLES, map(float, o.speeds.split(","))): at[SPEED[k]] = v
        sc = o.scale or at.get("ModelScale", 1.0)
        w = load(o.fk, code, "Wait1") or load(mlib.FK, code, "Wait1")
        if w is None: continue
        s = mlib.semantic(code, w)
        for act in CYCLES:
            a = load(o.fk, code, act)
            if a is not None: rows.append(cycle(code, act, a, s, at, sc))
        for act in ONESHOT:
            a = load(o.fk, code, act)
            if a is not None: rows.append(oneshot(code, act, a, s, at, sc))
    for r in rows:
        for k in ("duty", "knee_strike", "knee_stance_max", "knee_swing_max", "lift_L", "pitch_strike", "pitch_off", "slip",
                  "ratio", "slide", "arm_swing_half", "elbow_mean", "elbow_half", "forearm_lag", "arm_vs_leg_lag", "thigh_half",
                  "reach_fwd_L", "reach_back_L"):
            b = both(r, k)
            if b is not None: r[k] = b
    if o.csv:
        keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("char", "action", "frames"), k))
        with open(o.csv, "w") as f:
            w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
    fmt = lambda x, p=2: "-" if x is None else (f"{x:.{p}f}" if isinstance(x, float) else str(x))
    cols = [("frames", 0), ("stride_L", 2), ("duty", 2), ("knee_strike", 0), ("knee_stance_max", 0), ("knee_swing_max", 0),
            ("lift_L", 2), ("pitch_strike", 0), ("pitch_off", 0), ("bob_L", 3), ("bob_cycles", 0), ("hip_yaw_half", 0),
            ("hip_roll_half", 0), ("sh_yaw_half", 0), ("sh_vs_hip_corr", 2), ("arm_swing_half", 0), ("elbow_mean", 0),
            ("forearm_lag", 0), ("lean_mean", 0), ("head_bob_vs_hips", 2), ("ratio", 2), ("slide", 2)]
    for act in CYCLES:
        rs = [r for r in rows if r["action"] == act]
        if not rs: continue
        print(f"\n### {act}\n")
        print("| fighter | " + " | ".join(c for c, _ in cols) + " |")
        print("|" + "---|" * (len(cols) + 1))
        for r in rs:
            print(f"| {r['char']} | " + " | ".join(fmt(r.get(c), p) for c, p in cols) + " |")
        if len(rs) > 2:
            print("| **median** | " + " | ".join(fmt(med(rs, c)[0] if med(rs, c) else None, p) for c, p in cols) + " |")
    ocols = [("frames", 0), ("transn_total", 1), ("transn_f0_4", 2), ("hips_min_L", 2), ("hips_min_at", 0), ("lean_f0", 0),
             ("lean_max", 0), ("lean_max_at", 0), ("lean_min", 0), ("lean_min_at", 0), ("spread_f0", 2), ("spread_f2", 2),
             ("spread_f4", 2), ("spread_max", 2), ("spread_max_at", 0), ("hip_yaw_f0", 0), ("hip_yaw_f3", 0), ("hip_yaw_end", 0)]
    for act in ONESHOT:
        rs = [r for r in rows if r["action"] == act]
        if not rs: continue
        print(f"\n### {act}\n")
        print("| fighter | " + " | ".join(c for c, _ in ocols) + " |")
        print("|" + "---|" * (len(ocols) + 1))
        for r in rs:
            print(f"| {r['char']} | " + " | ".join(fmt(r.get(c), p) for c, p in ocols) + " |")
        if len(rs) > 2:
            print("| **median** | " + " | ".join(fmt(med(rs, c)[0] if med(rs, c) else None, p) for c, p in ocols) + " |")


if __name__ == "__main__":
    main()
