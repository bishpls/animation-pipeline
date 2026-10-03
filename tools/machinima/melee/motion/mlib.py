"""mlib: load `datkit fk` samples of Melee fighter animations and name the joints that matter.

Model space (verified in the data and the decomp): +Z is the fighter's forward, +Y up, +X the fighter's LEFT (the L leg and
L arm chains sit at +X in the bind pose). The engine yaws TopN by facing*90deg (fighter.c: ftPartSetRotY(fp, 0,
M_PI_2 * facing_dir)); it never mirrors. The camera looks down world -Z, so facing right shows the model's -X side (its
right) and facing left shows its +X side (its left).

Yaw convention used everywhere here: yaw = atan2(fwd.x, fwd.z) in degrees, 0 = square to +Z (pure side-on in the game),
positive = the segment turned toward the fighter's LEFT (+X). Toward the camera: -yaw when facing right, +yaw when facing
left.
"""
import json, os, re, csv
import numpy as np

WORK = os.path.expanduser("~/games/melee/work/art/motion")
FK = os.path.join(WORK, "fk")

NAMES = {"Mr": "Mario", "Lg": "Luigi", "Dr": "Dr. Mario", "Ms": "Marth", "Fe": "Roy", "Fx": "Fox", "Fc": "Falco",
         "Lk": "Link", "Cl": "Young Link", "Sk": "Sheik", "Ca": "C. Falcon", "Ns": "Ness", "Pe": "Peach", "Ss": "Samus",
         "Gn": "Ganondorf", "Kp": "Bowser", "Dk": "DK", "Ys": "Yoshi", "Zd": "Zelda", "Mt": "Mewtwo", "Pk": "Pikachu",
         "Pc": "Pichu", "Pr": "Jigglypuff", "Kb": "Kirby", "Gw": "G&W", "Pp": "Popo", "Ge": "Geno (blockout)"}
KIND = {"Mr": 0, "Fx": 1, "Ca": 2, "Dk": 3, "Kb": 4, "Kp": 5, "Lk": 6, "Sk": 7, "Ns": 8, "Pe": 9, "Pp": 10, "Pk": 12,
        "Ss": 13, "Ys": 14, "Pr": 15, "Mt": 16, "Lg": 17, "Ms": 18, "Zd": 19, "Cl": 20, "Dr": 21, "Fc": 22, "Pc": 23,
        "Gw": 24, "Gn": 25, "Fe": 26, "Ge": 34}
CORE = ["Mr", "Lg", "Dr", "Ms", "Fe", "Fx", "Fc", "Lk", "Cl", "Sk", "Ca", "Ns", "Pe", "Ss", "Gn"]
EXTRA = ["Kp", "Dk", "Ys", "Zd", "Mt", "Pk", "Pc", "Gw"]


class Anim:
    def __init__(self, path):
        d = json.load(open(path))
        self.name, self.frames, self.flags = d["name"], d["frames"], d["flags"]
        self.parent = np.array([j["p"] for j in d["joints"]])
        self.rest_local = np.array([j["t"] + j["r"] + j["s"] for j in d["joints"]], float)
        P = np.array(d["pose"], float)                      # (F, J, 12)
        self.R = P[:, :, :9].reshape(len(P), -1, 3, 3)      # columns = joint axes in model space
        self.P = P[:, :, 9:]
        self.local = np.array(d["local"], float)
        self.tracks = d["tracks"]
        self.nf = len(P)

    def rest_world(self):
        n = len(self.parent)
        R = np.zeros((n, 3, 3)); T = np.zeros((n, 3))
        for i in range(n):
            t, r, s = self.rest_local[i, :3], self.rest_local[i, 3:6], self.rest_local[i, 6:]
            m = rotz(r[2]) @ roty(r[1]) @ rotx(r[0]) @ np.diag(s)
            p = self.parent[i]
            if p < 0: R[i], T[i] = m, t
            else: R[i], T[i] = R[p] @ m, R[p] @ t + T[p]
        return R, T


def rotx(a):
    c, s = np.cos(a), np.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def roty(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rotz(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def part_map(code):
    """part -> joint from PlCo.dat's bone table (skel/<code>.txt, from `datkit skel PlCo.dat KIND PlXxNr.dat`)."""
    p = os.path.join(globals().get("WORK_SKEL") or os.path.join(WORK, "skel"), f"{code}.txt")
    L = open(p).read().splitlines()
    m = {int(a): int(b) for a, b in re.findall(r"(\d+):(\d+)", L[1]) if int(b) != 255}
    return m


def semantic(code, a):
    """Named joints. Measured part semantics (the decomp's FtPart enum is off by one after RFootJ): 4 HipN, 5 WaistN
    (the chest on the Mario-family skeletons), 7-10 L hip/knee/ankle/foot, 12-15 R, 16 spine, 17 chest ("BustN" on the
    5K skeletons), 19 L shoulder, 21 L elbow, 22 L wrist, 34 neck, 35 head, 37 R shoulder, 39 R elbow, 40 R wrist."""
    pm = part_map(code)
    kids = {}
    for i, p in enumerate(a.parent): kids.setdefault(p, []).append(i)
    s = {"top": 0, "trans": 1, "hips": pm.get(4)}
    s["chest"] = pm.get(17, pm.get(5))
    s["spine"] = pm.get(16)
    for side, o in (("l", 0), ("r", 18)):
        s[side + "sh"], s[side + "el"], s[side + "wr"] = pm.get(19 + o), pm.get(21 + o), pm.get(22 + o)
    for side, o in (("l", 0), ("r", 5)):
        s[side + "hip"], s[side + "knee"], s[side + "ank"], s[side + "foot"] = pm.get(7 + o), pm.get(8 + o), pm.get(9 + o), pm.get(10 + o)
        f = s[side + "foot"]
        s[side + "toe"] = kids.get(f, [None])[0] if f is not None else None
    head = pm.get(35)
    if head is None:
        # unmapped heads (Ganondorf, Pikachu...): the chest's non-arm descendant with the most children (face joints)
        best, bestn = None, 2
        arm = {pm.get(18), pm.get(36)}
        def walk(j, depth):
            nonlocal best, bestn
            for c in kids.get(j, []):
                if c in arm: continue
                n = len(kids.get(c, []))
                if n > bestn and depth < 5: best, bestn = c, n
                walk(c, depth + 1)
        if s["chest"] is not None: walk(s["chest"], 0)
        head = best if best is not None else pm.get(34)
    s["head"] = head
    s["neck"] = pm.get(34) if pm.get(34) != head else None
    if s["neck"] is None and head is not None: s["neck"] = a.parent[head]
    # wrist fallback (Samus's cannon arm has no part 40): the elbow's first child
    for side in "lr":
        if s[side + "wr"] is None and s[side + "el"] is not None:
            s[side + "wr"] = kids.get(s[side + "el"], [None])[0]
    return s


def bind_axis(a, j, axis):
    """the joint's local axis that points along the given model axis in the bind pose"""
    Rw, _ = a.rest_world()
    R = Rw[j] / np.linalg.norm(Rw[j], axis=0)
    return R.T @ np.asarray(axis, float)


def seg_yaw(a, j):
    """per-frame yaw and pitch (deg) of a joint. Yaw comes from its bind-pose lateral (+X) axis, like a line through the
    ears or hip sockets, so a forward lean or a nod never flips it; pitch from its bind-pose forward (+Z) axis."""
    Rn = a.R[:, j] / np.linalg.norm(a.R[:, j], axis=1, keepdims=True)
    lat = Rn @ bind_axis(a, j, (1, 0, 0))
    fwd = Rn @ bind_axis(a, j, (0, 0, 1))
    yaw = np.degrees(np.arctan2(-lat[:, 2], lat[:, 0]))
    pitch = np.degrees(np.arcsin(np.clip(fwd[:, 1] / np.linalg.norm(fwd, axis=1), -1, 1)))
    return yaw, pitch


def line_yaw(a, jl, jr):
    """yaw of a left-right line (L minus R), same convention: 0 when it lies along +X; plus its roll (tilt) in deg"""
    L = a.P[:, jl] - a.P[:, jr]
    yaw = np.degrees(np.arctan2(-L[:, 2], L[:, 0]))
    roll = np.degrees(np.arctan2(L[:, 1], np.hypot(L[:, 0], L[:, 2])))
    return yaw, roll


def attrs():
    rows = list(csv.DictReader(open(os.path.join(WORK, "attrs.csv"))))
    out = {}
    code_of = {v.split(" ")[0]: k for k, v in NAMES.items()}
    for r in rows:
        out[r["fighter"]] = {k: float(v) for k, v in r.items() if k != "fighter" and re.match(r"^-?[\d.eE+-]+$", v or "")}
    return out


def movedata(code):
    p = os.path.expanduser(f"~/games/melee/work/movedata/{code}.jsonl")
    if not os.path.exists(p): return {}
    out = {}
    for l in open(p):
        d = json.loads(l)
        if "move" in d: out[d["move"]] = d
        elif "body" in d: out["_" + d["body"]] = d
    return out


def load(code, action):
    p = os.path.join(FK, code, action + ".json")
    return Anim(p) if os.path.exists(p) else None
