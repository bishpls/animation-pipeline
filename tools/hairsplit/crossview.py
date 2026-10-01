"""The cross-view identity against the truth's names: our locks matched to the truth's per view (the scorer's
assignment), then each of our cross-view links (hairsplit.match) read as a pair of truth names; a link is right when
both ends match truth locks of one name (the truth's names carry the hand correspondences: the under-bun strands, the
side flicks front and back (call H), the bangs and side locks across front, three-quarter and profile). Reports the
links, precision and recall against the truth's same-name pairs, and call H's flicks.

    python tools/hairsplit/crossview.py OUT.json [--set K=V ...]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev

if __name__ == '__main__':
    a = sys.argv[1:]
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            k, v = a[i + 1].split('=')
            params[k] = json.loads(v)
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    hs.P.update(params)
    splits, shell, xid, matches = hs.split_views(I, params=params, log=lambda *x: None)
    r = hs.score(hs.lock_images(splits), T)
    # our lock -> truth name (matched at IoU >= 0.3)
    name_of = {}
    for v in splits:
        for q, x in r[v]['locks'].items():
            if x.get('ours') is not None and x['iou'] >= 0.3:
                name_of[(v, int(x['ours']))] = (q, x['iou'])
    print('shell check (median |error| of the back and three-quarter silhouettes predicted, L):', shell.check)
    links = []
    for m in matches:
        va, vb = m['views']
        for la, lb, c in m['pairs']:
            na, nb = name_of.get((va, la)), name_of.get((vb, lb))
            links.append(dict(views=[va, vb], ours=[la, lb], cost=c, truth=[na[0] if na else None, nb[0] if nb else None],
                              tip_phi=[splits[va].lock_info[la]['tip_phi'], splits[vb].lock_info[lb]['tip_phi']],
                              tip_z=[splits[va].lock_info[la]['tip_uz'][1], splits[vb].lock_info[lb]['tip_uz'][1]]))
    # the truth's same-name pairs between views (both matched by our locks)
    tl = {}
    for (v, l_), (q, _) in name_of.items():
        tl.setdefault(q, []).append((v, l_))
    want = set()
    for q, lst in tl.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                want.add(tuple(sorted([lst[i], lst[j]])))
    got = set()
    right = 0
    judged = 0
    for L in links:
        ka, kb = (L['views'][0], L['ours'][0]), (L['views'][1], L['ours'][1])
        if L['truth'][0] and L['truth'][1]:
            judged += 1
            if L['truth'][0] == L['truth'][1]:
                right += 1
                got.add(tuple(sorted([ka, kb])))
    print('links %d; with both ends on named truth locks %d, right %d (precision %.2f); truth same-name pairs %d, '
          'found %d (recall %.2f)' % (len(links), judged, right, right / max(1, judged), len(want), len(got & want),
                                      len(got & want) / max(1, len(want))))
    for L in links:
        if L['truth'][0] or L['truth'][1]:
            print('  %-13s %-13s %3d %3d  %-26s %-26s phi %6.1f %6.1f  z %.3f %.3f  cost %.3f %s' % (
                L['views'][0], L['views'][1], L['ours'][0], L['ours'][1], L['truth'][0], L['truth'][1],
                L['tip_phi'][0], L['tip_phi'][1], L['tip_z'][0], L['tip_z'][1], L['cost'],
                'OK' if L['truth'][0] == L['truth'][1] else ('--' if None in L['truth'] else 'WRONG')))
    # call H: the front's and back's side flicks
    print('call H (front and back side flicks):')
    H = {}
    for q in ('flyaways/flick_L1', 'flyaways/flick_L2', 'flyaways/flick_R1', 'flyaways/flick_R2', 'lower_back/flick_L3',
              'lower_back/flick_R3'):
        ends = {v: l_ for (v, l_), (qq, _) in name_of.items() if qq == q and v in ('front', 'back')}
        if len(ends) < 2:
            print('  %-22s not matched in both views by our locks: %s' % (q, ends))
            H[q] = dict(matched_both=False)
            continue
        la, lb = ends['front'], ends['back']
        linked = any(set(map(tuple, [(L['views'][0], L['ours'][0]), (L['views'][1], L['ours'][1])])) ==
                     {('front', la), ('back', lb)} for L in links)
        fa, fb = splits['front'].lock_info[la], splits['back'].lock_info[lb]
        same_id = fa.get('xid') == fb.get('xid')
        print('  %-22s front lock %d (tip phi %.1f, z %.3f) back lock %d (tip phi %.1f, z %.3f): linked %s, same id %s'
              % (q, la, fa['tip_phi'], fa['tip_uz'][1], lb, fb['tip_phi'], fb['tip_uz'][1], linked, same_id))
        H[q] = dict(matched_both=True, linked=bool(linked), same_id=bool(same_id), front=[fa['tip_phi'], fa['tip_uz'][1]],
                    back=[fb['tip_phi'], fb['tip_uz'][1]])
    # call H read by the tips: each named flick's region in front and back; our locks whose tip lies on it (within
    # three line widths: the truth stops at the outline's ink); is any of those front locks linked to any of those back locks?
    print('call H by the tips (our locks whose tips lie on the truth flick, front and back; linked?):')
    from scipy import ndimage
    Ht = {}
    for q in ('flyaways/flick_L1', 'flyaways/flick_L2', 'flyaways/flick_R1', 'flyaways/flick_R2', 'lower_back/flick_L3',
              'lower_back/flick_R3', 'flyaways/under_bun_L', 'flyaways/under_bun_R'):
        on = {}
        for v in ('front', 'back'):
            if q not in T[1][v]:
                continue
            S = splits[v]
            r0, r1, c0, c1 = S.box
            reg = ndimage.binary_dilation(T[0][v][r0:r1, c0:c1] == T[1][v].index(q), iterations=int(3 * S.lw))
            on[v] = [l_ for l_, x in S.lock_info.items()
                     if x['tip'] == 'drawn' and reg[int(round(x['tip_rc'][0])), int(round(x['tip_rc'][1]))]]
        pairs_ = [(L['ours'][0], L['ours'][1]) for L in links if L['views'] == ['front', 'back']]
        hit = [(a_, b_) for a_, b_ in pairs_ if a_ in on.get('front', []) and b_ in on.get('back', [])]
        Ht[q] = dict(front=on.get('front'), back=on.get('back'), linked=hit)
        print('  %-22s front tips %s  back tips %s  linked %s' % (q, on.get('front'), on.get('back'), hit))
    # call H at the tips themselves: detected tips on each named flick (front and back), linked by the tip matcher?
    TIP_TOL = 5
    print('call H, tip to tip (detected tips within %d line widths of the truth flick; the tip matcher links them?):' % TIP_TOL)
    tm = [m for m in getattr(shell, 'tip_matches', []) if m['views'] == ['front', 'back']]
    tpairs = {(a_, b_): c for m in tm for a_, b_, c in m['pairs']}
    Htt = {}
    for q in ('flyaways/flick_L1', 'flyaways/flick_L2', 'flyaways/flick_R1', 'flyaways/flick_R2', 'lower_back/flick_L3',
              'lower_back/flick_R3', 'flyaways/under_bun_L', 'flyaways/under_bun_R'):
        on = {}
        for v in ('front', 'back'):
            if q not in T[1][v]:
                continue
            S = splits[v]
            r0, r1, c0, c1 = S.box
            reg = ndimage.binary_dilation(T[0][v][r0:r1, c0:c1] == T[1][v].index(q), iterations=int(TIP_TOL * S.lw))
            on[v] = [i for i, t in enumerate(S.tip_list) if reg[int(round(t['rc'][0])), int(round(t['rc'][1]))]]
        hit = [(a_, b_, c) for (a_, b_), c in tpairs.items() if a_ in on.get('front', []) and b_ in on.get('back', [])]
        other = [(a_, b_, c) for (a_, b_), c in tpairs.items() if (a_ in on.get('front', [])) != (b_ in on.get('back', []))]
        Htt[q] = dict(front=on.get('front'), back=on.get('back'), linked=hit, linked_elsewhere=other)
        zs = lambda v, ii: [round(splits[v].uz(splits[v].tip_list[i]['rc'])[1], 3) for i in ii]
        print('  %-22s front tips %s z %s | back tips %s z %s | linked %s | linked elsewhere %s' % (
            q, on.get('front'), zs('front', on.get('front', [])), on.get('back'), zs('back', on.get('back', [])), hit, other))
    json.dump(dict(call_H_tip_to_tip=Htt, call_H_tips=Ht, links=links, precision=right / max(1, judged), recall=len(got & want) / max(1, len(want)),
                   call_H=H, shell=shell.check, matches=matches), open(a[0], 'w'), indent=1)
