"""Set presets shared by shots: the moonlit clearing (with eclipse state), and dawn."""
import bpy, math
from mathutils import Vector
import world as WD, char as CH

MOON_POS, MOON_R = Vector((-25, 160, 70)), 16


def night(S, bite=0.0, ring=0.0, trees=220, avoid=11, moon_pos=None, moon_r=None, stars=0.8, sky=None, clear=(), snow=300):
    WD.sky(stars=stars, **(sky or {}))
    m, moonset = WD.moon(Vector(moon_pos or MOON_POS), moon_r or MOON_R, bite=bite, ring=ring, cam=S.cam)
    WD.snowfield(size=snow)
    WD.forest(n=trees, avoid=[(0, 0, avoid)] + list(clear))
    S.moon = m
    return moonset


def moon_track(S, moonset, keys):
    """keys: [(beat, bite, ring)] -> stepped moon state per frame (anime: the eclipse advances in held steps)"""
    keys = sorted(keys)
    def cb(t, f):
        b = t / 0.4
        cur = keys[0]
        for k in keys:
            if b >= k[0]:
                cur = k
        moonset(cur[1], cur[2], f)
    S.per_frame.append(cb)


def dawn(S, trees=220, avoid=11, sun_dir=(-0.2, 1.0, 0.08)):
    WD.sky(top=(0.16, 0.22, 0.46), mid=(0.62, 0.52, 0.62), horizon=(1.0, 0.72, 0.46), stars=0.0)
    WD.snowfield()
    WD.forest(n=trees, avoid=[(0, 0, avoid)])
    # sun: an emissive disk low on the horizon behind the treeline
    import bmesh
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=64, radius=9)
    sun = CH.mesh_from_bm('sun', bm, [CH.flat('sunmat', (1.0, 0.93, 0.75), 4.0)], smooth=False)
    d = Vector(sun_dir).normalized()
    sun.location = d * 170
    c = sun.constraints.new('TRACK_TO'); c.target = S.cam; c.track_axis = 'TRACK_Z'; c.up_axis = 'UP_Y'
    return sun


_PINES = []
def tree_at(x, y, h, seed=0):
    """a hand-placed pine (for composed silhouettes)"""
    import random
    if not _PINES or _PINES[0].name not in bpy.data.meshes:
        _PINES.clear(); _PINES.extend(WD.pine_mesh(f'hpine{i}', random.Random(40 + i), 1.0) for i in range(3))
    ob = bpy.data.objects.new(f'htree_{x:.0f}_{y:.0f}', _PINES[seed % 3])
    ob.location = (x, y, -0.3); ob.scale = (h, h, h); ob.rotation_euler = (0, 0, seed * 1.7)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def crater(r=5.0, seed=3):
    """impact crater: a dark trampled floor, radiating cracks, a rim of heaved ice slabs"""
    import bmesh, random
    from mathutils import Matrix
    rnd = random.Random(seed)
    floor = CH.toon('craterfloor', (0.38, 0.4, 0.62), (0.2, 0.2, 0.38), rim_amt=0.0, thresh=0.5)
    ice = CH.toon('ice', (0.8, 0.86, 1.0), (0.42, 0.46, 0.72), rim=(0.7, 0.9, 1.0), rim_amt=0.3, thresh=0.45)
    crack = CH.flat('crack', (0.05, 0.05, 0.12), 1.0)
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=r)
    for v in bm.verts:
        a = math.atan2(v.co.y, v.co.x); v.co *= 1 + 0.08 * math.sin(a * 5 + 1) + 0.05 * math.sin(a * 11)
    fl = CH.mesh_from_bm('crater_floor', bm, [floor], smooth=False); fl.location.z = 0.015
    bm = bmesh.new()
    for i in range(34):                                       # rim slabs, tilted outward
        a = i / 34 * 6.283 + rnd.uniform(-0.08, 0.08); rr = r * rnd.uniform(0.95, 1.12)
        w, d, h = rnd.uniform(0.5, 1.1), rnd.uniform(0.15, 0.35), rnd.uniform(0.3, 0.9)
        M = (Matrix.Translation((math.cos(a) * rr, math.sin(a) * rr, h * 0.3)) @ Matrix.Rotation(a + 1.5708, 4, 'Z') @
             Matrix.Rotation(rnd.uniform(0.35, 0.8), 4, 'X') @ Matrix.Diagonal((w, d, h, 1)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=M)
    rim = CH.mesh_from_bm('crater_rim', bm, [ice], smooth=False); CH.add_outline(rim, 0.02)
    bm = bmesh.new()                                          # cracks: jagged dark polylines out from the centre
    def branch(p, a, L, n, w0, depth):
        for j in range(n):
            a += rnd.uniform(-0.45, 0.45)
            q = p + Vector((math.cos(a), math.sin(a), 0)) * (L / n) * rnd.uniform(0.7, 1.3)
            wdt = w0 * (1 - j / n) + 0.006
            side = Vector((-math.sin(a), math.cos(a), 0)) * wdt
            vs = [bm.verts.new(p + side), bm.verts.new(q + side * 0.7), bm.verts.new(q - side * 0.7), bm.verts.new(p - side)]
            bm.faces.new(vs)
            if depth > 0 and rnd.random() < 0.35:
                branch(q.copy(), a + rnd.choice([-1, 1]) * rnd.uniform(0.5, 0.9), L * 0.4, max(2, n // 2), wdt * 0.7, depth - 1)
            p = q
    for k in range(13):
        a = k / 13 * 6.283 + rnd.uniform(-0.2, 0.2)
        branch(Vector((0, 0, 0.03)), a, rnd.uniform(0.5, 1.0) * r * 1.3, 9, 0.035, 2)
    for k in range(0):
            pass
    cr = CH.mesh_from_bm('crater_cracks', bm, [crack], smooth=False); cr.location.z = 0.02
    return fl, rim, cr


KING_HEAD = Vector((0, 150, 52))          # the bust rises out of the forest; legs never shown


def hide_king_legs(parts):
    for k, ob in parts.items():
        if k.startswith(('up_', 'lo_')): ob.hide_render = True


def king_state(head=None, s=150.0, jaw=0.35, hp=10.0, t=0.0, dx=Vector((0, 0, 0)), roll=0.0, yaw=0.0):
    """the King posed so its head lands at `head` (pitch 32: shoulders rising behind the head); dx shifts it (e.g. the split)"""
    import kin
    head = Vector(head if head is not None else KING_HEAD)
    st = kin.Wolf(Vector((0, 0, 0)), -math.pi / 2 + yaw, s=s, mode='stand', pitch=32, roll=roll, jaw=jaw, t=t, seed=99, head_pitch=hp)
    off = head - Vector(st.headp) + dx
    return kin.Wolf(off, -math.pi / 2 + yaw, s=s, mode='stand', pitch=32, roll=roll, jaw=jaw, t=t, seed=99, head_pitch=hp)
