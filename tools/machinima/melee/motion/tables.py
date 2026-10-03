"""tables.py: markdown tables for MOTION_STUDY.md from analyze.py's CSVs (prints to stdout)."""
import os, csv, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import mlib

D = os.path.join(mlib.WORK, "data")
ROWS = mlib.CORE + ["Kp", "Dk", "Ys", "Zd", "Mt", "Pk", "Gw", "Ge"]


def load(name):
    return list(csv.DictReader(open(os.path.join(D, name + ".csv"))))


def f(x, fmt="{:+.0f}"):
    try: return fmt.format(float(x))
    except Exception: return "-"


def orient():
    rows = load("orientation")
    idx = {(r["char"], r["action"]): r for r in rows}
    print("| Fighter | Wait1 hips | Wait1 shoulders | Wait1 head | open side | WalkMiddle sh | Run sh (swing) | Dash sh | Fall sh | Guard sh / head | Jab sh | F-smash sh |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in ROWS:
        w = idx.get((c, "Wait1"))
        if not w: continue
        def sh(act, swing=False):
            r = idx.get((c, act))
            if not r: return "-"
            s = f(r.get("shline"))
            if swing:
                s += " (±{:.0f})".format((float(r["shline_max"]) - float(r["shline_min"])) / 2)
            return s
        side = float(w["shline"])
        open_ = "right (front faces camera facing R)" if side < -10 else "left (front faces camera facing L)" if side > 10 else "none (side-on)"
        g = idx.get((c, "Guard"))
        print(f"| {mlib.NAMES[c]} | {f(w['hipline'])} | {f(w['shline'])} | {f(w.get('head'))} | {open_} | {sh('WalkMiddle')} | {sh('Run', True)} | {sh('Dash')} | {sh('Fall')} | "
              f"{(f(g['shline']) + ' / ' + f(g.get('head'))) if g else '-'} | {sh('Attack11')} | {sh('AttackS4S')} |")


def idle():
    rows = load("idle")
    print("| Fighter | Wait1 frames | bob hips / head (% height) | bob cycles per loop | period (frames) |")
    print("|---|---|---|---|---|")
    for r in rows:
        if r["char"] not in ROWS: continue
        print(f"| {mlib.NAMES[r['char']]} | {f(r['frames'], '{:.0f}')} | {f(r.get('hips_bob_pct_h'), '{:.1f}')} / {f(r.get('head_bob_pct_h'), '{:.1f}')} | {r.get('hips_cycles', '-')} | {f(r.get('period'), '{:.0f}')} |")


def foot():
    rows = load("footfall")
    idx = {(r["char"], r["action"]): r for r in rows}
    print("| Fighter | Walk S/M/F cycle (frames) | Run cycle | Run cycle at top speed | stride/height walkF / run | foot backward speed / body speed (walkM, walkF, run) | run contact frames per foot | run flight frames |")
    print("|---|---|---|---|---|---|---|---|")
    for c in ROWS:
        ws = [idx.get((c, a)) for a in ("WalkSlow", "WalkMiddle", "WalkFast")]
        r = idx.get((c, "Run"))
        if not r or None in ws: continue
        def imp(x):
            v = [float(x[k]) for k in ("l_implied_speed_ratio", "r_implied_speed_ratio") if x.get(k)]
            return f"{np.mean(v):.2f}" if v else "-"
        cf = np.mean([float(r["l_duty"]), float(r["r_duty"])]) * (float(r["frames"]))
        print(f"| {mlib.NAMES[c]} | {'/'.join(f(w['frames'], '{:.0f}') for w in ws)} | {f(r['frames'], '{:.0f}')} | {f(r.get('cycle_at_vmax'), '{:.1f}')} | "
              f"{f(ws[2]['stride_per_height'], '{:.2f}')} / {f(r['stride_per_height'], '{:.2f}')} | {imp(ws[1])}, {imp(ws[2])}, {imp(r)} | {cf:.1f} | {r.get('flight_frames', '-')} |")


def jumps():
    rows = load("jumps")
    print("| Fighter | jumpsquat (frames) | hips drop by last squat frame (% height) | knee angle Wait -> squat -> JumpF f0 (deg) | Landing: deepest frame, drop % |")
    print("|---|---|---|---|---|")
    for r in rows:
        if r["char"] not in ROWS: continue
        print(f"| {mlib.NAMES[r['char']]} | {f(r.get('jumpsquat'), '{:.0f}')} | {f(r.get('squat_drop_pct_h'), '{:.0f}')} | {f(r.get('wait_knee'), '{:.0f}')} -> {f(r.get('squat_knee'), '{:.0f}')} -> {f(r.get('jump_f0_knee'), '{:.0f}')} | f{f(r.get('landing_min_frame'), '{:.0f}')}, {f(r.get('landing_drop_pct_h'), '{:.0f}')} |")


def attacks():
    rows = load("attacks")
    for act in ("Attack11", "AttackS4S"):
        print(f"\n{act}:\n")
        print("| Fighter | total | first active | last active | IASA | charge frame | drawn-back extreme (frame) | hips drop before contact (% h) | limb |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            if r["action"] != act or r["char"] not in ROWS or not r.get("startup"): continue
            print(f"| {mlib.NAMES[r['char']]} | {r['total']} | {r['startup']} | {r['last_active']} | {r['iasa']} | {r['charge'] if r['charge'] != '-1' else '-'} | {r.get('windup_frame', '-')} | {f(r.get('hips_drop_pct_h'), '{:.0f}')} | {r.get('limb', '')} |")


if __name__ == "__main__":
    for fn in (orient, idle, foot, jumps, attacks):
        print(f"\n### {fn.__name__}\n"); fn()
