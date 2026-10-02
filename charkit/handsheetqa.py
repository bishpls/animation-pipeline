"""The hand against its hand sheet (tool/hands2 round 6; docs/workstreams/hands.md, the reframing, Michael 2026-10-01):
the build's hand template (charkit.code_hand from the build's spec, as the build makes it) posed into the sheet's poses
by the pose library (charkit.handposes: the template's own weights) and drawn as the sheet draws it (charkit.handsheet),
its structure read off landmarks with the thumb left out. The palm page's widths read the silhouette across the arm, so a
thumb crossing the line counted as palm: the structure checks here read the webs between the fingers, which a thumb
moved alone can't move (calibrated with an invariant: calib/handsheet.py's thumb_only).

Checks (QA part 'hand_sheet', prefix handsheet_; shares of the palm length PL, the wrist line to the middle MCP):
  handsheet_open_span     the MCP span (4 x the webs' mean spacing: the four fingers tile the knuckle row) over PL on
                          the open hand, ours minus the sheet's
  handsheet_open_fingers  the fingers on the open hand: the middle's length over PL and the index's, ring's and
                          little's over the middle's, the largest |ours - sheet's|
  handsheet_{pose}_{row}  INFO: the posed hand's silhouette IoU with the sheet's (the pose's validation, not the
                          structure's fit), its tips beside the sheet's

    T, C = handsheetqa.measure(B, design)          # the 'hand_sheet' QA part
"""
import numpy as np

from .registry import qa_part

LIMITS = {'span': (0.05, 0.10), 'fingers': (0.05, 0.10)}
POSES = ('open', 'relaxed', 'fist', 'point')


def ratios_of(h):
    """an open hand's structural ratios off its landmarks (charkit.handsheet.ratios_of: the four fingers and their three
    webs; the thumb optional) -> dict or None."""
    from . import handsheet
    return handsheet.ratios_of(h)


def ours(B, poses=POSES):
    """our hand drawn on the sheet's terms per (pose, row) -> {(pose, row): h} (handsheet.draw's dicts), from the build's
    spec's hand (code_hand.params) posed by the pose library at one scale per row (handposes.PoseGrade's: the open
    hand's reach)."""
    from . import handposes
    G = handposes.PoseGrade(spec=B.spec)
    out = {}
    for p in poses:
        for row in ('back', 'side'):
            out[(p, row)] = G.ours(handposes.POSES[p], row)[0]
    return out


def sheet():
    """the sheet's hands -> {(pose, row): h} (handsheet.cells)."""
    from . import handsheet
    return handsheet.cells()


@qa_part('hand_sheet', order=1786, prefix='handsheet_', table='hand_sheet', checks=2 + 2 * len(POSES))
def hand_sheet(B, design=None, out=None):
    return measure(B, design, out)


def measure(B, design=None, out=None):
    from . import handqa
    S, O = sheet(), ours(B)
    rs, ro = ratios_of(S[('open', 'back')]), ratios_of(O[('open', 'back')])
    T = dict(open=dict(sheet=rs, ours=ro))
    C = {}
    if rs is None:
        C['open_span'] = C['open_fingers'] = {'status': 'SKIPPED', 'why': "the sheet's open hand: its webs not found"}
    elif ro is None:
        C['open_span'] = C['open_fingers'] = {'value': None, 'status': 'FAIL',
                                              'why': 'our open hand shows fewer than four fingers or three webs'}
    else:
        d = ro['span'] - rs['span']
        C['open_span'] = {'value': round(d, 4), 'status': _grade('span', d), 'ours': round(ro['span'], 4),
                          'design': round(rs['span'], 4),
                          'note': "the MCP span (4 x the webs' spacing: the thumb not in it) over the palm length on "
                                  "the open hand, ours minus the hand sheet's"}
        diffs = {k: ro[k] - rs[k] for k in ('middle', 'index', 'ring', 'little')}
        k = max(diffs, key=lambda x: abs(diffs[x]))
        C['open_fingers'] = {'value': round(diffs[k], 4), 'status': _grade('fingers', diffs[k]), 'worst': k,
                             'ours': {x: round(ro[x], 4) for x in diffs}, 'design': {x: round(rs[x], 4) for x in diffs},
                             'note': "the fingers on the open hand (the middle over the palm length, the others over "
                                     "the middle), the largest ours minus the hand sheet's"}
    for (p, row), h in sorted(O.items()):
        cell = S.get((p, row))
        if cell is None:
            continue
        iou = handqa.shape_iou(cell['mask'], h['mask'])
        C['%s_%s' % (p, row)] = {'value': round(iou, 4), 'status': 'INFO',
                                 'note': "the posed hand's silhouette IoU with the hand sheet's (the pose's validation; "
                                         "the structure is the landmark checks')"}
    return T, C


def _grade(k, v):
    p, w = LIMITS[k]
    v = abs(v)
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'
