"""(The splice engine from an earlier name-call splice; only `load` changed.)
Concatenative splicer for the Melee announcer: cut real recorded segments, PSOLA each voiced segment to a
template pitch contour/duration (Praat overlap-add via parselmouth, pulses placed from our robust F0), align
the joins pitch-synchronously, crossfade at zero crossings, and level-match. No synthesis: every sample comes
from the announcer's own recordings (only cut, time/pitch-scaled by PSOLA, gain-adjusted and crossfaded)."""
import numpy as np, soundfile as sf, parselmouth
from parselmouth.praat import call
from dataclasses import dataclass, field
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from hf0 import hf0

SR = 12000
from common import load   # SO BACK: sources are announcer registry keys (common.REG) or paths

@dataclass
class Seg:
    src: str            # source clip name in src/
    t0: float           # core start (s) in source
    t1: float           # core end (s) in source
    dur: float = None   # target output duration of the core (None = unchanged)
    pitch: list = None  # [(pos 0..1 within core, Hz), ...] target contour; None = leave pitch as recorded
    gain_db: float = 0.0
    floor: float = 140  # F0 range for pulse marking
    ceil: float = 480
    label: str = ''
    keep_jitter: bool = True   # keep the recording's own micro-prosody (only the trend is moved to the template)
    dur_tier: list = None      # [(pos 0..1 within core, factor), ...] piecewise-linear duration factor (overrides dur)
    fade_out: float = 0.0      # s: decay the last fade_out of the core (for trims), -70 dB/s then cos^2 to zero

def _pitch_obj_from_hf0(snd, floor, ceil):
    """Praat Pitch object built from our harmonic-sum tracker (robust to this voice's octave traps)."""
    x = snd.values[0]
    t, f0, sc, v = hf0(x, SR, hop=0.005, fmin=floor, fmax=ceil)
    pt = call('Create PitchTier', 'p', snd.xmin, snd.xmax)
    for tt, ff, vv in zip(t, f0, v):
        if vv:
            call(pt, 'Add point', snd.xmin + tt, float(ff))
    if call(pt, 'Get number of points') < 2:
        return None
    return call(pt, 'To Pitch', 0.005, floor, ceil)

def psola(x, pitch_pts=None, factor=1.0, floor=140, ceil=480, core=(0, None), dur_pts=None):
    """PSOLA x (numpy) to pitch points [(t_sec_in_x, Hz)] and constant duration factor on the core span."""
    snd = parselmouth.Sound(x, SR)
    manip = call(snd, 'To Manipulation', 0.005, floor, ceil)
    p = _pitch_obj_from_hf0(snd, floor, ceil)
    if p is not None:
        pulses = call([snd, p], 'To PointProcess (cc)')
        call([manip, pulses], 'Replace pulses')
    if pitch_pts is None and p is not None:
        # duration-only edit: keep the recorded pitch as *our* tracker sees it. (Praat's own analysis in the
        # Manipulation octave-jumps on this voice's creaky low tails, and PSOLA would then move them an octave.)
        call([call(p, 'Down to PitchTier'), manip], 'Replace pitch tier')
    if pitch_pts is not None:
        pt = call('Create PitchTier', 'target', snd.xmin, snd.xmax)
        for t, f in pitch_pts:
            call(pt, 'Add point', float(t), float(f))
        call([pt, manip], 'Replace pitch tier')
    if dur_pts is not None:
        dt = call('Create DurationTier', 'd', snd.xmin, snd.xmax)
        for t, f in dur_pts:
            call(dt, 'Add point', float(t), float(f))
        call([dt, manip], 'Replace duration tier')
    elif abs(factor - 1.0) > 1e-3:
        c0, c1 = core
        c1 = snd.xmax if c1 is None else c1
        dt = call('Create DurationTier', 'd', snd.xmin, snd.xmax)
        call(dt, 'Add point', max(snd.xmin, c0 - 0.0005), 1.0)
        call(dt, 'Add point', c0 + 0.0005, factor)
        call(dt, 'Add point', c1 - 0.0005, factor)
        call(dt, 'Add point', min(snd.xmax, c1 + 0.0005), 1.0)
        call([dt, manip], 'Replace duration tier')
    parselmouth.praat.run('random_initializeWithSeedUnsafelyButPredictably (1)')   # SO BACK: reproducible unvoiced PSOLA
    out = call(manip, 'Get resynthesis (overlap-add)')
    return out.values[0].copy()

def render_seg(s: Seg, margin):
    """Returns (y, pre, post): y includes `pre` samples before and `post` after the (processed) core."""
    x = load(s.src)
    a = int(round(s.t0 * SR)); b = int(round(s.t1 * SR))
    m = int(round(margin * SR))
    lo = max(0, a - m); hi = min(len(x), b + m)
    y = x[lo:hi].copy()
    pre, post = a - lo, hi - b
    core_len = b - a
    factor = 1.0 if s.dur is None else s.dur * SR / core_len
    dur_pts = None
    if s.dur_tier is not None:
        c0, c1 = pre / SR, (pre + core_len) / SR
        dur_pts = [(0.0, 1.0), (max(0.0, c0 - 0.0005), 1.0)] + \
                  [(c0 + p * (c1 - c0), f) for p, f in s.dur_tier] + [(c1 + 0.0005, 1.0), (len(y) / SR, 1.0)]
    if s.pitch is not None or abs(factor - 1) > 1e-3 or dur_pts is not None:
        c0, c1 = pre / SR, (pre + core_len) / SR
        pts = None
        if s.pitch is not None:
            pp = np.array(s.pitch, float)
            def templ(tt):  # template in Hz at source time tt (flat over the margins)
                return np.interp((tt - c0) / (c1 - c0), pp[:, 0], pp[:, 1])
            if s.keep_jitter:
                tt, f0, sc, v = hf0(y, SR, hop=0.005, fmin=s.floor, fmax=s.ceil)
                k = v & (tt > 0.01) & (tt < len(y) / SR - 0.01)
                if k.sum() >= 6:
                    lf = np.log(f0[k]); tk = tt[k]
                    # trend = 45 ms moving average of log F0 over voiced frames
                    trend = np.array([lf[np.abs(tk - t) <= 0.0225].mean() for t in tk])
                    tgt = np.exp(np.clip(lf - trend, -0.04, 0.04)) * templ(tk)  # keep micro-prosody, cap at +-4%
                    pts = [(0.0, float(templ(0.0)))] + list(zip(tk, tgt)) + [(len(y) / SR, float(templ(len(y) / SR)))]
                else:
                    pts = None
            else:
                pts = None
            if pts is None:
                pts = [(c0 + p * (c1 - c0), f) for p, f in s.pitch]
                pts = [(0.0, s.pitch[0][1])] + pts + [(len(y) / SR, s.pitch[-1][1])]
        y = psola(y, pts, factor, s.floor, s.ceil, core=(c0, c1), dur_pts=dur_pts)
        # margins keep factor 1, so their lengths are preserved; core is scaled
        new_core = len(y) - pre - post
    y = y * 10 ** (s.gain_db / 20)
    if s.fade_out > 0:
        n = int(s.fade_out * SR); e = len(y) - post
        t = np.arange(n) / SR
        env = 10 ** (-70 * t / 20) * np.cos(np.linspace(0, np.pi / 2, n)) ** 2
        y[e - n:e] *= env; y[e:] = 0
    return y, pre, post

def local_period(y, i, fmin=140, fmax=480):
    n = int(0.03 * SR); seg = y[max(0, i - n // 2): i + n // 2]
    if len(seg) < n // 2: return int(SR / 250)
    seg = seg - seg.mean(); ac = np.correlate(seg, seg, 'full')[len(seg) - 1:]
    lo, hi = int(SR / fmax), int(SR / fmin)
    if hi >= len(ac): return int(SR / 250)
    return lo + int(np.argmax(ac[lo:hi]))

def join(a, b, a_end, b_start, xf, align=True, max_shift=None):
    """Overlap-add b onto a: a's content up to a_end (sample idx) continues for xf/2 past it; b's content from
    b_start - xf/2. Aligns b by cross-correlation within +-half a period, snaps to a zero crossing, then fades."""
    h = xf // 2
    if align:
        P = local_period(a, a_end)
        ms = P // 2 if max_shift is None else max_shift
        ref = a[a_end - h: a_end + h]
        best, bs = -1e9, 0
        for sh in range(-ms, ms + 1):
            c = b[b_start - h + sh: b_start + h + sh]
            if len(c) != len(ref) or b_start - h + sh < 0: continue
            v = np.dot(ref, c) / (np.linalg.norm(ref) * np.linalg.norm(c) + 1e-9)
            if v > best: best, bs = v, sh
        b_start += bs
    # snap the fade centre to a zero crossing of a (within 1 ms)
    w = int(0.001 * SR)
    zc = [i for i in range(a_end - w, a_end + w) if 0 < i < len(a) and a[i - 1] <= 0 < a[i]]
    if zc:
        d = min(zc, key=lambda i: abs(i - a_end)) - a_end
        a_end += d; b_start += d
    # correlation-adaptive fade: raised-cosine gains normalised so that fo^2 + fi^2 + 2 r fo fi = 1, where r is the
    # correlation of the two (aligned) overlaps: r=1 -> amplitude-complementary, r=0 -> equal-power. Avoids both the
    # +3 dB bump of equal-power fades on correlated audio and the dip of linear fades between unlike sounds.
    oa = a[a_end - h:a_end + h]; ob = b[b_start - h:b_start + h]
    r = float(np.clip(np.dot(oa, ob) / (np.linalg.norm(oa) * np.linalg.norm(ob) + 1e-9), 0.0, 1.0))
    u = np.sin(np.linspace(0, np.pi / 2, 2 * h)) ** 2
    fo, fi = 1 - u, u
    norm = np.sqrt(fo ** 2 + fi ** 2 + 2 * r * fo * fi)
    fo, fi = fo / norm, fi / norm
    head = a[:a_end - h]
    mix = a[a_end - h:a_end + h] * fo + b[b_start - h:b_start + h] * fi
    tail = b[b_start + h:]
    return np.concatenate([head, mix, tail]), a_end, a_end - b_start  # join centre, offset of b in output

def build(segs, xfades, margin=0.04, lead=0.012):
    """segs: list of Seg; xfades: crossfade length (s) for each join (len(segs)-1).
    Returns (y, joins, spans): joins = output times (s) of each seam; spans = output (start,end) of each core."""
    rendered = [render_seg(s, margin) for s in segs]
    y, pre, post = rendered[0]
    L = min(pre, int(lead * SR))
    out = y[pre - L:].copy()
    out[:L] *= np.linspace(0, 1, L) if L else 1
    out_core_end = len(y) - post - (pre - L)
    spans = [(L / SR, out_core_end / SR)]
    joins = []
    for (yb, preb, postb), xf in zip(rendered[1:], xfades):
        xs = int(round(xf * SR)) // 2 * 2
        xs = max(2, min(xs, 2 * min(preb, len(out) - out_core_end) - 2))
        out, jc, off = join(out, yb, out_core_end, preb, xs)
        out_core_end = off + len(yb) - postb
        spans.append((jc / SR, out_core_end / SR))
        joins.append(jc / SR)
    return out, joins, spans

def lufs_like(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)

def finish(y, peak=0.87):
    y = y - np.mean(y)
    return y * (peak / (np.abs(y).max() + 1e-12))

def write(path, y):
    sf.write(path, np.clip(y, -1, 1), SR, subtype='PCM_16')
