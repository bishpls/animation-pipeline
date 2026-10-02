"""The motion video check (tool/motionvid; Michael, 2026-10-02: "a basic motion video check showing the animations we're
testing on-rig"): the build's exported rig (charkit.rom.Rig: NAME.look.glb's VRM humanoid skeleton and skin weights)
animated through the test poses and drawn by charkit's toon renderer, as a video and a contact sheet. Report-only: it
reads a build and writes nothing into it but its own folder.

    python -m charkit rom video BUILD [--out DIR] [--poses a,b] [--clips rom,motionqa] [--views 0,35,90]
                                      [--res 640x800] [--fps 24] [--timing 1,0.5,1] [--export PATH] [--frames] [--ss 2]
                                      [--rom ROM.json] [--no-page]
        -> DIR/rom_video.mp4 (H.264, yuv420p, 24 fps: plays in a browser), DIR/contact.png (each clip at its hold, every
           view), DIR/video.json (the clips and their frames, the rig features honoured, seconds per frame),
           DIR/page/index.html (the review page, charkit.reviewpage, from DIR/page.json: the video with a chapter per
           clip, the contact sheet, the clips with the ROM suite's FAILs for the pose when BUILD/rom/rom.json or --rom
           has them); with --frames (or with no ffmpeg on the machine) DIR/frames/NNNNN.jpg as well
    python -m charkit rom video encode DIR      the frames in DIR/frames encoded into DIR/rom_video.mp4 (wherever ffmpeg is)
    python -m charkit rom video page DIR [--rom ROM.json]     the review page again from DIR/video.json
DIR defaults to BUILD/rom/video. --poses names the clips (the library's poses; mqa_kick etc. motion QA's).

The clips: every pose of the pose library (charkit/poses/rom.json, charkit.pose; `rest` is every clip's end), then the
motion QA's test clips (charkit.evalmesh.POSES: the kick, squat, split... the cloth's test poses). Each runs rest -> pose
-> rest: TIMING seconds in (eased: smoothstep), held, out. A clip's key is each humanoid bone's local rotation (its
parent's frame; the VRM rest frames are the world's, so these are what a runtime's animation clip carries), read off the
pose's solve (charkit.pose.solve, through rom.Rig.solve: the extra nodes' constraints and the clavicle's rhythm when the
codebase has them); a frame's rotations are slerped from the identity by the eased weight and composed down the
hierarchy (compose), the export's constrained extra nodes then evaluated (rom.Rig.nodes, when present), and the skin
skinned as a runtime skins it (linear blend, the export's four weights: rom.Rig.matrices).

The pictures: the ROM boards' views (rom.board_views: orthographic, one scale for every pose, 1.45 x the height on the
picture's height) at VIEWS (front, three-quarter, profile), side by side, each frame labelled with the clip's index, name,
group and phase. Like a runtime (engine/three/charkit/look.js), the face's SDF shading and the baked cast shadows' lookup
read the key light in the posed head's frame; like the ROM boards, the baked cast shadows are off (they belong to the
rest pose) and the outlined objects' normals are recomputed on the posed surface (charkit.render.normals). Identical
poses render once (a clip's out is its in reversed; the hold one picture; every clip's rest the same).
"""
import copy, json, os, shutil, subprocess, sys, time

import numpy as np

from . import pose as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
C3 = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])       # Blender -> glTF (charkit.render.model.C3)
FPS = 24
TIMING = (1.0, 0.5, 1.0)        # s: rest -> pose, held, pose -> rest
VIEWS = (0, 35, 90)             # the boards' azimuths drawn side by side: front, three-quarter, profile
VIEW_NAMES = {0: 'front', 35: 'three-quarter', 90: 'profile', 180: 'back'}
RES = (640, 800)                # px per view: the ROM boards' (rom.BOARD_RES)
BAR = 96                        # px: the label bar over the views
SHEET_SCALE = 0.4               # the contact sheet's views at this share of the video's
SHEET_COLS = 4
ENCODERS = (                    # tried in order (the first that encodes a test clip here): hardware or permissive first
    ('h264_nvenc', ['-preset', 'p5', '-rc', 'vbr', '-cq', '21', '-b:v', '0', '-profile:v', 'high']),
    ('h264_videotoolbox', ['-b:v', '8M', '-profile:v', 'high']),
    ('libopenh264', ['-b:v', '8M']),
    ('libx264', ['-crf', '20', '-preset', 'medium', '-profile:v', 'high']),
)
COLOUR = ['-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709']


# --------------------------------------------------------------------------------------------- rotations and slerp
def quat(R):
    """rotation matrices (..., 3, 3) -> unit quaternions (..., 4) as (w, x, y, z), w >= 0 (Shepperd's method)."""
    R = np.asarray(R, float)
    sh = R.shape[:-2]
    R = R.reshape(-1, 3, 3)
    q = np.zeros((len(R), 4))
    tr = np.trace(R, axis1=1, axis2=2)
    d = np.stack([R[:, 0, 0], R[:, 1, 1], R[:, 2, 2]], 1)
    for i, M in enumerate(R):
        if tr[i] > 0:
            s = 2.0 * np.sqrt(1.0 + tr[i])
            q[i] = (0.25 * s, (M[2, 1] - M[1, 2]) / s, (M[0, 2] - M[2, 0]) / s, (M[1, 0] - M[0, 1]) / s)
        else:
            k = int(np.argmax(d[i]))
            a, b = (k + 1) % 3, (k + 2) % 3
            s = 2.0 * np.sqrt(max(1e-300, 1.0 + M[k, k] - M[a, a] - M[b, b]))
            v = np.zeros(3)
            v[k] = 0.25 * s
            v[a] = (M[a, k] + M[k, a]) / s
            v[b] = (M[b, k] + M[k, b]) / s
            q[i] = ((M[b, a] - M[a, b]) / s, *v)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    q[q[:, 0] < 0] *= -1
    return q.reshape(*sh, 4)


def matrix(q):
    """unit quaternions (..., 4) (w, x, y, z) -> rotation matrices (..., 3, 3)."""
    q = np.asarray(q, float)
    q = q / np.linalg.norm(q, axis=-1, keepdims=True)
    w, x, y, z = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def slerp(q0, q1, s):
    """spherical linear interpolation from unit quaternion q0 to q1 (..., 4) by s (scalar or (...)), the shorter way
    round (q and -q are the same rotation) -> (..., 4)."""
    q0, q1 = np.asarray(q0, float), np.asarray(q1, float)
    s = np.asarray(s, float)[..., None] if np.ndim(s) else float(s)
    d = np.sum(q0 * q1, -1, keepdims=True)
    q1 = np.where(d < 0, -q1, q1)
    d = np.abs(d)
    th = np.arccos(np.clip(d, -1.0, 1.0))
    sn = np.sin(th)
    near = sn < 1e-8                                 # (the same rotation: linear, renormalised)
    a = np.where(near, 1.0 - s, np.sin((1.0 - s) * th) / np.where(near, 1.0, sn))
    b = np.where(near, s, np.sin(s * th) / np.where(near, 1.0, sn))
    q = a * q0 + b * q1
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def ease(u):
    """smoothstep: 0 at 0, 1 at 1, flat at both ends (the motion QA's ramp, charkit.sim.rig.smoothstep)."""
    u = np.clip(np.asarray(u, float), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


# ------------------------------------------------------------------------------------------------- poses as keys
def local_rotations(sk, D):
    """{bone: 4x4 world deformation} (charkit.pose.solve) -> {bone: 3x3 local rotation}: each humanoid bone's rotation
    in its parent's frame about its own head (D_b = D_parent . T(h) L_b T(-h), the rest frames the world's); bones D
    leaves out or doesn't turn are left out."""
    L = {}
    for b in sk.order:
        if b not in D:
            continue
        p = sk.parent.get(b)
        Rp = D[p][:3, :3] if p in D else np.eye(3)
        R = Rp.T @ D[b][:3, :3]
        if np.abs(R - np.eye(3)).max() > 1e-12:
            L[b] = R
    return L


def compose(sk, L):
    """{bone: 3x3 local rotation} -> {bone: 4x4 world deformation} over every bone of sk (rest -> posed), as
    charkit.pose.solve composes: each bone turned about its head where its parent has carried it."""
    D = {}
    for b in sk.order:
        p = sk.parent.get(b)
        M = np.eye(4)
        if b in L:
            h = sk.head[b]
            M[:3, :3] = L[b]
            M[:3, 3] = h - L[b] @ h
        D[b] = D[p] @ M if p in D else M
    return D


class Key:
    """a clip's key pose as local rotations: bones (names), q (n, 4) their quaternions."""

    def __init__(self, L):
        self.bones = list(L)
        self.q = quat(np.array([L[b] for b in self.bones])) if L else np.zeros((0, 4))

    def at(self, w):
        """the key taken w of the way from the rest (slerp from the identity) -> {bone: 3x3}."""
        if not self.bones:
            return {}
        I = np.zeros_like(self.q)
        I[:, 0] = 1.0
        R = matrix(slerp(I, self.q, w))
        return dict(zip(self.bones, R))


def schedule(timing=TIMING, fps=FPS):
    """a clip's frames -> [(phase, w)]: in (w = ease(k / n_in), k = 0 .. n_in - 1: the rest first), held (w = 1), out
    (w = ease((n_out - 1 - k) / n_out): the in's weights reversed, the rest last)."""
    n_in, n_hold, n_out = (int(round(t * fps)) for t in timing)
    fr = [('in', float(ease(k / n_in))) for k in range(n_in)] + [('hold', 1.0)] * n_hold
    fr += [('out', float(ease((n_out - 1 - k) / n_out))) for k in range(n_out)]
    return fr


# ------------------------------------------------------------------------------------------------------- the clips
def rom_clips(rig, lib=None, names=None):
    """the pose library's poses (but rest) as clips -> [dict(name, group, what, source, key)]."""
    lib = lib or P.library()
    out = []
    for n in (list(lib) if names is None else names):
        if n not in lib or n == 'rest' or not (lib[n].get('bones') or {}):
            continue
        D = rig.solve(lib[n])
        out.append(dict(name=n, group=lib[n].get('group') or '', what=lib[n].get('what') or '',
                        source='rom.json', key=Key(local_rotations(rig.sk, D))))
    return out


def motionqa_clips(rig, names=None):
    """motion QA's test poses (charkit.evalmesh.POSES: per bone (axis, degrees) about its head in the rest frame,
    composed down the chain: local rotations as they stand) as clips."""
    try:
        from .evalmesh import POSES
    except Exception:                               # (a codebase without them)
        return []
    axes = {'X': (1.0, 0, 0), 'Y': (0, 1.0, 0), 'Z': (0, 0, 1.0)}
    out = []
    for n, pose in POSES.items():
        if names is not None and n not in names and 'mqa_' + n not in names:
            continue
        L = {b: P.rotation(axes[ax], deg) for b, (ax, deg) in pose.items() if b in rig.sk.head}
        if not L:
            continue
        what = ', '.join('%s %+g deg about %s' % (b, deg, ax) for b, (ax, deg) in pose.items())
        out.append(dict(name='mqa_' + n, group='motion QA', what='motion QA clip %s (charkit.evalmesh.POSES; the cloth '
                        'is not solved here: the garments follow their weights): %s' % (n, what),
                        source='evalmesh.POSES', key=Key(L)))
    return out


def deform(rig, L):
    """local rotations -> the frame's deformations: composed down the humanoid, then the export's constrained extra
    nodes evaluated (rom.Rig.nodes: present when the codebase evaluates VRMC_node_constraint and the export has them)."""
    D = compose(rig.sk, L)
    nodes = getattr(rig, 'nodes', None)
    return nodes.deform(D) if nodes is not None else D


# ----------------------------------------------------------------------------------------------------- the skinning
def _unit(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.maximum(n, 1e-12)


class Skinner:
    """the export's drawn primitives skinned per frame as rom.Rig.model_posed skins them (linear blend over the four
    weights, normalised; positions, normals and hull normals; the baked cast shadows dropped), float32."""

    def __init__(self, rig):
        self.rig = rig
        self.rows = []
        for i, p in enumerate(rig.M.prims):
            J, W = rig.attrs[i]
            if J is None or p.variant:                # (a variant isn't drawn: rom.Rig.model_posed skins it, unseen)
                continue
            Wn = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
            self.rows.append((i, np.ascontiguousarray(J, np.int64), Wn.astype(np.float32), p))

    def rest(self):
        """the export's prims with the skinned ones' cast shadows off: the renderer's first model."""
        prims = list(self.rig.M.prims)
        for i, _, _, p in self.rows:
            q = copy.copy(p)
            q.cast = None
            prims[i] = q
        M = copy.copy(self.rig.M)
        M.prims = prims
        return M

    def prims(self, D):
        """{bone: 4x4} -> {prim index: posed Prim} for the skinned, drawn prims."""
        R, t = self.rig.matrices(D)
        Rg = np.einsum('ij,njk,lk->nil', C3, R, C3).astype(np.float32)
        tg = (t @ C3.T).astype(np.float32)
        out = {}
        for i, J, W, p in self.rows:
            Lm = np.zeros((len(J), 3, 3), np.float32)
            T = np.zeros((len(J), 3), np.float32)
            for k in range(J.shape[1]):
                w = W[:, k]
                if not w.any():
                    continue
                Lm += w[:, None, None] * Rg[J[:, k]]
                T += w[:, None] * tg[J[:, k]]
            q = copy.copy(p)
            q.position = (np.einsum('nij,nj->ni', Lm, p.position) + T).astype(np.float32)
            q.normal = _unit(np.einsum('nij,nj->ni', Lm, p.normal)).astype(np.float32)
            if p.hull_normal is not None:
                q.hull_normal = _unit(np.einsum('nij,nj->ni', Lm, p.hull_normal)).astype(np.float32)
            q.cast = None
            out[i] = q
        return out


def posed_renderer(M, adapter=None, ss=2):
    """charkit's toon renderer (charkit.render.gpu.Renderer) that takes a new pose per frame: its vertex streams
    rewritten (set_pose) instead of the character uploaded again, the outlined objects' normals recomputed on the posed
    surface, and the head-space light (the face's SDF, the cast shadows' lookup) read in the posed head's frame."""
    from .render import gpu

    class PosedRenderer(gpu.Renderer):
        def __init__(self, M, **kw):
            super().__init__(M, **kw)
            wgpu = self.wgpu
            use = wgpu.BufferUsage.VERTEX | wgpu.BufferUsage.COPY_DST
            for it in self.items:                     # (the streams writable: _upload makes them VERTEX only)
                V, _ = gpu.vertex_array(it['P'])
                it['vb'] = self.dev.create_buffer_with_data(data=V.tobytes(), usage=use)
            self.groups = [g for g in self.groups if not g['items'][0]['variant']]      # (never drawn)
            self.head_R = np.eye(3)

        def set_pose(self, posed, head_R=None):
            """posed: {item index: posed Prim}; head_R: the head bone's posed rotation (glTF frame)."""
            for i, q in posed.items():
                it = self.items[i]
                V, Nn = gpu.vertex_array(q)
                self.dev.queue.write_buffer(it['vb'], 0, V.tobytes())
                self.dev.queue.write_buffer(it['nb'], 0, Nn.tobytes())
                it['P'] = q
                it['centre'] = q.position.mean(0)
            for g in self.groups:
                G = g['G']
                ps = [it['P'] for it in g['items']]
                G.prims = ps
                G.co = np.concatenate([p.co().astype(np.float32) for p in ps])
                G.hull = np.concatenate([p.hull_dir() for p in ps]).astype(np.float64)
                G._cache = {}
                g['w'] = None
            self.head_R = np.eye(3) if head_R is None else np.asarray(head_R, float)

        def view_uniform(self, v, cam):
            u, light, line = super().view_uniform(v, cam)
            u[28:31] = self.head_R.T @ np.asarray(light, float)     # (look.js: the light in the posed head's frame)
            return u, light, line

    return PosedRenderer(M, adapter=adapter or os.environ.get('CHARKIT_RENDER_ADAPTER'), ss=ss)


# --------------------------------------------------------------------------------------------------- the rig's features
def rig_features(rig):
    """what the export carries that a runtime plays, and which of it this video honours -> [dict(feature, carried,
    honoured, how)]."""
    js = rig.M.js
    sk = js['skins'][0]
    nodes = js['nodes']
    ext = lambda n: (n.get('extensions') or {})
    from .mh import VRM_PARENT
    hum = set(VRM_PARENT)
    joints = [nodes[j].get('name') for j in sk['joints']]
    extra = [n for n in joints if n not in hum]
    cons = [nodes[j].get('name') for j in sk['joints'] if ext(nodes[j]).get('VRMC_node_constraint')]
    kinds = {}
    for j in sk['joints']:
        c = (ext(nodes[j]).get('VRMC_node_constraint') or {}).get('constraint') or {}
        for k in c:
            kinds[k] = kinds.get(k, 0) + 1
    evaluated = getattr(rig, 'nodes', None) is not None
    spring = (js.get('extensions') or {}).get('VRMC_springBone')
    morphs = sum(len(pr.get('targets') or ()) for m in js['meshes'] for pr in m['primitives'])
    infl = max((a[0].shape[1] for a in rig.attrs if a[0] is not None), default=0)
    out = [
        dict(feature='skeleton', carried='%d skin joints: %d humanoid, %d extra' % (len(joints), len(joints) - len(extra),
                                                                                  len(extra)),
             honoured=True, how='posed by local rotations slerped from the rest, composed down the hierarchy'),
        dict(feature='skinning', carried='linear blend, %d influences a vertex' % infl, honoured=True,
             how='linear blend skinning of positions, normals and hull normals (rom.Rig.matrices), as a runtime skins'),
        dict(feature='VRMC_node_constraint', carried=('%d nodes (%s)' % (len(cons), ', '.join(
            '%s %d' % kv for kv in sorted(kinds.items())))) if cons else 'none',
             honoured=bool(cons) and evaluated,
             how=('evaluated each frame (rom.Rig.nodes.deform)' if evaluated else
                  'not evaluated by this codebase: each constrained node moves as its nearest humanoid ancestor')
             if cons else 'nothing to evaluate'),
        dict(feature='VRMC_springBone', carried='present' if spring else 'none', honoured=False,
             how='no secondary dynamics: spring chains move rigidly with their skinned parents' if spring else
             'nothing to simulate'),
        dict(feature='morph targets (expressions)', carried='%d' % morphs if morphs else 'none (the look export)',
             honoured=False, how='the rest face throughout'),
        dict(feature='head-space light', carried='look extension (face SDF, cast lookup)', honoured=True,
             how='the key light read in the posed head\'s frame, as engine/three/charkit/look.js does'),
        dict(feature='baked cast shadows', carried='rest pose only', honoured=False,
             how='off, as on the ROM boards (they belong to the rest pose)'),
        dict(feature='cloth (motion QA)', carried='a build-side solve, not in the export', honoured=False,
             how='the garments follow their own skin weights'),
    ]
    return out


# ----------------------------------------------------------------------------------------------------- the pictures
def _font(size):
    from PIL import ImageFont
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf',
              '/Library/Fonts/Arial.ttf'):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                                    # (Pillow < 10.1)
        return ImageFont.load_default()


def compose_frame(imgs, clip, n_clips, phase, w, t, k, nk, fonts, bg=(24, 24, 28), views=VIEWS):
    """the views side by side under a label bar: the clip's index and name, its group and phase, the pose's weight, a
    progress bar over the clip -> (H, W, 3) uint8."""
    from PIL import Image, ImageDraw
    h, wv = imgs[0].shape[:2]
    W, H = wv * len(imgs), h + BAR
    im = Image.new('RGB', (W, H), bg)
    for j, a in enumerate(imgs):
        im.paste(Image.fromarray(a), (j * wv, BAR))
    d = ImageDraw.Draw(im)
    big, small = fonts
    d.text((16, 10), '%02d/%02d  %s' % (clip['index'], n_clips, clip['name']), fill=(245, 245, 245), font=big)
    ph = {'in': 'rest -> pose', 'hold': 'hold', 'out': 'pose -> rest'}[phase]
    right = '%s   %s   w %.2f   t %.2f s' % (clip['group'], ph, w, t)
    tw = d.textlength(right, font=small)
    d.text((W - tw - 16, 16), right, fill=(200, 200, 205), font=small)
    what = clip['what']
    while what and d.textlength(what, font=small) > W - 32:
        what = what[:-2]
    if what != clip['what']:
        what = what[:-1] + '...'
    d.text((16, 52), what, fill=(170, 170, 178), font=small)
    y = BAR - 6                                          # the clip's progress: in, hold, out
    d.rectangle((0, y, W, BAR - 1), fill=(48, 48, 54))
    d.rectangle((0, y, int(W * (k + 1) / nk), BAR - 1), fill=(90, 150, 230) if phase != 'hold' else (230, 170, 60))
    for j, az in enumerate(views):
        lab = '%s %d deg' % (VIEW_NAMES.get(az, 'az'), az)
        d.text((j * wv + 10, H - 30), lab, fill=(60, 60, 66), font=small)
    return np.asarray(im)


def contact_sheet(holds, path, n_clips, views=VIEWS, scale=SHEET_SCALE, cols=SHEET_COLS, bg=(24, 24, 28)):
    """each clip at its hold, every view, in a grid -> path."""
    from PIL import Image, ImageDraw
    if not holds:
        return None
    h0, w0 = holds[0][1][0].shape[:2]
    vw, vh = int(w0 * scale), int(h0 * scale)
    lab = 34
    tw, th = vw * len(views), vh + lab
    rows = (len(holds) + cols - 1) // cols
    im = Image.new('RGB', (tw * cols + 8 * (cols - 1), th * rows + 8 * (rows - 1)), bg)
    d = ImageDraw.Draw(im)
    f = _font(18)
    for n, (clip, imgs) in enumerate(holds):
        x, y = (n % cols) * (tw + 8), (n // cols) * (th + 8)
        for j, a in enumerate(imgs):
            im.paste(Image.fromarray(a).resize((vw, vh), Image.LANCZOS), (x + j * vw, y + lab))
        d.text((x + 6, y + 6), '%02d/%02d  %s  (%s)' % (clip['index'], n_clips, clip['name'], clip['group']),
               fill=(240, 240, 240), font=f)
    im.save(path, optimize=True)
    return path


# ------------------------------------------------------------------------------------------------------- encoding
def encoder(ffmpeg, log=print):
    """the first of ENCODERS that encodes a small yuv420p test clip with this ffmpeg -> (name, args) or None."""
    import tempfile
    d = tempfile.mkdtemp(prefix='romvideo_')
    try:
        for name, args in ENCODERS:
            p = os.path.join(d, 'probe.mp4')
            cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
                   '256x144', '-r', str(FPS), '-i', '-', '-c:v', name, *args, '-pix_fmt', 'yuv420p', p]
            r = subprocess.run(cmd, input=np.zeros((4, 144, 256, 3), np.uint8).tobytes(), capture_output=True)
            if r.returncode == 0 and os.path.getsize(p) > 0:
                return name, args
            log('rom video: encoder %s unavailable here (%s)' % (name, (r.stderr or b'').decode()[-200:].strip()))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return None


class Encoder:
    """frames piped into ffmpeg as raw RGB -> H.264 mp4, yuv420p, BT.709, faststart (a browser plays it)."""

    def __init__(self, path, size, fps=FPS, log=print):
        self.path, self.proc, self.name = path, None, None
        ff = shutil.which('ffmpeg')
        enc = encoder(ff, log) if ff else None
        if not enc:
            return
        self.name, args = enc
        W, H = size
        cmd = [ff, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
               '-r', str(fps), '-i', '-', '-vf', 'scale=out_color_matrix=bt709:out_range=tv', '-c:v', self.name, *args,
               '-pix_fmt', 'yuv420p', *COLOUR, '-movflags', '+faststart', path]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.seconds = 0.0

    def write(self, a):
        if self.proc:
            t = time.time()
            self.proc.stdin.write(np.ascontiguousarray(a, np.uint8).tobytes())
            self.seconds += time.time() - t

    def close(self):
        if not self.proc:
            return None
        t = time.time()
        self.proc.stdin.close()
        rc = self.proc.wait()
        self.seconds += time.time() - t
        return rc


def encode_frames(d, fps=FPS, log=print):
    """DIR/frames/*.jpg -> DIR/rom_video.mp4 (`rom video encode DIR`: the frames rendered where there was no ffmpeg)."""
    from PIL import Image
    fs = sorted(f for f in os.listdir(os.path.join(d, 'frames')) if f.endswith(('.jpg', '.png')))
    if not fs:
        raise SystemExit('rom video encode: no frames in %s/frames' % d)
    a = np.asarray(Image.open(os.path.join(d, 'frames', fs[0])).convert('RGB'))
    out = os.path.join(d, 'rom_video.mp4')
    E = Encoder(out, (a.shape[1], a.shape[0]), fps, log)
    if not E.proc:
        raise SystemExit('rom video encode: no ffmpeg with an H.264 encoder here')
    for f in fs:
        E.write(np.asarray(Image.open(os.path.join(d, 'frames', f)).convert('RGB')))
    rc = E.close()
    js = os.path.join(d, 'video.json')
    if os.path.exists(js):
        rep = json.load(open(js))
        rep['video'], rep['encoder'], rep['encode_s'] = os.path.basename(out), E.name, round(E.seconds, 1)
        json.dump(rep, open(js, 'w'), indent=1)
    log('rom video encode: %s (%s, exit %d)' % (out, E.name, rc))
    return out


# ------------------------------------------------------------------------------------------------------------ the run
def run(build, out=None, poses=None, clips=('rom', 'motionqa'), views=VIEWS, res=RES, fps=FPS, timing=TIMING,
        export=None, frames=False, ss=2, adapter=None, log=print):
    """the video, the contact sheet and video.json for a build -> the report (video.json's dict)."""
    from . import rom
    from PIL import Image
    t0, c0 = time.time(), time.process_time()
    out = out or os.path.join(build, 'rom', 'video')
    os.makedirs(out, exist_ok=True)
    rig, _ = rom.load(build, export)
    t_rig = time.time() - t0
    lib = P.library()
    C = []
    if 'rom' in clips:
        C += rom_clips(rig, lib, [n for n in poses if n in lib] if poses else None)
    if 'motionqa' in clips:
        C += motionqa_clips(rig, [n for n in poses if n not in lib] if poses else None)
    if not C:
        raise SystemExit('rom video: no clips (poses %s, clips %s)' % (poses, clips))
    for i, c in enumerate(C):
        c['index'] = i + 1
    sch = schedule(timing, fps)
    t1 = time.time()
    sk = Skinner(rig)
    R = posed_renderer(sk.rest(), adapter, ss)
    V = rom.board_views(rig, tuple(views), tuple(res))
    t_setup = time.time() - t1
    W, H = res[0] * len(views), res[1] + BAR
    vid = os.path.join(out, 'rom_video.mp4')
    E = None if frames == 'only' else Encoder(vid, (W, H), fps, log)
    keep_frames = bool(frames) or E is None or E.proc is None
    if keep_frames:
        fdir = os.path.join(out, 'frames')
        shutil.rmtree(fdir, ignore_errors=True)
        os.makedirs(fdir)
    fonts = (_font(30), _font(19))
    tm = dict(pose=0.0, skin=0.0, upload=0.0, render=0.0, label=0.0, write=0.0)
    cache_rest = None
    renders, nframe, holds, rows = 0, 0, [], []

    def draw(L, w):
        nonlocal renders
        ta = time.time()
        D = deform(rig, L)
        Rh = D.get('head', np.eye(4))[:3, :3]
        tb = time.time()
        posed = sk.prims(D)
        tc = time.time()
        R.set_pose(posed, C3 @ Rh @ C3.T)
        td = time.time()
        imgs = [R.render(v) for v in V]
        te = time.time()
        tm['pose'] += tb - ta
        tm['skin'] += tc - tb
        tm['upload'] += td - tc
        tm['render'] += te - td
        renders += 1
        return imgs

    for c in C:
        tc0 = time.time()
        cache = {}
        start = nframe
        for k, (phase, w) in enumerate(sch):
            key = round(w, 9)
            if key == 0.0:
                if cache_rest is None:
                    cache_rest = draw({}, 0.0)
                imgs = cache_rest
            elif key in cache:
                imgs = cache[key]
            else:
                imgs = cache[key] = draw(c['key'].at(w), w)
            if phase == 'hold' and not any(h[0] is c for h in holds):
                holds.append((c, imgs))
            t = time.time()
            fr = compose_frame(imgs, c, len(C), phase, w, k / fps, k, len(sch), fonts, views=views)
            tm['label'] += time.time() - t
            t = time.time()
            if E is not None and E.proc:
                E.write(fr)
            if keep_frames:
                Image.fromarray(fr).save(os.path.join(fdir, '%05d.jpg' % nframe), quality=92)
            tm['write'] += time.time() - t
            nframe += 1
        rows.append(dict(index=c['index'], name=c['name'], group=c['group'], what=c['what'], source=c['source'],
                         bones=len(c['key'].bones), start_frame=start, frames=nframe - start,
                         start_s=round(start / fps, 3), hold_s=round((start + int(round(timing[0] * fps))) / fps, 3),
                         seconds=round(time.time() - tc0, 1)))
        log('rom video %02d/%02d %-20s %d frames, %.1f s' % (c['index'], len(C), c['name'], nframe - start,
                                                            time.time() - tc0))
    rc = E.close() if E is not None else None
    sheet = contact_sheet(holds, os.path.join(out, 'contact.png'), len(C), views)
    wall = time.time() - t0
    loop = wall - t_rig - t_setup
    rep = dict(build=os.path.abspath(build), export=os.path.basename(rig.path), out=os.path.abspath(out),
               video=os.path.basename(vid) if (E is not None and E.proc and rc == 0) else None,
               encoder=E.name if E is not None else None, contact=os.path.basename(sheet) if sheet else None,
               frames_dir='frames' if keep_frames else None, fps=fps, timing_s=list(timing), views=list(views),
               res=[W, H], view_res=list(res), ss=ss, frames=nframe, duration_s=round(nframe / fps, 2),
               renders=renders, adapter=R.info, clips=rows, features=rig_features(rig),
               seconds=dict(wall=round(wall, 1), cpu=round(time.process_time() - c0, 1), rig=round(t_rig, 1),
                            setup=round(t_setup, 1), encode=round(E.seconds, 1) if E is not None and E.proc else None,
                            **{k: round(v, 1) for k, v in tm.items()}),
               per_frame_s=round(loop / max(nframe, 1), 4), per_render_s=round(
                   (tm['pose'] + tm['skin'] + tm['upload'] + tm['render']) / max(renders, 1), 4),
               vertices=int(sum(len(p.position) for _, _, _, p in sk.rows)))
    json.dump(rep, open(os.path.join(out, 'video.json'), 'w'), indent=1, default=rom._js)
    log('rom video: %d clips, %d frames (%.1f s), %d renders; %.3f s a frame (%.3f s a render); %s' % (
        len(C), nframe, nframe / fps, renders, rep['per_frame_s'], rep['per_render_s'],
        os.path.join(out, rep['video'] or 'frames/')))
    return rep


# ------------------------------------------------------------------------------------------------------- the page
def rom_grades(build, rom_json=None):
    """the ROM suite's grades per pose when the build has its report (BUILD/rom/rom.json, or rom_json) -> {pose: (FAILs,
    WARNs)} or {}."""
    p = rom_json or os.path.join(build, 'rom', 'rom.json')
    try:
        R = json.load(open(p))
    except (OSError, ValueError):
        return {}
    out = {}
    for n, r in (R.get('poses') or {}).items():
        g = r.get('grades') or {}
        out[n] = (sorted(k for k, v in g.items() if v == 'FAIL'), sorted(k for k, v in g.items() if v == 'WARN'))
    return out


def page(rep, rom_json=None, log=print):
    """the review page (charkit.reviewpage, `review page`): the summary box, the video with a chapter per clip, the
    contact sheet, the clips and the rig's features -> (page.json, index.html)."""
    from . import reviewpage
    out = rep['out']
    G = rom_grades(rep['build'], rom_json)
    hon = [f['feature'] for f in rep['features'] if f['honoured']]
    off = [f['feature'] for f in rep['features'] if not f['honoured'] and f['carried'] not in ('none',)]
    name = os.path.basename(rep['build'].rstrip('/'))
    spec = dict(
        title='Motion video check: %s' % name,
        summary=dict(
            recommended='Watch the video for the joints the ROM suite flags (its FAILs are listed per clip below): this '
                        'is the shipped rig (%s) posed as a runtime poses it, %d clips rest -> pose -> rest, %.0f s at '
                        '%d fps. Honoured: %s. Not honoured: %s.' % (
                            rep['export'], len(rep['clips']), rep['duration_s'], rep['fps'], ', '.join(hon),
                            ', '.join(off) or 'nothing the export carries'),
            asked=['nothing: informational (a basic motion check; the clips are the ROM poses and the motion QA '
                   'poses)'],
            numbers=dict(columns=['measure', 'value'], rows=[
                ['clips', len(rep['clips'])], ['frames', '%d (%.1f s at %d fps)' % (rep['frames'], rep['duration_s'],
                                                                                 rep['fps'])],
                ['renders (identical poses drawn once)', rep['renders']],
                ['seconds a frame (wall, after setup)', rep['per_frame_s']],
                ['seconds a render (pose, skin, upload, 3 views)', rep['per_render_s']],
                ['renderer', '%s (%s)' % ((rep.get('adapter') or {}).get('device'),
                                          (rep.get('adapter') or {}).get('backend'))],
                ['encoder', rep.get('encoder') or 'none here (frames kept)'],
                ['vertices skinned a frame', rep.get('vertices')]])),
        notes=['Build %s, export %s. Views %s at %dx%d px each, one orthographic scale for every pose (the ROM boards\' '
               '1.45 x the figure height). Timing %s s (in, hold, out), eased (smoothstep); joints slerped from the '
               'rest. Command: python -m charkit rom video %s' % (
                   rep['build'], rep['export'], ', '.join('%s %d' % (VIEW_NAMES.get(a, 'az'), a) for a in rep['views']),
                   rep['view_res'][0], rep['view_res'][1], ' / '.join('%g' % t for t in rep['timing_s']),
                   rep['build'])],
        tables=[dict(title='The rig\'s features', text='What the export carries that a runtime plays, and whether the '
                     'video honours it.', columns=['feature', 'carried', 'honoured', 'how'],
                     rows=[[f['feature'], f['carried'], ['yes', 'PASS'] if f['honoured'] else ['no', 'WARN'], f['how']]
                           for f in rep['features']]),
                dict(title='The clips', text='Start and hold times in the video; the ROM suite\'s FAIL and WARN measures '
                     'for the pose where the build has its report (BUILD/rom/rom.json).',
                     columns=['#', 'clip', 'group', 'start (s)', 'hold (s)', 'ROM FAIL', 'ROM WARN', 'what'],
                     rows=[[c['index'], c['name'], c['group'], c['start_s'], c['hold_s'],
                            [', '.join(G[c['name']][0]) or '-', 'FAIL' if G[c['name']][0] else 'PASS']
                            if c['name'] in G else '-',
                            ', '.join(G[c['name']][1]) or '-' if c['name'] in G else '-', c['what']]
                           for c in rep['clips']])],
        figures=[dict(title='Contact sheet: every clip at its hold', images=[dict(
            path=os.path.join(out, rep['contact']), caption='each clip at its hold, %s' % ', '.join(
                VIEW_NAMES.get(a, str(a)) for a in rep['views']))])] if rep.get('contact') else [],
    )
    if rep.get('video'):
        spec['videos'] = [dict(title='The video', text='%d clips, rest -> pose -> rest; a chapter per clip seeks to its '
                               'start.' % len(rep['clips']), videos=[dict(
                                   path=os.path.join(out, rep['video']), caption='%s: %s, %d fps, %dx%d' % (
                                       name, rep['encoder'], rep['fps'], rep['res'][0], rep['res'][1]),
                                   chapters=[dict(label='%02d %s' % (c['index'], c['name']), t=c['start_s'])
                                             for c in rep['clips']])])]
    pj = os.path.join(out, 'page.json')
    json.dump(spec, open(pj, 'w'), indent=1)
    idx = reviewpage.make(spec, os.path.join(out, 'page'), log=log)
    return pj, idx


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if args[0] == 'encode':
        encode_frames(args[1])
        return 0
    if args[0] == 'page':                                   # the page again from DIR/video.json
        d = args[1]
        rep = json.load(open(os.path.join(d, 'video.json')))
        rep['out'] = os.path.abspath(d)
        print(page(rep, args[args.index('--rom') + 1] if '--rom' in args else None)[1])
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = args[0]
    lst = lambda s: [x for x in s.split(',') if x] if s else None
    res = tuple(int(x) for x in opt('--res', '%dx%d' % RES).lower().split('x'))
    rep = run(build, opt('--out'), poses=lst(opt('--poses')),
              clips=tuple(lst(opt('--clips', 'rom,motionqa'))),
              views=tuple(int(x) for x in lst(opt('--views', ','.join(map(str, VIEWS))))), res=res,
              fps=int(opt('--fps', FPS)), timing=tuple(float(x) for x in lst(opt('--timing', '1,0.5,1'))),
              export=opt('--export'), frames='--frames' in args, ss=int(opt('--ss', 2)))
    if '--no-page' not in args:
        rep['page'] = page(rep, opt('--rom'))[1]
    print(json.dumps({k: rep.get(k) for k in ('out', 'video', 'contact', 'page', 'frames', 'duration_s', 'per_frame_s',
                                              'per_render_s', 'encoder')}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
