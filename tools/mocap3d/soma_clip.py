"""GEM-X output to our canonical 3D motion clip (docs/PIPELINE_3D.md §2): the SOMA 77-joint skeleton, local rotations against a
T-pose rest, a metric root and foot contacts, as <base>.clip.npz, plus the same motion as <base>.bvh for Blender's BVH importer.

Two stages. On the GPU box, inside GEM-X's venv (it needs torch and the soma package), FK the prediction on the SOMA skeleton (MHR
identity, averaged over the clip so bone lengths are fixed) into <base>.raw.npz, then convert. Anywhere with numpy + scipy,
convert a raw file again, check a clip, or write the QA for a folder of clips.
    python tools/mocap3d/soma_clip.py HPE_RESULTS.pt OUT_BASE --src CLIP.mp4 --fps 24 [--gemx /srv/work/gemx] [--cmd '...']
    .venv/bin/python tools/mocap3d/soma_clip.py OUT_BASE.raw.npz OUT_BASE        # convert again (numpy + scipy only)
    .venv/bin/python tools/mocap3d/soma_clip.py --check OUT_BASE                 # FK of the npz vs FK of the BVH read back, + QA
    .venv/bin/python tools/mocap3d/soma_clip.py --qa DIR [--mp POSE_DIR]         # DIR/qa.json over every DIR/*.clip.npz

The clip (<base>.clip.npz), everything in metres, Y up, the character facing +Z on the first frame (glTF convention):
  fps       float
  joints    J names (SOMA public joints, the virtual Root dropped: 0 = Hips)
  parents   J ints, -1 for the root
  offsets   J×3 rest-pose offsets from the parent joint, in the parent's (world-aligned) rest frame. offsets[0] is the root's rest
            position (hips above the floor in the rest T-pose); FK does not add it, the root sits at root[t].
  rot       T×J×4 local rotations (w, x, y, z) relative to the rest pose, so the rest pose is all identity
  root      T×3 world position of the root joint; the first frame at x = z = 0; the floor at y = 0, taken from the body mesh's
            lowest point on planted frames with GEM-X's slow height drift fitted out as a line (--floor flat: one constant shift)
  contact   T×4 probabilities for L heel, L toe, R heel, R toe: GEM-X's static-joint confidences (sigmoid of its logits) for
            LeftFoot (the ankle, standing in for the heel) and LeftToeBase (the ball of the foot), then the right side
  meta      JSON string: source, model, versions, licences, command, date, conventions
FK:  G[root] = rot[root], p[root] = root[t];  G[j] = G[parent]·rot[j],  p[j] = p[parent] + G[parent]·offsets[j].
The BVH carries the same skeleton and motion: metres, Y up, ZXY Euler channels (degrees), root OFFSET 0 with absolute position
channels (CMU style), a leaf's End Site 2 cm along its bone.
"""
import argparse, datetime, glob, json, os, sys
import numpy as np
from scipy.spatial.transform import Rotation as Rot

CONTACT_NAMES = ['LeftFoot', 'LeftToeBase', 'RightFoot', 'RightToeBase']   # GEM-X static_conf_logits[:, 0:4] (SOMA77 69, 70, 74, 75)
BVH_ORDER = 'ZXY'
FLOOR_LAMBDA = 30.0          # floor lock smoothing (frames⁴): responds within ~0.6 s at 24 fps


# ---------------------------------------------------------------- stage 1: FK on the box (torch + soma)
def export_raw(pt, base, gemx, fps, src, cmd):
    import torch
    sys.path.insert(0, gemx); os.chdir(gemx)                     # GEM-X resolves inputs/soma_assets relative to its root
    from gem.utils.soma_utils.soma_layer import SomaLayer
    pred = torch.load(pt, map_location='cpu', weights_only=False)
    bp = {k: v.float() for k, v in pred['body_params_global'].items()}
    L = bp['transl'].shape[0]
    layer = SomaLayer(data_root='inputs/soma_assets', low_lod=True, device='cuda', identity_model_type='mhr', mode='warp')
    soma = layer.soma
    ident, scale = bp['identity_coeffs'].mean(0, keepdim=True).cuda(), bp['scale_params'].mean(0, keepdim=True).cuda()
    soma.prepare_identity(ident, scale[:, 1:], repose_to_bind_pose=False, global_scale=scale[:, :1])
    poses = torch.cat([bp['global_orient'][:, None], bp['body_pose'].reshape(L, 76, 3)], 1).cuda()
    with torch.no_grad():
        out = soma_fk(soma, poses, bp['transl'].cuda())
        rest = soma_fk(soma, torch.zeros(1, 77, 3, device='cuda'), torch.zeros(1, 3, device='cuda'))
        # the same call GEM-X's own renderer makes (SomaLayer.temporal_forward), to confirm we FK exactly what it shows
        ref = layer(**{k: v[None].cuda() for k, v in bp.items()})['joints'][0]
    err = (out['transforms'][:, 1:, :3, 3] - ref).norm(dim=-1).max().item()
    print(f'[soma_clip] FK vs GEM-X temporal_forward: max {err * 1000:.4f} mm')
    names = [str(n) for n in (soma.public_joint_names if hasattr(soma, 'public_joint_names') else soma.rig_data['joint_names'])]
    parents = np.asarray(soma.output_joint_parent_ids.cpu() if hasattr(soma, 'output_joint_parent_ids')
                         else soma.rig_data['joint_parent_ids']).astype(int)
    assert len(names) == 78 and len(parents) == 78, (len(names), len(parents))
    logits = pred['net_outputs'].get('static_conf_logits')
    logits = logits[0].float().numpy() if logits is not None else np.full((L, 6), np.nan, np.float32)
    kp2d = [p for p in (os.path.join(os.path.dirname(pt), d, 'vitpose.pt') for d in ('preprocess', '.')) if os.path.exists(p)]
    kp = torch.load(kp2d[0], weights_only=False) if kp2d else None
    kp = (kp[0] if isinstance(kp, tuple) else kp)
    kpconf = np.asarray(kp[..., 2], np.float32) if kp is not None else np.full((L, 77), np.nan, np.float32)
    hf_sha = gemx_ckpt_sha(gemx)
    meta = {'source': os.path.abspath(src) if src else None, 'source_name': os.path.basename(src) if src else None,
            'model': 'NVIDIA GEM-X, gem_soma.ckpt (SOMA 77 joints, MHR identity backend), regression decoder, contact post-process on',
            'gemx_commit': git_rev(gemx), 'soma_x_commit': git_rev(os.path.join(gemx, 'third_party/soma')),
            'weights': f'huggingface.co/nvidia/GEM-X{"@" + hf_sha if hf_sha else ""} (gem_soma.ckpt, sam3d_body.ckpt, vitpose.pth, mhr_model.pt)',
            'licence': 'GEM-X code Apache-2.0; GEM-X weights NVIDIA Open Model License; SOMA-X Apache-2.0; MHR Apache-2.0; '
                       'SAM-3D-Body features: SAM Licence; person detector YOLOX-X (OpenMMLab, Apache-2.0, trained on COCO + Human-Art)',
            'command': cmd, 'date': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
            'fps_note': "GEM-X's demo re-encodes the input at 30 fps (same frames, relabelled); frames map 1:1 to the source, so "
                        'fps here is the source rate', 'fk_check_mm': round(err * 1000, 5)}
    raw = dict(fps=float(fps), names=np.array(names), parents=parents,
               T=out['transforms'].double().cpu().numpy(), T_rest=rest['transforms'][0].double().cpu().numpy(),
               vmin_y=out['vertices'][..., 1].min(-1).values.double().cpu().numpy(),
               rest_vmin_y=float(rest['vertices'][0, :, 1].min()), static_logits=logits, kp2d_conf=kpconf,
               meta=json.dumps(meta))
    np.savez_compressed(base + '.raw.npz', **raw)
    return base + '.raw.npz'


def soma_fk(soma, poses, transl):
    """World transforms (B×78×4×4, incl. the virtual Root) and vertices for T-pose-relative axis-angle poses (B×77×3), no
    pose correctives. SOMA-X main returns 'transforms' from pose(); the version GEM-X pins (e0f8ff0) doesn't, so go one level down."""
    import inspect
    if 'fk_only' in inspect.signature(soma.pose).parameters:
        return soma.pose(poses, transl=transl, pose2rot=True, apply_correctives=False)
    from soma.geometry.lbs import batch_rodrigues
    B = poses.shape[0]
    R = soma._pad_poses(batch_rodrigues(poses.reshape(-1, 3)).view(B, 77, 3, 3))
    rest, bind = soma._cached_rest_shape, soma._cached_bind_transforms_world
    if bind.shape[0] == 1 and B > 1: bind, rest = bind.expand(B, -1, -1, -1), rest.expand(B, -1, -1)
    soma.batched_skinning.rebind(bind, rest)
    v, T = soma.batched_skinning.pose(local_rotations=R, hips_translations=transl, return_transforms=True, absolute_pose=False)
    return {'vertices': v, 'transforms': T}


def git_rev(d):
    try:
        import subprocess
        return subprocess.run(['git', '-C', d, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def gemx_ckpt_sha(gemx):
    for p in glob.glob(os.path.join(gemx, 'inputs/pretrained/.cache/huggingface/download/*.metadata')):
        try: return open(p).read().split()[0]
        except Exception: pass
    return None


# ---------------------------------------------------------------- stage 2: canonical clip (numpy + scipy)
def quat_wxyz(R):
    q = Rot.from_matrix(R.reshape(-1, 3, 3)).as_quat().reshape(R.shape[:-2] + (4,))    # x, y, z, w
    q = np.concatenate([q[..., 3:], q[..., :3]], -1)
    for t in range(1, len(q)):                                                           # one hemisphere, frame to frame
        flip = (q[t] * q[t - 1]).sum(-1) < 0; q[t, flip] *= -1
    return q


def mat_wxyz(q):
    return Rot.from_quat(np.concatenate([q[..., 1:], q[..., :1]], -1).reshape(-1, 4)).as_matrix().reshape(q.shape[:-1] + (3, 3))


def fk(parents, offsets, rot, root):
    """World joint positions (T×J×3) and rotations (T×J×3×3) from a clip."""
    R = mat_wxyz(rot); T, J = rot.shape[:2]
    G = np.zeros((T, J, 3, 3)); P = np.zeros((T, J, 3))
    for j in range(J):
        p = parents[j]
        if p < 0: G[:, j] = R[:, j]; P[:, j] = root
        else: G[:, j] = G[:, p] @ R[:, j]; P[:, j] = P[:, p] + np.einsum('tab,b->ta', G[:, p], offsets[j])
    return P, G


def convert(raw_path, base, floor_mode='lock'):
    r = np.load(raw_path, allow_pickle=False)
    meta = json.loads(str(r['meta']))
    names78, par78 = [str(n) for n in r['names']], r['parents']
    assert names78[0] == 'Root' and par78[1] == 0, (names78[:2], par78[:2])
    names, parents = names78[1:], np.array([p - 1 if p > 0 else -1 for p in par78[1:]])
    T, Tr = r['T'][:, 1:], r['T_rest'][1:]
    R, P, Rr, Pr = T[..., :3, :3], T[..., :3, 3], Tr[:, :3, :3], Tr[:, :3, 3]
    n = len(P)
    # heading: rotate about Y so the root faces +Z on frame 0; move the frame-0 root to x = z = 0
    D0 = R[0, 0] @ Rr[0].T
    f = D0 @ np.array([0, 0, 1.0]); yaw = np.arctan2(f[0], f[2])
    Ry = Rot.from_euler('y', -yaw).as_matrix()
    P = P - np.array([P[0, 0, 0], 0, P[0, 0, 2]])
    P = np.einsum('ab,tjb->tja', Ry, P); R = np.einsum('ab,tjbc->tjac', Ry, R)
    # contacts, then the floor: the mesh's lowest point on frames where a foot is planted
    lg = r['static_logits'][:, :4].astype(float)
    contact = 1 / (1 + np.exp(-lg)) if np.isfinite(lg).all() else None
    vmin = r['vmin_y']
    planted = contact.max(1) > .5 if contact is not None else np.zeros(n, bool)
    # The floor. GEM-X's world height wanders by several cm within a clip (a planted foot's sole rises and sinks, then jumps
    # when the weight changes feet), so by default ('lock') the floor follows the body mesh's lowest point wherever a foot is
    # planted: a Whittaker smoother of the sole height, weighted by the contact probability, bridging unplanted spans smoothly
    # (airborne arcs keep their shape against a straight floor), and no frame's sole below it by more than 5 mm.
    # 'linear' fits one line on planted frames; 'flat' is one shift.
    t = np.arange(n) / float(r['fps'])
    if floor_mode == 'lock' and planted.sum() >= 5:
        w = np.clip((contact.max(1) - .3) / .4, 0, 1) ** 2 + 1e-4
        D = np.diff(np.eye(n), 2, axis=0)
        for _ in range(4):                  # then no frame may sink through the floor: pin the ones that do, and solve again
            floor_t = np.linalg.solve(np.diag(w) + FLOOR_LAMBDA * D.T @ D, w * vmin)
            sunk = vmin - floor_t < -.005
            if not sunk.any(): break
            w[sunk] = 1.0
    elif floor_mode == 'linear' and planted.sum() >= 10:
        keep = planted.copy()
        for _ in range(2):                                                        # drop fit outliers (> 2 cm) once
            b, a = np.polyfit(t[keep], vmin[keep], 1); res = np.abs(vmin - (a + b * t))
            keep = planted & (res < max(.02, 2.5 * np.median(res[planted])))
        floor_t = a + b * t
    else:
        floor_t = np.full(n, float(np.median(vmin[planted])) if planted.sum() >= 5 else float(np.percentile(vmin, 2)))
    floor = float(floor_t[0])
    P[..., 1] -= floor_t[:, None]; vmin = vmin - floor_t
    # local rotations against the rest pose, rest frames world-aligned
    Dw = np.einsum('tjab,jcb->tjac', R, Rr)                                    # world delta: R · Rrᵀ
    Lr = Dw.copy()
    for j in range(len(names)):
        if parents[j] >= 0: Lr[:, j] = np.einsum('tba,tbc->tac', Dw[:, parents[j]], Dw[:, j])
    offsets = np.array([Pr[j] - Pr[parents[j]] if parents[j] >= 0 else Pr[j] - [0, float(r['rest_vmin_y']), 0]
                        for j in range(len(names))])                          # root: its rest position above the rest sole
    rot, root = quat_wxyz(Lr), P[:, 0].copy()
    if contact is None:
        contact = derived_contacts(names, P, float(r['fps'])); meta['contact'] = 'derived from foot height and speed (no GEM-X logits)'
    else:
        meta['contact'] = ('GEM-X static_conf_logits, sigmoid: LeftFoot (ankle, as heel), LeftToeBase (ball, as toe), RightFoot, '
                           'RightToeBase')
    Pf, _ = fk(parents, offsets, rot, root)
    err = np.linalg.norm(Pf - P, axis=-1).max()
    meta.update({'conventions': 'metres; Y up; facing +Z on frame 0 (glTF); rot = local quaternions w,x,y,z against a T-pose rest '
                                'with world-aligned joint frames; root = world root position, frame 0 at x=z=0, floor y=0; '
                                'offsets[0] = root rest position, not added in FK',
                 'floor': floor_mode, 'floor_shift_m': round(floor, 5),
                 'floor_drift_cm_over_clip': round(float((floor_t[-1] - floor_t[0]) * 100), 2),
                 'floor_correction_range_cm': round(float(np.ptp(floor_t) * 100), 2), 'heading_yaw_deg': round(float(np.degrees(yaw)), 3),
                 'canonical_fk_err_mm': round(float(err) * 1000, 5), 'frames': int(n),
                 'bvh': f'{os.path.basename(base)}.bvh: metres, Y up, {BVH_ORDER} Euler (degrees), root OFFSET 0 + absolute position'})
    assert err < 1e-4, f'canonical FK mismatch {err * 1000:.3f} mm'
    clip = dict(fps=float(r['fps']), joints=np.array(names), parents=parents.astype(np.int32), offsets=offsets.astype(np.float32),
                rot=rot.astype(np.float32), root=root.astype(np.float32), contact=contact.astype(np.float32), meta=json.dumps(meta))
    np.savez_compressed(base + '.clip.npz', **clip)
    extra = dict(sole_y=vmin, kp2d_conf=r['kp2d_conf'])
    np.savez_compressed(base + '.aux.npz', **extra)
    write_bvh(base + '.bvh', clip, meta)
    return base + '.clip.npz'


def derived_contacts(names, P, fps):
    ids = [names.index(n) for n in CONTACT_NAMES]
    h = P[:, ids, 1]; v = np.r_[np.zeros((1, 4)), np.linalg.norm(np.diff(P[:, ids][..., [0, 2]], axis=0), axis=-1) * fps]
    return (1 / (1 + np.exp((h - (np.percentile(h, 5, axis=0) + .03)) / .01))) * (1 / (1 + np.exp((v - .25) / .05)))


# ---------------------------------------------------------------- BVH
def euler_continuous(Rm, order=BVH_ORDER):
    """Intrinsic Euler angles (radians) per frame for one joint, choosing the equivalent triple nearest the previous frame."""
    e = Rot.from_matrix(Rm).as_euler(order)
    alt = np.stack([e[:, 0] + np.pi, np.pi - e[:, 1], e[:, 2] + np.pi], 1)
    out = e.copy()
    for t in range(1, len(e)):
        best = None
        for c in (e[t], alt[t]):
            c = c + 2 * np.pi * np.round((out[t - 1] - c) / (2 * np.pi))
            d = np.abs(c - out[t - 1]).sum()
            if best is None or d < best[0]: best = (d, c)
        out[t] = best[1]
    return out


def write_bvh(path, clip, meta):
    names, parents, off = [str(n) for n in clip['joints']], clip['parents'], clip['offsets'].astype(float)
    rot, root, fps = clip['rot'].astype(float), clip['root'].astype(float), float(clip['fps'])
    kids = {j: [k for k in range(len(names)) if parents[k] == j] for j in range(len(names))}
    ch = {'Z': 'Zrotation', 'X': 'Xrotation', 'Y': 'Yrotation'}
    rch = ' '.join(ch[a] for a in BVH_ORDER)
    lines, order = ['HIERARCHY',
                    f'# {os.path.basename(path)}: SOMA 77 joints from GEM-X ({meta.get("source_name")}); units METRES, Y up, facing +Z; '
                    f'rotation channels {BVH_ORDER} (intrinsic, degrees); root OFFSET 0, root position channels absolute'], []

    def node(j, depth):
        ind = '  ' * depth
        o = [0.0, 0.0, 0.0] if parents[j] < 0 else off[j]
        lines.append(f'{ind}{"ROOT" if parents[j] < 0 else "JOINT"} {names[j]}')
        lines.append(f'{ind}{{')
        lines.append(f'{ind}  OFFSET {o[0]:.6f} {o[1]:.6f} {o[2]:.6f}')
        lines.append(f'{ind}  CHANNELS {"6 Xposition Yposition Zposition " if parents[j] < 0 else "3 "}{rch}')
        order.append(j)
        for k in kids[j]: node(k, depth + 1)
        if not kids[j]:
            d = off[j] if np.linalg.norm(off[j]) > 1e-6 else np.array([0, 1.0, 0])
            e = d / np.linalg.norm(d) * .02
            lines.extend([f'{ind}  End Site', f'{ind}  {{', f'{ind}    OFFSET {e[0]:.6f} {e[1]:.6f} {e[2]:.6f}', f'{ind}  }}'])
        lines.append(f'{ind}}}')
    node(int(np.where(parents < 0)[0][0]), 0)
    eul = {j: np.degrees(euler_continuous(mat_wxyz(rot[:, j]))) for j in order}
    lines += ['MOTION', f'Frames: {len(root)}', f'Frame Time: {1 / fps:.8f}']
    for t in range(len(root)):
        vals = []
        for j in order:
            if parents[j] < 0: vals += [f'{v:.6f}' for v in root[t]]
            vals += [f'{v:.6f}' for v in eul[j][t]]
        lines.append(' '.join(vals))
    open(path, 'w').write('\n'.join(lines) + '\n')


def read_bvh(path):
    """Minimal BVH reader: names, parents, offsets, per-joint channel lists, motion (frames × channels), frame time."""
    tok = [l.split() for l in open(path) if l.strip() and not l.lstrip().startswith('#')]
    names, parents, offsets, chans, stack, i = [], [], [], [], [], 0
    while tok[i][0] != 'MOTION':
        w = tok[i]
        if w[0] in ('ROOT', 'JOINT'):
            names.append(w[1]); parents.append(stack[-1] if stack else -1); stack.append(len(names) - 1)
            offsets.append([float(x) for x in tok[i + 2][1:4]]); chans.append(tok[i + 3][2:]); i += 4; continue
        if w[0] == 'End': i += 4; continue
        if w[0] == '}': stack.pop()
        i += 1
    frames, ft = int(tok[i + 1][1]), float(tok[i + 2][2])
    motion = np.array([[float(x) for x in l] for l in tok[i + 3:i + 3 + frames]])
    return names, np.array(parents), np.array(offsets), chans, motion, ft


def bvh_fk(path):
    names, parents, offsets, chans, motion, ft = read_bvh(path)
    T, c = len(motion), 0
    G = np.zeros((T, len(names), 3, 3)); P = np.zeros((T, len(names), 3))
    for j in range(len(names)):
        pos, R = np.zeros((T, 3)), np.tile(np.eye(3), (T, 1, 1))
        for ch in chans[j]:
            v = motion[:, c]; c += 1
            if ch.endswith('position'): pos[:, 'XYZ'.index(ch[0])] = v
            else: R = R @ Rot.from_euler(ch[0].lower(), np.radians(v)[:, None]).as_matrix()   # channels compose left to right
        p = parents[j]
        if p < 0: G[:, j] = R; P[:, j] = offsets[j] + pos
        else: G[:, j] = G[:, p] @ R; P[:, j] = P[:, p] + np.einsum('tab,b->ta', G[:, p], offsets[j])
    return names, P, 1 / ft


# ---------------------------------------------------------------- checks and QA
def load_clip(base):
    c = np.load(base + '.clip.npz', allow_pickle=False)
    return {k: c[k] for k in c.files}


def check(base):
    c = load_clip(base)
    P, _ = fk(c['parents'], c['offsets'].astype(float), c['rot'].astype(float), c['root'].astype(float))
    names, Pb, fps = bvh_fk(base + '.bvh')
    assert names == [str(n) for n in c['joints']], 'BVH joint order differs'
    err = np.linalg.norm(Pb - P, axis=-1)
    print(f'{os.path.basename(base)}: BVH vs npz FK over {len(P)} frames × {P.shape[1]} joints: max {err.max() * 1000:.4f} mm, '
          f'mean {err.mean() * 1000:.4f} mm; BVH fps {fps:.3f}, npz fps {float(c["fps"]):.3f}')
    return float(err.max())


BODY = ['Hips', 'Spine1', 'Spine2', 'Chest', 'Neck1', 'Neck2', 'Head', 'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
        'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand', 'LeftLeg', 'LeftShin', 'LeftFoot', 'LeftToeBase',
        'RightLeg', 'RightShin', 'RightFoot', 'RightToeBase']


def qa(base):
    c = load_clip(base); names = [str(n) for n in c['joints']]; fps = float(c['fps'])
    P, _ = fk(c['parents'], c['offsets'].astype(float), c['rot'].astype(float), c['root'].astype(float))
    n = len(P); con = c['contact']
    aux = np.load(base + '.aux.npz') if os.path.exists(base + '.aux.npz') else None
    # planted-foot slide: horizontal travel of each contact joint between frames where it is planted on both
    slide = {}
    for k, jn in enumerate(CONTACT_NAMES):
        j = names.index(jn); on = (con[1:, k] > .5) & (con[:-1, k] > .5)
        d = np.linalg.norm(np.diff(P[:, j][:, [0, 2]], axis=0), axis=-1) * 1000
        slide[jn] = {'planted_frames': int(on.sum()), 'mean_mm_per_frame': round(float(d[on].mean()), 2) if on.any() else None,
                     'p95_mm_per_frame': round(float(np.percentile(d[on], 95)), 2) if on.any() else None}
    # speed spikes (possible swaps or pops): body joints, speed in m/s, and single-frame jumps against the neighbours
    ids = [names.index(b) for b in BODY if b in names]
    v = np.linalg.norm(np.diff(P[:, ids], axis=0), axis=-1) * fps                         # (n-1) × body
    vmax_i = np.unravel_index(v.argmax(), v.shape)
    acc = np.linalg.norm(P[2:, ids] - 2 * P[1:-1, ids] + P[:-2, ids], axis=-1) * fps * fps   # m/s²
    med = np.median(acc, axis=0); mad = np.median(np.abs(acc - med), axis=0) + 1e-6
    spk = (acc > med + 12 * mad) & (acc > 60)
    spikes = [{'frame': int(t + 1), 'joint': BODY[b] if b < len(BODY) else names[ids[b]], 'accel_ms2': round(float(acc[t, b]), 1)}
              for t, b in zip(*np.where(spk))]
    spikes = sorted(spikes, key=lambda s: -s['accel_ms2'])
    # left/right swap check on the legs: the ankles' side (x in the root's heading frame) flipping for a frame or two
    # bone lengths (should be ~0 variance: fixed skeleton)
    bl = np.stack([np.linalg.norm(P[:, j] - P[:, c['parents'][j]], axis=-1) for j in range(len(names)) if c['parents'][j] >= 0], 1)
    root = c['root']
    out = {'frames': int(n), 'fps': fps, 'seconds': round(n / fps, 3),
           'foot_slide': slide,
           'max_body_joint_speed': {'m_per_s': round(float(v.max()), 2), 'joint': BODY[vmax_i[1]], 'frame': int(vmax_i[0] + 1)},
           'accel_spikes': {'count': len(spikes), 'top': spikes[:5]},
           'bone_length_std_mm_max': round(float(bl.std(0).max() * 1000), 4),
           'root_height_m': {'min': round(float(root[:, 1].min()), 3), 'max': round(float(root[:, 1].max()), 3),
                             'range': round(float(np.ptp(root[:, 1])), 3)},
           'root_travel_xz_m': round(float(np.linalg.norm(root[:, [0, 2]] - root[0, [0, 2]], axis=1).max()), 3),
           'contact_frac': {k: round(float((con[:, i] > .5).mean()), 3) for i, k in enumerate(['L_heel', 'L_toe', 'R_heel', 'R_toe'])}}
    if aux is not None:
        s = aux['sole_y']; pl = con.max(1) > .5
        out['sole_height_m'] = {'min': round(float(s.min()), 3), 'max': round(float(s.max()), 3),
                                'planted_abs_mean': round(float(np.abs(s[pl]).mean()), 4) if pl.any() else None,
                                'planted_abs_p95': round(float(np.percentile(np.abs(s[pl]), 95)), 4) if pl.any() else None}
        kc = aux['kp2d_conf']
        if np.isfinite(kc).all():
            grp = {'body': list(range(0, 8)) + [11, 12, 13, 14, 39, 40, 41, 42] + list(range(67, 77)), 'face': [8, 9, 10],
                   'left_fingers': list(range(15, 39)), 'right_fingers': list(range(43, 67))}
            out['kp2d_conf_mean'] = {g: round(float(kc[:, ix].mean()), 3) for g, ix in grp.items()}
    return out


def vs_mediapipe(base, pose_json):
    """Agreement with a MediaPipe track of the same clip (tools/posetrack.py): hip-relative wrists, elbows, knees and ankles, RMS
    distance and per-axis correlation (x = image right = the dancer's left when she faces the camera, y up, z toward the camera),
    after the one yaw that best maps the clip's frame onto the camera's. MediaPipe's world scale and depth are approximate, so read
    the correlations (a negative x means a left/right swap)."""
    c = load_clip(base); names = [str(n) for n in c['joints']]
    P, _ = fk(c['parents'], c['offsets'].astype(float), c['rot'].astype(float), c['root'].astype(float))
    fr = json.load(open(pose_json))['frames']; n = min(len(P), len(fr))
    W = np.array([f['world'] if f['world'] is not None else [[np.nan] * 3] * 33 for f in fr])[:n]
    W = np.stack([W[..., 0], -W[..., 1], -W[..., 2]], -1)                 # MediaPipe x right, y down, z away -> y up, z toward camera
    hipc = (P[:n, names.index('LeftLeg')] + P[:n, names.index('RightLeg')]) / 2
    pairs = {'L_wrist': ('LeftHand', 15), 'R_wrist': ('RightHand', 16), 'L_elbow': ('LeftForeArm', 13),
             'R_elbow': ('RightForeArm', 14), 'L_knee': ('LeftShin', 25), 'R_knee': ('RightShin', 26),
             'L_ankle': ('LeftFoot', 27), 'R_ankle': ('RightFoot', 28)}
    # the clip faces +Z on its first frame, the camera needn't: fit the one yaw that best maps the clip onto the camera view
    G = np.stack([P[:n, names.index(sj)] - hipc for sj, _ in pairs.values()], 1); M = W[:, [mj for _, mj in pairs.values()]]
    ok = ~np.isnan(M).any(-1)
    err = [np.nanmean(np.linalg.norm((G @ Rot.from_euler('y', a, degrees=True).as_matrix().T)[ok] - M[ok], axis=-1)) for a in range(360)]
    yaw = int(np.argmin(err)); Ry = Rot.from_euler('y', yaw, degrees=True).as_matrix()
    out = {'yaw_to_camera_deg': yaw}
    for k, (sj, mj) in pairs.items():
        g, m = (P[:n, names.index(sj)] - hipc) @ Ry.T, W[:, mj]; v = ~np.isnan(m).any(1)
        cor = [round(float(np.corrcoef(g[v, a], m[v, a])[0, 1]), 2) if g[v, a].std() > .01 and m[v, a].std() > .01 else None
               for a in range(3)]
        out[k] = {'rms_cm': round(float(np.sqrt((np.linalg.norm(g[v] - m[v], axis=1) ** 2).mean()) * 100), 1), 'corr_xyz': cor}
    return out


def qa_dir(d, mp=None):
    res = {}
    for f in sorted(glob.glob(os.path.join(d, '*.clip.npz'))):
        b = f[:-len('.clip.npz')]; name = os.path.basename(b)
        res[name] = qa(b)
        if os.path.exists(b + '.bvh'): res[name]['bvh_vs_npz_max_mm'] = round(check(b) * 1000, 4)
        if mp and os.path.exists(os.path.join(mp, name + '_pose.json')):
            res[name]['vs_mediapipe'] = vs_mediapipe(b, os.path.join(mp, name + '_pose.json'))
    json.dump(res, open(os.path.join(d, 'qa.json'), 'w'), indent=1)
    print(f'wrote {os.path.join(d, "qa.json")} ({len(res)} clips)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inp', nargs='?'); ap.add_argument('base', nargs='?')
    ap.add_argument('--src'); ap.add_argument('--fps', type=float, default=None)
    ap.add_argument('--gemx', default='/srv/work/gemx'); ap.add_argument('--cmd', default='')
    ap.add_argument('--check'); ap.add_argument('--qa'); ap.add_argument('--floor', default='lock', choices=['lock', 'linear', 'flat'])
    ap.add_argument('--mp', help='with --qa: a folder of MediaPipe tracks (<name>_pose.json) to compare against')
    a = ap.parse_args()
    if a.check: check(a.check); print(json.dumps(qa(a.check), indent=1)); return
    if a.qa: qa_dir(a.qa, a.mp); return
    base = os.path.abspath(a.base)
    if a.inp.endswith('.pt'):
        fps = a.fps
        if fps is None and a.src:
            import cv2
            fps = cv2.VideoCapture(a.src).get(cv2.CAP_PROP_FPS)
        raw = export_raw(os.path.abspath(a.inp), base, a.gemx, fps or 30.0, a.src and os.path.abspath(a.src), a.cmd)
    else:
        raw = a.inp
    out = convert(raw, base, a.floor)
    check(base)
    print(f'wrote {out}, {base}.bvh')


if __name__ == '__main__':
    main()
