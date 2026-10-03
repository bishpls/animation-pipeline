"""analyze.py: orientation, key/interpolation, loop, overlap, arc, anticipation and footfall metrics for Melee fighters.

  .venv/bin/python tools/machinima/melee/motion/analyze.py            # reads ~/games/melee/work/art/motion/fk/<Xx>/*.json
Writes CSVs and summary.json to ~/games/melee/work/art/motion/data/ (game-derived; never commit them).
"""
import os, sys, json, csv, math
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import mlib

OUT = os.path.join(mlib.WORK, "data")
ACTIONS = ["Wait1", "Wait2", "Wait3", "Wait4", "WalkSlow", "WalkMiddle", "WalkFast", "Dash", "Run", "RunBrake", "Turn",
           "TurnRun", "KneeBend", "JumpF", "Fall", "Landing", "Squat", "SquatWait", "GuardOn", "Guard", "Attack11",
           "AttackS4S", "AttackHi4", "AttackLw4"]
LOOPS = ["Wait1", "WalkSlow", "WalkMiddle", "WalkFast", "Run", "SquatWait", "Fall"]
INTERNAL = {"Mr": "Mario", "Lg": "Luigi", "Dr": "Drmario", "Ms": "Mars", "Fe": "Emblem", "Fx": "Fox", "Fc": "Falco", "Lk": "Link",
            "Cl": "Clink", "Sk": "Seak", "Ca": "Captain", "Ns": "Ness", "Pe": "Peach", "Ss": "Samus", "Gn": "Ganon", "Kp": "Koopa",
            "Dk": "Donkey", "Ys": "Yoshi", "Zd": "Zelda", "Mt": "Mewtwo", "Pk": "Pikachu", "Pc": "Pichu", "Pr": "Purin", "Kb": "Kirby",
            "Gw": "Gamewatch", "Pp": "Popo", "Ge": "Geno"}
INTERP = {1: "CON", 2: "LIN", 3: "SPL0", 4: "SPL", 5: "SLP", 6: "KEY"}


def circ_mean(deg):
    r = np.radians(deg); return float(np.degrees(np.arctan2(np.sin(r).mean(), np.cos(r).mean())))


def unwrap(deg):
    return np.degrees(np.unwrap(np.radians(deg)))


def stats(v):
    u = unwrap(v); m = circ_mean(v)
    # express min/max around the circular mean
    d = (u - u.mean()); return m, m + d.min(), m + d.max()


def height(a):
    return float(a.P[0, :, 1].max() - min(0.0, a.P[0, :, 1].min()))


# ---------------------------------------------------------------- orientation
def orientation(code, act, a, s):
    row = {"char": code, "action": act, "frames": a.frames}
    for k in ("hips", "chest", "head"):
        if s.get(k) is None: continue
        y, p = mlib.seg_yaw(a, s[k])
        row[k], row[k + "_min"], row[k + "_max"] = stats(y)
        row[k + "_pitch"] = float(p.mean())
    if s.get("lhip") is not None and s.get("rhip") is not None:
        y, r = mlib.line_yaw(a, s["lhip"], s["rhip"]); row["hipline"], row["hipline_min"], row["hipline_max"] = stats(y); row["hipline_roll"] = float(r.mean())
    if s.get("lsh") is not None and s.get("rsh") is not None:
        y, r = mlib.line_yaw(a, s["lsh"], s["rsh"]); row["shline"], row["shline_min"], row["shline_max"] = stats(y); row["shline_roll"] = float(r.mean())
    if "head" in row and "chest" in row:
        row["head_vs_chest"] = ((row["head"] - row["chest"] + 180) % 360) - 180
    if "chest" in row and "hips" in row:
        row["chest_vs_hips"] = ((row["chest"] - row["hips"] + 180) % 360) - 180
    return row


# ---------------------------------------------------------------- keys
def region(code, s, a):
    """node -> body region by walking up the tree to a named joint"""
    names = {}
    for k, j in s.items():
        if j is not None: names.setdefault(j, k)
    reg = {}
    for j in range(len(a.parent)):
        k = j; lab = None
        while k >= 0:
            if k in names:
                n = names[k]
                lab = ("root" if n in ("top", "trans") else "hips" if n == "hips" else "spine/head" if n in ("chest", "spine", "neck", "head")
                       else "hands" if n in ("lwr", "rwr") else "arms" if n[1:] in ("sh", "el") else "legs")
                break
            k = a.parent[k]
        if j in (2, 3): lab = "root"
        reg[j] = lab or "other"
    return reg


def keystats(code, act, a, s):
    reg = region(code, s, a)
    dur = max(a.frames, 1)
    ic = {v: 0 for v in INTERP.values()}
    per_reg = {}
    spacing, anim_tracks, all_tracks, baked = [], 0, 0, 0
    tan_ratio, flat_ext, ext = [], 0, 0
    for t in a.tracks:
        keys = t["keys"]; all_tracks += 1
        vals = [k for k in keys if k[3] != 5]
        for k in keys: ic[INTERP.get(k[3], "?")] = ic.get(INTERP.get(k[3], "?"), 0) + 1
        v = np.array([k[1] for k in vals]) if vals else np.zeros(1)
        if len(vals) < 2 or np.ptp(v) < 1e-4: continue
        anim_tracks += 1
        fr = sorted(set(k[0] for k in vals))
        sp = np.diff(fr); spacing += list(sp)
        if len(fr) >= dur: baked += 1
        r = reg.get(t["node"], "other")
        per_reg.setdefault(r, []).append(len(fr) / (dur / 60.0))
        # spline tangents vs the neighbours' slope, and flat tangents at extremes
        for i in range(1, len(vals) - 1):
            f0, v0 = vals[i - 1][0], vals[i - 1][1]; f1, v1, d1, op = vals[i][0], vals[i][1], vals[i][2], vals[i][3]
            f2, v2 = vals[i + 1][0], vals[i + 1][1]
            if op != 4 or f2 <= f0 or f1 == f0 or f2 == f1: continue
            cd = (v2 - v0) / (f2 - f0)
            is_ext = (v1 - v0) * (v2 - v1) < 0 and abs(v1 - v0) > 1e-3 and abs(v2 - v1) > 1e-3
            if is_ext:
                ext += 1
                scale = max(abs(v1 - v0) / (f1 - f0), abs(v2 - v1) / (f2 - f1))
                if abs(d1) < 0.1 * scale: flat_ext += 1
            elif abs(cd) > 1e-3:
                tan_ratio.append(d1 / cd)
    nval = sum(ic[k] for k in ("CON", "LIN", "SPL0", "SPL", "KEY"))
    row = {"char": code, "action": act, "frames": a.frames, "tracks": all_tracks, "animated": anim_tracks,
           "key_spacing_med": float(np.median(spacing)) if spacing else None,
           "key_spacing_mean": float(np.mean(spacing)) if spacing else None,
           "baked_tracks": baked, "slp": ic["SLP"], "value_keys": nval,
           "tan_vs_cd_med": float(np.median(tan_ratio)) if tan_ratio else None,
           "flat_at_extremes": (flat_ext / ext) if ext else None}
    for k in ("CON", "LIN", "SPL0", "SPL"):
        row["pct_" + k] = 100.0 * ic[k] / nval if nval else 0
    for r, v in per_reg.items(): row["kps_" + r] = float(np.median(v))
    return row


# ---------------------------------------------------------------- loops
MAIN = ("hips", "chest", "head", "lsh", "lel", "lwr", "rsh", "rel", "rwr", "lknee", "lank", "rknee", "rank", "ltoe", "rtoe")


def loopstats(code, act, a, s):
    js = [s[k] for k in MAIN if s.get(k) is not None]
    P = a.P[:, js]; H = height(a); N = a.nf - 1
    gap = np.linalg.norm(P[N] - P[0], axis=1).max() / H
    v = np.diff(P, axis=0)                      # N velocities
    acc = np.linalg.norm(np.diff(v, axis=0), axis=2)  # interior |a|
    seam = np.linalg.norm(v[0] - v[-1], axis=1)       # |a| across the seam (frame N == frame 0)
    typical = np.percentile(acc, 90, axis=0)
    ratio = float(np.max(seam / np.maximum(typical, 1e-6)))
    return {"char": code, "action": act, "frames": a.frames, "seam_gap_pct_h": 100 * gap, "seam_accel_vs_p90": ratio}


# ---------------------------------------------------------------- overlap (phase lags)
def phase_lag(sig_parent, sig_child, n, k=None):
    """lag in frames of child behind parent at the dominant harmonic of the parent (cyclic over n frames)"""
    x = sig_parent[:n] - sig_parent[:n].mean(); y = sig_child[:n] - sig_child[:n].mean()
    X = np.fft.rfft(x); Y = np.fft.rfft(y)
    if k is None: k = int(np.argmax(np.abs(X[1:6]))) + 1
    dphi = np.angle(X[k]) - np.angle(Y[k])
    dphi = (dphi + np.pi) % (2 * np.pi) - np.pi
    return float(dphi / (2 * np.pi * k) * n), k, float(np.abs(Y[k]) / max(np.abs(X[k]), 1e-9))


def seg_angle(a, j0, j1, plane="sag"):
    d = a.P[:, j1] - a.P[:, j0]
    return np.degrees(np.arctan2(d[:, 2], -d[:, 1]))          # swing forward(+)/back in the sagittal plane


def overlap(code, act, a, s):
    n = a.nf - 1
    row = {"char": code, "action": act, "frames": a.frames}
    if n < 6: return row
    # vertical bob chain
    ch = [k for k in ("hips", "chest", "neck", "head") if s.get(k) is not None]
    ys = {k: a.P[:, s[k], 1] for k in ch}
    row["bob_k"] = None
    if "hips" in ys:
        base = ys["hips"]
        for k in ch[1:]:
            lag, kk, amp = phase_lag(base, ys[k], n)
            row[f"bob_lag_{k}"] = lag; row["bob_k"] = kk
    # pitch chain: chest pitch vs head pitch
    if s.get("chest") is not None and s.get("head") is not None:
        _, pc = mlib.seg_yaw(a, s["chest"]); _, ph = mlib.seg_yaw(a, s["head"])
        if np.ptp(pc[:n]) > 0.5: row["pitch_lag_head"], _, row["pitch_gain_head"] = phase_lag(pc, ph, n)
    # arm swing chain (both arms, averaged): upper arm -> forearm -> hand (wrist to its first child) angles
    for side in "lr":
        sh, el, wr = s.get(side + "sh"), s.get(side + "el"), s.get(side + "wr")
        if None in (sh, el, wr): continue
        up = seg_angle(a, sh, el); fo = seg_angle(a, el, wr)
        if np.ptp(up[:n]) > 3:
            row[f"arm_lag_{side}"], _, row[f"arm_gain_{side}"] = phase_lag(up, fo, n)
    for side in "lr":
        hp, kn, an = s.get(side + "hip"), s.get(side + "knee"), s.get(side + "ank")
        if None in (hp, kn, an): continue
        th = seg_angle(a, hp, kn); sh = seg_angle(a, kn, an)
        if np.ptp(th[:n]) > 3:
            row[f"leg_lag_{side}"], _, _ = phase_lag(th, sh, n)
    return row


def ang_speed(a, j):
    R = a.R[:, j] / np.linalg.norm(a.R[:, j], axis=1, keepdims=True)
    out = [0.0]
    for t in range(1, a.nf):
        M = R[t] @ R[t - 1].T
        out.append(math.degrees(math.acos(max(-1, min(1, (np.trace(M) - 1) / 2)))))
    return np.array(out)


# ---------------------------------------------------------------- attacks
def attack(code, act, a, s, md):
    move = {"Attack11": "jab1", "AttackS4S": "fsmash", "AttackHi4": "usmash", "AttackLw4": "dsmash"}[act]
    d = md.get(move)
    H = height(a)
    row = {"char": code, "action": act, "frames": a.frames}
    if not d: return row
    c0 = d["startup"] - 1; c1 = d["last_active"] - 1          # anim frames (action frame n shows anim frame n-1)
    if c0 is None or c0 < 1 or c0 >= a.nf - 1: return row
    c1 = min(max(c1, c0), a.nf - 2)
    row.update({"startup": d["startup"], "last_active": d["last_active"], "iasa": d.get("iasa"), "charge": d.get("charge"), "total": d.get("frames")})
    # striking limb: the wrist or ankle moving fastest at contact
    cands = [k for k in ("lwr", "rwr", "lank", "rank", "ltoe", "rtoe") if s.get(k) is not None]
    sp = {k: np.linalg.norm(a.P[min(c0 + 1, a.nf - 1), s[k]] - a.P[max(c0 - 1, 0), s[k]]) for k in cands}
    lim = max(sp, key=sp.get); j = s[lim]; row["limb"] = lim
    # direction of the strike: from the limb's position 3 frames before contact to contact
    p = a.P[:, j]
    dirv = p[c0] - p[max(c0 - 3, 0)]; dirv = dirv / (np.linalg.norm(dirv) + 1e-9)
    proj = (p - p[c0]) @ dirv
    wind = int(np.argmin(proj[: c0 + 1]))                      # most drawn-back frame before contact
    row["windup_frame"] = wind + 1
    row["windup_dist_pct_h"] = float(100 * (proj[0] - proj[wind]) / H)          # moved against the strike before it
    row["windup_frames"] = wind                                  # frames spent drawing back
    # strike: path length and arc (sagitta / chord) from wind-up to contact
    seg = p[wind: c0 + 1]
    if len(seg) >= 3:
        chord = seg[-1] - seg[0]; L = np.linalg.norm(chord)
        dev = np.linalg.norm(np.cross(seg - seg[0], chord / (L + 1e-9)), axis=1).max() if L > 1e-6 else 0
        row["strike_arc_ratio"] = float(dev / (L + 1e-9)); row["strike_len_pct_h"] = float(100 * L / H)
    # follow-through: frames after the last active frame until the limb stops moving along the strike (speed < 15% peak)
    v = np.linalg.norm(np.diff(p, axis=0), axis=1)
    peak = v[max(wind, 0): c1 + 1].max() if c1 + 1 > wind else v.max()
    ft = c1
    while ft + 1 < len(v) and v[ft] > 0.15 * peak: ft += 1
    row["follow_settle_frame"] = ft + 1
    # proximal-to-distal sequencing: frame of peak angular speed per segment, wind-up .. last active + 4
    lo, hi = max(wind - 2, 0), min(c1 + 5, a.nf)
    if hi - lo < 2: lo, hi = 0, a.nf
    side = lim[0]
    seq = {}
    for k in ("hips", "chest", side + "sh", side + "el", side + "wr") if lim.endswith("wr") else ("hips", side + "hip", side + "knee", side + "ank"):
        if s.get(k) is None: continue
        w = ang_speed(a, s[k]); seq[k] = int(lo + np.argmax(w[lo:hi])) + 1
    row["peak_seq"] = " ".join(f"{k}:{v}" for k, v in seq.items())
    # head settle: frames after the chest's peak angular speed until the head's angular speed peaks
    if s.get("head") is not None and s.get("chest") is not None:
        wc, wh = ang_speed(a, s["chest"]), ang_speed(a, s["head"])
        row["head_peak_minus_chest"] = int(np.argmax(wh[lo:hi]) - np.argmax(wc[lo:hi]))
    # body squash: hips height drop before contact
    hy = a.P[:, s["hips"], 1]
    row["hips_drop_pct_h"] = float(100 * (hy[0] - hy[: c0 + 1].min()) / H)
    return row


# ---------------------------------------------------------------- idle
def idle(code, a, s):
    H = height(a); n = a.nf - 1
    row = {"char": code, "frames": a.frames, "height": H}
    for k in ("hips", "chest", "head"):
        if s.get(k) is None: continue
        y = a.P[:n, s[k], 1]
        row[f"{k}_bob_pct_h"] = float(100 * np.ptp(y) / H)
        X = np.abs(np.fft.rfft(y - y.mean())); kk = int(np.argmax(X[1:8])) + 1
        row[f"{k}_cycles"] = kk
    if "hips_cycles" in row: row["period"] = n / row["hips_cycles"]
    # sway: lateral (X, toward/away camera) and forward (Z) of the head
    if s.get("head") is not None:
        row["head_sway_z_pct_h"] = float(100 * np.ptp(a.P[:n, s["head"], 2]) / H)
    # arm idle motion: wrist path length per cycle / H
    for side in "lr":
        if s.get(side + "wr") is not None:
            row[f"{side}wr_path_pct_h"] = float(100 * np.linalg.norm(np.diff(a.P[:, s[side + "wr"]], axis=0), axis=1).sum() / H)
    return row


# ---------------------------------------------------------------- jumps
def jumps(code, s, at, loads):
    w, kb, jf, ld = loads("Wait1"), loads("KneeBend"), loads("JumpF"), loads("Landing")
    row = {"char": code}
    if not (w and kb): return row
    H = height(w); hy0 = w.P[0, s["hips"], 1]
    J = int(at.get("JumpStartupLag", 0))
    row["jumpsquat"] = J
    hk = kb.P[:, s["hips"], 1]
    row["squat_drop_pct_h"] = float(100 * (hy0 - hk[: max(J, 1)].min()) / H)
    row["squat_frame_of_min"] = int(np.argmin(hk[: max(J, 1)]))
    row["landing_min_frame"] = int(np.argmin(hk)); row["landing_drop_pct_h"] = float(100 * (hy0 - hk.min()) / H)
    row["landing_frames"] = kb.frames
    if jf:
        hj = jf.P[:, s["hips"], 1]
        row["jump_f0_stretch_pct_h"] = float(100 * (hj[0] - hy0) / H)
        row["jump_max_stretch_pct_h"] = float(100 * (hj[:6].max() - hy0) / H)
        # knee angles at takeoff
        def knee(a, t, side):
            hp, kn, an = a.P[t, s[side + "hip"]], a.P[t, s[side + "knee"]], a.P[t, s[side + "ank"]]
            u, v = hp - kn, an - kn
            return math.degrees(math.acos(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v)))
        row["jump_f0_knee"] = float((knee(jf, 0, "l") + knee(jf, 0, "r")) / 2)
        row["wait_knee"] = float((knee(w, 0, "l") + knee(w, 0, "r")) / 2)
        row["squat_knee"] = float((knee(kb, max(J - 1, 0), "l") + knee(kb, max(J - 1, 0), "r")) / 2)
    return row


# ---------------------------------------------------------------- footfall
SPEED_ATTR = {"WalkSlow": "WalkAnimationSpeed", "WalkMiddle": "MidWalkPoint", "WalkFast": "FastWalkSpeed", "Run": "RunAnimationScale"}


def footfall(code, act, a, s, at):
    v = at.get(SPEED_ATTR[act]); sc = at.get("ModelScale", 1.0)
    H = height(a); n = a.nf - 1
    vmax = at.get("MaxWalkSpeed") if act.startswith("Walk") else at.get("InitialRunSpeed")   # walk_max_vel / dash_max_velocity
    row = {"char": code, "action": act, "frames": a.frames, "speed": v, "scale": sc,
           "vmax": vmax, "cycle_at_vmax": (n * v / vmax) if (v and vmax and act in ("WalkFast", "Run")) else None,
           "stride_world": v * n if v else None, "stride_per_height": (v * n) / (H * sc) if v else None}
    stances = {}
    for side in "lr":
        an, to = s.get(side + "ank"), s.get(side + "toe")
        if an is None: continue
        pts = [an] + ([to] if to is not None else [])
        Y = np.stack([a.P[:n, j, 1] for j in pts]); Z = np.stack([a.P[:n, j, 2] for j in pts])
        low = np.argmin(Y, axis=0); y = Y.min(axis=0); z = Z[low, np.arange(n)]
        g = y.min(); thr = float(np.clip(0.15 * (y.max() - g), 0.01 * H, 0.03 * H))
        st = (y - g) < thr
        # forward velocity of the contact point in world units, plus body speed
        zc = np.stack([a.P[:, j, 2] for j in pts])                 # (k, n+1)
        dz = (zc[:, 1:] - zc[:, :-1])[low, np.arange(n)] * sc          # per frame, contact point
        slip = dz + (v or 0)
        idx = np.where(st)[0]
        stances[side] = st
        row[f"{side}_duty"] = float(st.mean())
        if len(idx) and v:
            row[f"{side}_slip_pct"] = float(100 * np.abs(slip[idx]).mean() / v)
            row[f"{side}_implied_speed_ratio"] = float(-dz[idx].mean() / v)
        # swing clearance
        row[f"{side}_clear_pct_h"] = float(100 * (y.max() - g) / H)
        # contacts per cycle (rising edges, cyclic)
        row[f"{side}_contacts"] = int(np.sum(st & ~np.roll(st, 1)))
    if "l" in stances and "r" in stances:
        row["flight_frames"] = int(np.sum(~stances["l"] & ~stances["r"]))
        row["double_support_frames"] = int(np.sum(stances["l"] & stances["r"]))
    return row


def main():
    os.makedirs(OUT, exist_ok=True)
    at_all = mlib.attrs()
    chars = [c for c in mlib.CORE + mlib.EXTRA + ["Ge"] if os.path.isdir(os.path.join(mlib.FK, c))]
    tables = {k: [] for k in ("orientation", "keys", "loops", "overlap", "attacks", "idle", "jumps", "footfall")}
    for code in chars:
        at = at_all.get(INTERNAL.get(code, ""), {})
        cache = {}
        def loads(act):
            if act not in cache: cache[act] = mlib.load(code, act)
            return cache[act]
        w = loads("Wait1")
        if w is None: continue
        s = mlib.semantic(code, w)
        md = mlib.movedata(code)
        for act in ACTIONS:
            a = loads(act)
            if a is None: continue
            tables["orientation"].append(orientation(code, act, a, s))
            tables["keys"].append(keystats(code, act, a, s))
            if act in LOOPS: tables["loops"].append(loopstats(code, act, a, s))
            if act in ("Wait1", "Run", "WalkMiddle", "WalkFast", "WalkSlow"): tables["overlap"].append(overlap(code, act, a, s))
            if act.startswith("Attack"): tables["attacks"].append(attack(code, act, a, s, md))
            if act in SPEED_ATTR: tables["footfall"].append(footfall(code, act, a, s, at))
        tables["idle"].append(idle(code, w, s))
        tables["jumps"].append(jumps(code, s, at, loads))
        cache.clear()
        print(code, "done", file=sys.stderr)
    for k, rows in tables.items():
        cols = []
        for r in rows:
            for c in r:
                if c not in cols: cols.append(c)
        with open(os.path.join(OUT, k + ".csv"), "w") as f:
            wr = csv.DictWriter(f, cols); wr.writeheader()
            for r in rows: wr.writerow({c: (round(v, 3) if isinstance(v, float) else v) for c, v in r.items()})
    json.dump(tables, open(os.path.join(OUT, "summary.json"), "w"), default=float)


if __name__ == "__main__":
    main()
