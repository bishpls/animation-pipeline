"""Cloth caches for rendered shots: the loose garments moved as the style profile says (charkit.sim.motionqa's
settings: the anime default holds toward the drawn shape carried by the pelvis), baked per clip from a build, measured
as they are baked, and written where a render reads them.

    python -m charkit.sim bake BUILD --clip kick [--out DIR] [--method M] [--pc2]

Where: BUILD/cloth/CLIP/ (beside the build's bundle; a shot's render names the build and the clip). Format:
  cloth.json        what was baked: the clip (a motion QA pose's schedule: 1 s settled at rest, 0.4 s into the pose,
                    0.6 s held, 60 fps; frame `first` is the clip's first, the settle is pre-roll), the method and its
                    settings (style, hold), the colliders, the pieces (their coarse and final vertex counts, the
                    object each drives), the build's bundle digest, the commit, and the measures every 6 frames (each
                    piece's new penetration share and depth, its stretch p99)
  coarse.npz        per piece (frames, coarse vertices, 3) float32 in the build's world frame: the garment's recording
                    (geom/garments.npz) with every vertex moved. The build's own finalize (Solidify, Subdivision:
                    charkit.evalmesh.finalize, equal to Blender's per round 1) makes the render mesh from it, so the
                    cache stays small and one cache serves every render resolution of the stack
  PIECE.pc2         (--pc2) the same coarse positions as a PC2 point cache for Blender's Mesh Cache modifier, first in
                    the piece's stack with its Armature modifier off: Blender's own Solidify and Subdivision then make
                    the render mesh (the replay check: charkit.sim.bake.blender_check)
The skeleton's per-frame matrices are in coarse.npz too ('bones/NAME'), so a renderer poses the body the same way.
"""
import hashlib, json, os, struct, subprocess, time

import numpy as np

from . import motion as mo


# ------------------------------------------------------------------------------------------------------------ PC2
def write_pc2(path, frames, fps=mo.FPS, start=0.0):
    """frames (F, n, 3) -> a PC2 point cache (Blender's Mesh Cache modifier reads it)."""
    X = np.ascontiguousarray(np.asarray(frames, np.float32))
    F, n, _ = X.shape
    with open(path, 'wb') as f:
        f.write(b'POINTCACHE2\0' + struct.pack('<iiffi', 1, n, float(start), 1.0, F))
        f.write(X.tobytes())


def read_pc2(path):
    """-> (frames (F, n, 3) float32, start, sample rate)."""
    with open(path, 'rb') as f:
        head = f.read(32)
        if head[:12] != b'POINTCACHE2\0':
            raise ValueError('%s: not a PC2 cache' % path)
        _, n, start, rate, F = struct.unpack('<iiffi', head[12:32])
        X = np.frombuffer(f.read(), np.float32).reshape(F, n, 3)
    return X, start, rate


# ------------------------------------------------------------------------------------------------------------ the bake
def bake(build, clip='kick', out=None, method=None, pc2=False, every=6, log=print):
    """the loose garments through a clip -> the cache folder (see the module's docstring)."""
    from .. import bundle as bl
    from ..evalmesh import POSES
    from . import motionqa
    t0 = time.time()
    B = bl.load(os.path.join(build, 'bundle'))
    gm = motionqa.settings(B)
    if method:
        gm['method'] = method
    pieces = motionqa.loose_pieces(B, gm) or list(mo.PIECES)
    S = mo.Scene(build, pieces=pieces, log=log)
    M = mo.method(S, gm['method'], style=gm.get('style', 'anime'), hold_shape=gm.get('hold_shape'), log=log)
    out = out or os.path.join(build, 'cloth', clip)
    os.makedirs(out, exist_ok=True)
    fs, n0 = S.schedule(clip)
    X = {n: np.zeros((len(fs), len(S.co[n]['V']), 3), np.float32) for n in pieces}
    bones = {}
    rows = []
    for k, f in enumerate(fs):
        D = S.rig.skinning(POSES[clip], f)
        fin, co = M.frame(D, 1.0 / mo.FPS)
        for n in pieces:
            X[n][k] = co[n]
        for b, m in D.items():
            bones.setdefault(b, np.zeros((len(fs), 4, 4), np.float32))[k] = m
        if k >= n0 - 1 and ((k - n0 + 1) % every == 0 or k == len(fs) - 1):
            r = S.measure(D, fin, co)
            rows.append(dict(frame=k, **{n: {q: round(r[n][q], 5) for q in ('new_share', 'new_depth', 'stretch_p99')}
                                         for n in pieces}))
    arrays = {n: X[n] for n in pieces}
    arrays.update({'bones/' + b: m for b, m in bones.items()})
    np.savez_compressed(os.path.join(out, 'coarse.npz'), **arrays)
    if pc2:
        for n in pieces:
            write_pc2(os.path.join(out, n + '.pc2'), X[n], fps=mo.FPS)
    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=os.path.dirname(os.path.abspath(__file__)),
                          capture_output=True, text=True).stdout.strip()
    man = dict(clip=clip, fps=mo.FPS, frames=len(fs), first=n0, settle_s=mo.SETTLE, ramp_s=mo.RAMP, hold_s=mo.HOLD,
               method=gm['method'], style=gm.get('style'), hold_shape=gm.get('hold_shape'),
               cloth=dict(mo.CLOTH) if gm['method'].startswith('xpbd') else None,
               colliders=[dict(name=c['name'], bone=c['bone'], r_L=round(c['r'] / S.L, 4)) for c in
                          getattr(M, 'caps', [])],
               pieces={n: dict(coarse=int(len(S.co[n]['V'])), final=int(len(S.fin[n]['V'])), object=n,
                               pc2=(n + '.pc2') if pc2 else None) for n in pieces},
               bundle=B.meta('content'), commit=head, L=S.L, measures=rows, seconds=round(time.time() - t0, 1),
               digest=hashlib.sha256(b''.join(X[n].tobytes() for n in pieces)).hexdigest()[:16])
    json.dump(man, open(os.path.join(out, 'cloth.json'), 'w'), indent=1)
    log('bake %s %s: %d frames, %s; %.1f s -> %s' % (clip, gm['method'], len(fs), ', '.join(
        '%s %d' % (n, len(S.co[n]['V'])) for n in pieces), time.time() - t0, out))
    return out


def load(cache):
    """a cache folder -> (manifest, {piece: (F, n, 3)}, {bone: (F, 4, 4)})."""
    man = json.load(open(os.path.join(cache, 'cloth.json')))
    Z = np.load(os.path.join(cache, 'coarse.npz'))
    return man, {n: Z[n] for n in man['pieces']}, {k[6:]: Z[k] for k in Z.files if k.startswith('bones/')}


def finals(build, cache, frames):
    """the render meshes (the build's own finalize) of a cache's pieces at frames -> {frame: {piece: V}}."""
    from . import drape
    man, X, _ = load(cache)
    Bd = drape.Build(build)
    return {k: {n: Bd.final(n, X[n][k].astype(float))['V'] for n in man['pieces']} for k in frames}


# ------------------------------------------------------------------------------------------------ the replay check
BLENDER_CHECK = r'''
import bpy, json, sys, numpy as np
args = json.loads(sys.argv[sys.argv.index('--') + 1])
out = {}
sc = bpy.context.scene
for n, p in args['pc2'].items():
    ob = bpy.data.objects.get(n)
    if ob is None:
        out[n] = 'missing'
        continue
    for m in ob.modifiers:
        if m.type == 'ARMATURE':
            m.show_viewport = m.show_render = False
    mc = ob.modifiers.new('cloth_cache', 'MESH_CACHE')
    mc.cache_format = 'PC2'
    mc.filepath = p
    mc.frame_start = 0
    mc.deform_mode = 'OVERWRITE'
    mc.forward_axis, mc.up_axis = 'POS_Y', 'POS_Z'
    with bpy.context.temp_override(object=ob):
        bpy.ops.object.modifier_move_to_index(modifier=mc.name, index=0)
    out[n] = {}
    for f in args['frames']:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = ob.evaluated_get(dg).to_mesh()
        V = np.array([ob.matrix_world @ v.co for v in me.vertices])
        np.save(args['out'] + '/%s_%d.npy' % (n, f), V)
        out[n][f] = len(V)
json.dump(out, open(args['out'] + '/blender.json', 'w'))
'''


def blender_check(build, cache, frames=(0, 70, 95), blender=None, blend=None, log=print):
    """Blender's Mesh Cache modifier replaying the PC2 caches first in each piece's stack (its Armature off) against
    our finalize of the same frames -> {piece: {frame: max |d| (L)}} (cache/replay.json)."""
    import tempfile
    blender = blender or os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
    man, X, _ = load(cache)
    blend = blend or os.path.join(build, 'clawd.blend')
    w = tempfile.mkdtemp(prefix='cloth_replay_')
    open(os.path.join(w, 'check.py'), 'w').write(BLENDER_CHECK)
    arg = json.dumps(dict(pc2={n: os.path.abspath(os.path.join(cache, n + '.pc2')) for n in man['pieces']},
                          frames=list(frames), out=w))
    r = subprocess.run([blender, '-b', blend, '--python', os.path.join(w, 'check.py'), '--', arg],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(os.path.join(w, 'blender.json')):
        raise RuntimeError('blender replay failed:\n' + (r.stdout + r.stderr)[-2000:])
    ours = finals(build, cache, frames)
    rep = {}
    for n in man['pieces']:
        rep[n] = {}
        for f in frames:
            p = os.path.join(w, '%s_%d.npy' % (n, f))
            if not os.path.exists(p):
                rep[n][f] = None
                continue
            Vb = np.load(p)
            Vo = ours[f][n]
            rep[n][f] = float(np.abs(Vb - Vo).max() / man['L']) if Vb.shape == Vo.shape else 'shape %s vs %s' % (
                Vb.shape, Vo.shape)
    json.dump(rep, open(os.path.join(cache, 'replay.json'), 'w'), indent=1)
    log('replay: %s' % json.dumps(rep))
    return rep


def main(a):
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    out = bake(a[0], clip=opt('--clip', 'kick'), out=opt('--out'), method=opt('--method'), pc2='--pc2' in a)
    if '--replay' in a:
        blender_check(a[0], out, blender=opt('--blender'))
    return 0
