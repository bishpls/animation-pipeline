#!/usr/bin/env python3
"""castspec.py: aggregate `datkit meshstats` JSON (one per fighter) into per-fighter numbers and cast medians.

  python castspec.py STATSDIR [--out summary.json] [--md tables.md]

STATSDIR holds XX.json from `datkit meshstats PlXxNr.dat --ft PlXx.dat --co PlCo.dat --kind N` and attrs.csv from
`datkit attrs PlXx.dat ...` (for ModelScale). Regions come from PlCo.dat's joint-to-part table (part ids as measured in the
data, not the decomp's enum, which is one off after HipN): a triangle belongs to the joint with the largest summed weight
over its three vertices, and extra joints (part 255) inherit their nearest standard ancestor, except that extras hanging off
anything but the head count as 'extra' (capes, tails, weapons, holsters).
"""
import csv, json, math, os, statistics as st, sys

NAMES = {'Mr': 'Mario', 'Lg': 'Luigi', 'Dr': 'Dr. Mario', 'Ms': 'Marth', 'Fe': 'Roy', 'Fx': 'Fox', 'Fc': 'Falco', 'Lk': 'Link',
         'Cl': 'Young Link', 'Sk': 'Sheik', 'Ca': 'Captain Falcon', 'Ns': 'Ness', 'Pc': 'Pichu', 'Pk': 'Pikachu', 'Kb': 'Kirby',
         'Dk': 'Donkey Kong', 'Kp': 'Bowser', 'Pe': 'Peach', 'Pp': 'Popo', 'Nn': 'Nana', 'Ss': 'Samus', 'Ys': 'Yoshi',
         'Pr': 'Jigglypuff', 'Mt': 'Mewtwo', 'Zd': 'Zelda', 'Gw': 'Mr. Game & Watch', 'Gn': 'Ganondorf', 'Ge': 'Geno (current)'}
ATTR = {'Mr': 'Mario', 'Fx': 'Fox', 'Ca': 'Captain', 'Dk': 'Donkey', 'Kb': 'Kirby', 'Kp': 'Koopa', 'Lk': 'Link', 'Sk': 'Seak',
        'Ns': 'Ness', 'Pe': 'Peach', 'Pp': 'Popo', 'Nn': 'Nana', 'Pk': 'Pikachu', 'Ss': 'Samus', 'Ys': 'Yoshi', 'Pr': 'Purin',
        'Mt': 'Mewtwo', 'Lg': 'Luigi', 'Ms': 'Mars', 'Zd': 'Zelda', 'Cl': 'Clink', 'Dr': 'Drmario', 'Fc': 'Falco', 'Pc': 'Pichu',
        'Gw': 'Gamewatch', 'Gn': 'Ganon', 'Fe': 'Emblem', 'Ge': 'Geno'}
CORE = ['Mr', 'Lg', 'Dr', 'Ms', 'Fe', 'Fx', 'Fc', 'Lk', 'Cl', 'Sk', 'Ca', 'Ns', 'Pc']   # the requested cast


def part_region(p):
    if p == 35: return 'head'
    if 6 <= p <= 15: return 'legs'
    if 18 <= p <= 21 or 36 <= p <= 39: return 'arms'
    if 22 <= p <= 33 or 40 <= p <= 51: return 'hands'
    return 'torso'


HEAD_OVERRIDE = {'Gn': 54}   # PlCo.dat leaves Ganondorf's neck and head parts unmapped (part_to_joint 34, 35 = 255)


def regions(joints, code=None, dyn_roots=()):
    """joint -> (region, is_extra). The head joint is part 35 (HeadN), else part 34 (Pichu/Pikachu put the head in the
    NeckN slot), else HEAD_OVERRIDE. Joints at or under a dynamics chain's first bone (ftData+0x2C: capes, tails, hat tips,
    coat tails) are 'dynamics'; other extra joints (part 255: toes, props, face parts) take their nearest standard
    ancestor's region, so a toe counts as legs, a held sword as hands, a hat or eyelid as head."""
    head = HEAD_OVERRIDE.get(code)
    if head is None:
        for want in (35, 34):
            hs = [j['i'] for j in joints if j['part'] == want]
            if hs: head = hs[0]; break
    dyn = set(dyn_roots)
    out = {}
    for j in joints:
        i, p = j['i'], j['part']
        chain = []; k = i
        while k >= 0: chain.append(k); k = joints[k]['p']
        extra = p in (255, -1) and i != head
        if any(k in dyn for k in chain): out[i] = ('dynamics', True); continue
        if head is not None and head in chain: out[i] = ('head', i != head); continue
        anc = next((k for k in chain if joints[k]['part'] not in (255, -1)), None)
        pa = joints[anc]['part'] if anc is not None else 0
        out[i] = ('torso' if pa in (34, 35) else part_region(pa), extra)
    return out


def fighter(code, d, scale):
    J = d['joints']; R = regions(J, code, [c['bone'] for c in ((d.get('dynamics') or {}).get('chains', []))]) if any(j['part'] != -1 for j in J) else {j['i']: ('torso', False) for j in J}
    D = {o['i']: o for o in d['dobjs']}
    hi, lo = set(d.get('high') or []), set(d.get('low') or [])
    listed = hi | lo
    # default high model: option 0 of each high group, plus everything in neither table
    hg = d.get('highGroups') or []
    default = {i for i in D if i not in listed}
    alternates = set()
    for g in hg:
        for k, opt in enumerate(g):
            (default if k == 0 else alternates).update(opt)
    alternates -= default
    lg = d.get('lowGroups') or []
    low_default = {i for i in D if i not in listed}
    for g in lg:
        for k, opt in enumerate(g):
            if k == 0: low_default.update(opt)

    def tris(s): return sum(D[i]['tris'] for i in s if i in D)
    reg = {r: 0 for r in ('head', 'torso', 'arms', 'hands', 'legs', 'dynamics')}
    tex = {'head': [0, 0], 'body': [0, 0]}
    bb = {}; core = [1e9, 1e9, 1e9, -1e9, -1e9, -1e9]
    hj = next((i for i, (r, e) in R.items() if r == 'head' and not e), None)
    for i in default:
        for js, acc in D[i]['byJoint'].items():
            r, _ = R.get(int(js), ('torso', False))
            reg[r] += acc[0]
            key = 'head' if r == 'head' else 'body'
            tex[key][0] += acc[2]; tex[key][1] += acc[3]
            b = bb.setdefault(r, [1e9, 1e9, 1e9, -1e9, -1e9, -1e9])
            if int(js) == hj:
                for q in range(3): core[q] = min(core[q], acc[4 + q]); core[q + 3] = max(core[q + 3], acc[7 + q])
            if r in ('hands', 'head') and J[int(js)]['part'] in (255, -1) and int(js) != hj and r == 'hands': continue
            for q in range(3): b[q] = min(b[q], acc[4 + q]); b[q + 3] = max(b[q + 3], acc[7 + q])
            if r == 'hands':
                hb_ = bb.setdefault('handL' if 22 <= J[int(js)]['part'] <= 33 else 'handR', [1e9, 1e9, 1e9, -1e9, -1e9, -1e9])
                for q in range(3): hb_[q] = min(hb_[q], acc[4 + q]); hb_[q + 3] = max(hb_[q + 3], acc[7 + q])
    ymin = min(D[i]['ymin'] for i in default if D[i]['tris']); ymax = max(D[i]['ymax'] for i in default if D[i]['tris'])
    height = ymax - ymin
    # head block: chin (lowest vertex on the head joint itself) to the top of everything on the head (hat, hair, ears)
    hb = bb.get('head'); head_h = hb[4] - core[1] if hb and hj is not None and core[1] < 1e8 else 0
    head_core_h = core[4] - core[1] if core[1] < 1e8 else 0
    # hand length: the longest side of each hand's box (wrist joint and fingers, not props), averaged over both hands
    hs = [max(h[3] - h[0], h[4] - h[1], h[5] - h[2]) for h in (bb.get('handL'), bb.get('handR')) if h and h[3] > h[0]]
    hand_sz = sum(hs) / len(hs) if hs else 0
    # PObjs / skinning
    pk = {}; vinf = [0] * 9; envh = [0] * 9; npobj = 0
    for i in default:
        for p in D[i]['pobjs']:
            npobj += 1; pk[p['kind']] = pk.get(p['kind'], 0) + p['tris']
            for k in range(9): vinf[k] += p['vinf'][k]; envh[k] += p['envhist'][k]
    # textures
    texs = {}; texdob = {}
    for i in D:
        for t in D[i]['mat']['tex']:
            if t['key'] is None: continue
            texs[t['key']] = t; texdob.setdefault(t['key'], set()).add(i)
    hi_tex = {t['key'] for i in default for t in D[i]['mat']['tex'] if t['key']}
    lo_only = {k for k in texs if k not in hi_tex}
    # texture animations (eyes): distinct images across DObjs, since both eyes may share one set
    ta_keys = {}; seen = set(); ta_bytes = 0
    for ta in d.get('texanims', []):
        sizes = ta['sizes'] if len(ta['sizes']) == len(ta['keys']) else ta['sizes'] * len(ta['keys'])
        per = ta['bytes'] / max(1, ta['images'])
        for k, sz in zip(ta['keys'], sizes):
            ta_keys[k] = sz
            if k not in seen: seen.add(k); ta_bytes += per
    fmt = {}
    for k, t in texs.items(): fmt[t['fmt']] = fmt.get(t['fmt'], 0) + 1
    coord = {}
    for k, t in texs.items(): coord[t['coord']] = coord.get(t['coord'], 0) + 1
    # materials
    mats = [D[i]['mat'] for i in default]
    flags = {}
    for m in mats:
        for f in m['flags']: flags[f] = flags.get(f, 0) + 1
    vcol = sum(1 for i in default if any('CLR0' in (p['attrs'] or '') for p in D[i]['pobjs']))
    dyn = d.get('dynamics') or {}
    chains = [(c['bone'], c['n']) for c in dyn.get('chains', [])]
    std = sum(1 for j in J if j['part'] not in (255, -1))
    s = scale or 1
    dens = {k: (math.sqrt(v[0] / v[1]) if v[1] else 0) for k, v in tex.items()}
    return dict(
        code=code, name=NAMES.get(code, code), scale=scale,
        head_joints=sorted(i for i, (r, _) in R.items() if r == 'head'), hand_joints=sorted(i for i, (r, e) in R.items() if r == 'hands'), joints=len(J), std_joints=std, extra_joints=len(J) - std,
        dobjs=len(D), high_dobjs=len(default), low_dobjs=len(low_default), alt_dobjs=len(alternates), pobjs_high=npobj,
        tris_high=tris(default), tris_low=tris(low_default), tris_alt=tris(alternates), tris_all=tris(D.keys()),
        verts_high=sum(D[i]['uniquePos'] for i in default), verts_low=sum(D[i]['uniquePos'] for i in low_default),
        dlverts_high=sum(D[i]['dlverts'] for i in default), prims_high=sum(D[i]['prims'] for i in default),
        regions=reg, pobj_kinds=pk, vinf=vinf, envhist=envh,
        height_model=height, height_game=height * s, head_h=head_h, heads_tall=height / head_h if head_h else 0, head_core_h=head_core_h, head_joint=hj,
        head_w=(hb[3] - hb[0]) if hb else 0,
        hand=hand_sz, hand_ratio=hand_sz / height if height else 0,
        tex_count=len(texs), tex_high=len(hi_tex), tex_low_only=len(lo_only),
        tex_bytes=sum(t['bytes'] for t in texs.values()), tex_bytes_high=sum(texs[k]['bytes'] for k in hi_tex),
        texanim_images=len(seen), texanim_bytes=int(ta_bytes), texanim_sizes=sorted(set(ta_keys.values())),
        texanim_dobjs=sorted({ta['dobj'] for ta in d.get('texanims', [])}),
        fmt=fmt, coord=coord, sizes=sorted({(t['w'], t['h']) for t in texs.values()}, key=lambda wh: (-wh[0] * wh[1], wh)),
        largest=max(((t['w'] * t['h'], f"{t['w']}x{t['h']} {t['fmt']}") for t in texs.values()), default=(0, ''))[1],
        density_head=dens['head'], density_body=dens['body'],
        density_head_game=dens['head'] / s, density_body_game=dens['body'] / s,
        texels_per_height_head=dens['head'] * height, texels_per_height_body=dens['body'] * height,
        mat_flags=flags, mats_high=len(mats), vcol_dobjs=vcol,
        dif=[m['dif'] for m in mats], amb=[m['amb'] for m in mats], spc=[m['spc'] for m in mats], shin=[m['shininess'] for m in mats],
        alpha=[m['alpha'] for m in mats], pe=sum(1 for m in mats if m['pe']), chains=chains, bubbles=len(dyn.get('bubbles', [])),
    )


def med(xs): xs = [x for x in xs if x is not None]; return st.median(xs) if xs else 0


def main():
    sd = sys.argv[1]
    scales = {}
    if os.path.exists(os.path.join(sd, 'attrs.csv')):
        for r in csv.DictReader(open(os.path.join(sd, 'attrs.csv'))): scales[r['fighter']] = float(r['ModelScale'])
    out = {}
    for fn in sorted(os.listdir(sd)):
        if not fn.endswith('.json') or fn.startswith('summary'): continue
        code = fn[:-5]
        d = json.load(open(os.path.join(sd, fn)))
        out[code] = fighter(code, d, scales.get(ATTR.get(code)))
    if '--out' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--out') + 1], 'w'), indent=1)
    core = [out[c] for c in CORE if c in out]
    cols = ['tris_high', 'tris_low', 'verts_high', 'dobjs', 'pobjs_high', 'joints', 'extra_joints', 'tex_count', 'tex_bytes',
            'texanim_bytes', 'height_game', 'heads_tall', 'density_head_game', 'density_body_game', 'texels_per_height_head',
            'texels_per_height_body']
    print('code ' + ' '.join(f'{c[:12]:>12}' for c in cols))
    for f in list(out.values()):
        print(f"{f['code']:4} " + ' '.join(f"{f[c]:12.1f}" if isinstance(f[c], float) else f"{f[c]:12}" for c in cols))
    print('MED  ' + ' '.join(f"{med([f[c] for f in core]):12.1f}" for c in cols))
    print('MIN  ' + ' '.join(f"{min(f[c] for f in core):12.1f}" for c in cols))
    print('MAX  ' + ' '.join(f"{max(f[c] for f in core):12.1f}" for c in cols))


if __name__ == '__main__':
    main()


def md_tables(out, order):
    """Markdown tables for SPEC.md: geometry, regions, textures/face, proportions."""
    core = [out[c] for c in CORE if c in out]
    def row(cells): return '| ' + ' | '.join(str(x) for x in cells) + ' |'
    def stats(key, fmt='{:.0f}', fs=core):
        v = [f[key] for f in fs]
        return fmt.format(med(v)), f"{fmt.format(min(v))}–{fmt.format(max(v))}"
    L = []
    L.append('### Geometry (costume 0, default visible set)\n')
    L.append(row(['Fighter', 'Tris high', 'Tris low', 'Verts high', 'Verts low', 'Meshes (DObj) hi/lo', 'PObjs hi', 'Joints (std+extra)', 'Height (game u)', 'ModelScale']))
    L.append(row(['---'] * 10))
    for c in order:
        f = out[c]
        L.append(row([f"{f['name']} ({c})", f['tris_high'], f['tris_low'], f['verts_high'], f['verts_low'], f"{f['high_dobjs']}/{f['low_dobjs']}",
                      f['pobjs_high'], f"{f['joints']} ({f['std_joints']}+{f['extra_joints']})", f"{f['height_game']:.1f}", f"{f['scale']:.2f}" if f['scale'] else '-']))
    L.append(row(['**Median (13)**'] + [stats(k)[0] for k in ('tris_high', 'tris_low', 'verts_high', 'verts_low')] + [f"{stats('high_dobjs')[0]}/{stats('low_dobjs')[0]}", stats('pobjs_high')[0], stats('joints')[0], stats('height_game', '{:.1f}')[0], '']))
    L.append(row(['**Range (13)**'] + [stats(k)[1] for k in ('tris_high', 'tris_low', 'verts_high', 'verts_low')] + [f"{stats('high_dobjs')[1]} / {stats('low_dobjs')[1]}", stats('pobjs_high')[1], stats('joints')[1], stats('height_game', '{:.1f}')[1], '']))
    L.append('\n### Where the high model\'s triangles go (% of triangles, by the joint with the largest summed weight)\n')
    regs = ['head', 'torso', 'arms', 'hands', 'legs', 'dynamics']
    L.append(row(['Fighter'] + regs + ['head tris']))
    L.append(row(['---'] * 8))
    for c in order:
        f = out[c]; T = f['tris_high'] or 1
        L.append(row([c] + [f"{100 * f['regions'][r] / T:.0f}" for r in regs] + [f['regions']['head']]))
    for lab, fn in (('**Median (13)**', med), ('**Min**', min), ('**Max**', max)):
        L.append(row([lab] + [f"{fn([100 * f['regions'][r] / f['tris_high'] for f in core]):.0f}" for r in regs] + [f"{fn([f['regions']['head'] for f in core]):.0f}"]))
    L.append('\n### Textures and face\n')
    L.append(row(['Fighter', 'Textures (hi)', 'KiB (all)', 'Largest', 'Formats', 'Eye anim: frames × size', 'Eye KiB', 'Face texels/game-u', 'Body texels/game-u', 'Face texels over head height']))
    L.append(row(['---'] * 10))
    for c in order:
        f = out[c]
        eyes = ', '.join(f['texanim_sizes']) if f['texanim_sizes'] else 'none'
        n = f['texanim_images']
        L.append(row([c, f"{f['tex_count']} ({f['tex_high']})", f"{f['tex_bytes'] / 1024:.0f}", f['largest'], ' '.join(f'{k}:{v}' for k, v in sorted(f['fmt'].items(), key=lambda kv: -kv[1])),
                      f"{n} img, {eyes}".replace('/RGB565x256', ' (RGB565 palette)'), f"{f['texanim_bytes'] / 1024:.0f}",
                      f"{f['density_head_game']:.0f}", f"{f['density_body_game']:.0f}", f"{f['density_head'] * f['head_h']:.0f}"]))
    dh = [f['density_head'] * f['head_h'] for f in core]
    L.append(row(['**Median (13)**', stats('tex_count')[0], f"{med([f['tex_bytes'] for f in core]) / 1024:.0f}", '', '', f"{stats('texanim_images')[0]} img", f"{med([f['texanim_bytes'] for f in core]) / 1024:.0f}",
                  stats('density_head_game')[0], stats('density_body_game')[0], f"{med(dh):.0f}"]))
    L.append(row(['**Range (13)**', stats('tex_count')[1], f"{min(f['tex_bytes'] for f in core) / 1024:.0f}–{max(f['tex_bytes'] for f in core) / 1024:.0f}", '', '', '', '',
                  stats('density_head_game')[1], stats('density_body_game')[1], f"{min(dh):.0f}–{max(dh):.0f}"]))
    L.append('\n### Proportions (rest T-pose; in-game units = model units × ModelScale)\n')
    L.append(row(['Fighter', 'Height', 'Head block height', 'Heads tall', 'Head width', 'Hand length', 'Hand / height', 'Hand / head', 'Dynamics chains (start joint × bones)']))
    L.append(row(['---'] * 9))
    for c in order:
        f = out[c]; s = f['scale'] or 1
        ch = ', '.join(f'{b}×{n}' for b, n in f['chains']) or '–'
        L.append(row([c, f"{f['height_game']:.1f}", f"{f['head_h'] * s:.1f}", f"{f['heads_tall']:.1f}", f"{f['head_w'] * s:.1f}", f"{f['hand'] * s:.1f}",
                      f"{f['hand_ratio']:.2f}", f"{f['hand'] / f['head_h']:.2f}" if f['head_h'] else '-', ch]))
    L.append(row(['**Median (13)**', stats('height_game', '{:.1f}')[0], f"{med([f['head_h'] * f['scale'] for f in core]):.1f}", stats('heads_tall', '{:.1f}')[0],
                  f"{med([f['head_w'] * f['scale'] for f in core]):.1f}", f"{med([f['hand'] * f['scale'] for f in core]):.1f}", stats('hand_ratio', '{:.2f}')[0],
                  f"{med([f['hand'] / f['head_h'] for f in core]):.2f}", '']))
    return '\n'.join(L) + '\n'


if __name__ == '__main__' and '--md' in sys.argv:
    sd = sys.argv[1]
    out = json.load(open(os.path.join(sd, '..', 'summary.json')))
    order = CORE + [c for c in ['Pk', 'Kb', 'Pr', 'Pp', 'Ys', 'Pe', 'Zd', 'Ss', 'Mt', 'Gn', 'Dk', 'Kp', 'Ge'] if c in out]
    open(sys.argv[sys.argv.index('--md') + 1], 'w').write(md_tables(out, order))
