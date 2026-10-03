"""Nintendo GameCube DSP-ADPCM encoder and decoder (used by hps.py; also what built Geno's geno.ssm sound bank).

A line-by-line Python port of the reference algorithm as published in jackoalan/gc-dspadpcm-encode (grok.c:
DSPCorrelateCoefs + DSPEncodeFrame; MIT licence), which reproduces Nintendo's DSPADPCM tool. C integer semantics are
kept exactly (truncating division, arithmetic shifts, lround, the 0.4999999f rounding constant, the negative-index
history reads of the 2-D PCM buffer).

API:
    coefs = correlate_coefs(pcm_int16)                  # 8 x (c1, c2) as ints
    data, info = encode(pcm_int16)                       # bytes (frames * 8) + header fields (ps, nibbles, ...)
    pcm = decode(data, coefs, n, yn1=0, yn2=0)           # int16
"""
import math, struct
import numpy as np

DBL_EPSILON = 2.220446049250313e-16
F_0_4999999 = float(np.float32(0.4999999))   # the C source uses the float literal 0.4999999f

def _cdiv(a, b):                     # C integer division (truncate toward zero)
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q

def _fdiv(a, b):
    """IEEE-754 double division as C does it (x/0 = +-inf, 0/0 = nan) instead of raising. In _matrix_filter a zero
    divisor only occurs for i == 1, whose result lands in the unused row mtx[0]; the C reference stores inf there."""
    if b != 0.0:
        return a / b
    if a == 0.0 or a != a:
        return float('nan')
    return math.copysign(float('inf'), a) * math.copysign(1.0, b)

def _lround(d):                      # C lround: half away from zero
    return int(math.floor(d + 0.5)) if d >= 0 else -int(math.floor(-d + 0.5))

# ----------------------------------------------------------------------------------------------- coefficients
def _inner_product_merge(buf, o):
    # vecOut[i] = -sum_x pcmBuf[x-i]*pcmBuf[x], pcmBuf = buf[o:], negative indices read the previous frame
    v = [0.0, 0.0, 0.0]
    for i in range(3):
        acc = 0.0
        for x in range(14):
            acc -= buf[o + x - i] * buf[o + x]
        v[i] = acc
    return v

def _outer_product_merge(buf, o):
    m = [[0.0] * 3 for _ in range(3)]
    for x in range(1, 3):
        for y in range(1, 3):
            acc = 0.0
            for z in range(14):
                acc += buf[o + z - x] * buf[o + z - y]
            m[x][y] = acc
    return m

def _analyze_ranges(mtx, idx):
    recips = [0.0, 0.0, 0.0]
    for x in range(1, 3):
        val = max(abs(mtx[x][1]), abs(mtx[x][2]))
        if val < DBL_EPSILON:
            return True
        recips[x] = 1.0 / val
    max_index = 0
    for i in range(1, 3):
        for x in range(1, i):
            tmp = mtx[x][i]
            for y in range(1, x):
                tmp -= mtx[x][y] * mtx[y][i]
            mtx[x][i] = tmp
        val = 0.0
        for x in range(i, 3):
            tmp = mtx[x][i]
            for y in range(1, i):
                tmp -= mtx[x][y] * mtx[y][i]
            mtx[x][i] = tmp
            tmp = abs(tmp) * recips[x]
            if tmp >= val:
                val = tmp
                max_index = x
        if max_index != i:
            for y in range(1, 3):
                mtx[max_index][y], mtx[i][y] = mtx[i][y], mtx[max_index][y]
            recips[max_index] = recips[i]
        idx[i] = max_index
        if mtx[i][i] == 0.0:
            return True
        if i != 2:
            tmp = 1.0 / mtx[i][i]
            for x in range(i + 1, 3):
                mtx[x][i] *= tmp
    mn, mx = 1.0e10, 0.0
    for i in range(1, 3):
        tmp = abs(mtx[i][i])
        mn = min(mn, tmp); mx = max(mx, tmp)
    return mn / mx < 1.0e-10

def _bidirectional_filter(mtx, idx, v):
    x = 0
    for i in range(1, 3):
        index = idx[i]
        tmp = v[index]
        v[index] = v[i]
        if x != 0:
            for y in range(x, i):
                tmp -= v[y] * mtx[i][y]
        elif tmp != 0.0:
            x = i
        v[i] = tmp
    for i in range(2, 0, -1):
        tmp = v[i]
        for y in range(i + 1, 3):
            tmp -= v[y] * mtx[i][y]
        v[i] = tmp / mtx[i][i]
    v[0] = 1.0

def _quadratic_merge(v):
    v2 = v[2]
    tmp = 1.0 - v2 * v2
    if tmp == 0.0:
        return True
    v0 = (v[0] - v2 * v2) / tmp
    v1 = (v[1] - v[1] * v2) / tmp
    v[0] = v0; v[1] = v1
    return abs(v1) > 1.0

def _finish_record(inv, out):
    for z in range(1, 3):
        if inv[z] >= 1.0:
            inv[z] = 0.9999999999
        elif inv[z] <= -1.0:
            inv[z] = -0.9999999999
    out[0] = 1.0
    out[1] = inv[2] * inv[1] + inv[1]
    out[2] = inv[2]

def _matrix_filter(src, dst):
    mtx = [[0.0] * 3 for _ in range(3)]
    mtx[2][0] = 1.0
    for i in range(1, 3):
        mtx[2][i] = -src[i]
    for i in range(2, 0, -1):
        val = 1.0 - mtx[i][i] * mtx[i][i]
        for y in range(1, i + 1):
            mtx[i - 1][y] = _fdiv(mtx[i][i] * mtx[i][y] + mtx[i][y], val)
    dst[0] = 1.0
    for i in range(1, 3):
        dst[i] = 0.0
        for y in range(1, i + 1):
            dst[i] += mtx[i][y] * dst[i - y]

def _merge_finish_record(src, dst):
    tmp = [0.0, 0.0, 0.0]
    val = src[0]
    dst[0] = 1.0
    for i in range(1, 3):
        v2 = 0.0
        for y in range(1, i):
            v2 += dst[y] * src[i - y]
        dst[i] = -(v2 + src[i]) / val if val > 0.0 else 0.0
        tmp[i] = dst[i]
        for y in range(1, i):
            dst[y] += dst[i] * dst[i - y]
        val *= 1.0 - dst[i] * dst[i]
    _finish_record(tmp, dst)

def _contrast_vectors(s1, s2):
    val = (s2[2] * s2[1] + -s2[1]) / (1.0 - s2[2] * s2[2])
    val1 = s1[0] * s1[0] + s1[1] * s1[1] + s1[2] * s1[2]
    val2 = s1[0] * s1[1] + s1[1] * s1[2]
    val3 = s1[0] * s1[2]
    return val1 + 2.0 * val * val2 + 2.0 * (-s2[1] * val + -s2[2]) * val3

def _filter_records(best, exp, records):
    buf2 = [0.0, 0.0, 0.0]
    for _ in range(2):
        counts = [0] * 8
        blist = [[0.0, 0.0, 0.0] for _ in range(8)]
        for rec in records:
            index = 0; value = 1.0e30
            for i in range(exp):
                t = _contrast_vectors(best[i], rec)
                if t < value:
                    value = t; index = i
            counts[index] += 1
            _matrix_filter(rec, buf2)
            for i in range(3):
                blist[index][i] += buf2[i]
        for i in range(exp):
            if counts[i] > 0:
                for y in range(3):
                    blist[i][y] /= counts[i]
        for i in range(exp):
            _merge_finish_record(blist[i], best[i])

def correlate_coefs(pcm):
    pcm = [int(v) for v in pcm]
    samples = len(pcm)
    block = [0] * 0x3800
    hist = [0] * 28                    # pcmHistBuffer[2][14], contiguous: [prev 14 | current 14]
    records = []
    src = 0
    x = samples
    while x > 0:
        if x > 0x3800:
            frame_samples = 0x3800; x -= 0x3800
        else:
            frame_samples = x
            z = 0
            while z < 14 and z + frame_samples < 0x3800:
                block[frame_samples + z] = 0; z += 1
            x = 0
        block[:frame_samples] = pcm[src:src + frame_samples]
        src += frame_samples
        i = 0
        while i < frame_samples:
            hist[0:14] = hist[14:28]
            hist[14:28] = block[i:i + 14]
            i += 14
            v1 = _inner_product_merge(hist, 14)
            if abs(v1[0]) > 10.0:
                mtx = _outer_product_merge(hist, 14)
                idx = [0, 0, 0]
                if not _analyze_ranges(mtx, idx):
                    _bidirectional_filter(mtx, idx, v1)
                    if not _quadratic_merge(v1):
                        rec = [0.0, 0.0, 0.0]
                        _finish_record(v1, rec)
                        records.append(rec)
    v1 = [1.0, 0.0, 0.0]
    best = [[0.0, 0.0, 0.0] for _ in range(8)]
    for rec in records:
        _matrix_filter(rec, best[0])
        for y in range(1, 3):
            v1[y] += best[0][y]
    for y in range(1, 3):
        v1[y] /= len(records)            # (as in the C source; a silent clip would divide by zero there too)
    _merge_finish_record(v1, best[0])
    exp = 1
    w = 0
    while w < 3:
        v2 = [0.0, -1.0, 0.0]
        for i in range(exp):
            for y in range(3):
                best[exp + i][y] = 0.01 * v2[y] + best[i][y]
        w += 1
        exp = 1 << w
        _filter_records(best, exp, records)
    coefs = []
    for z in range(8):
        pair = []
        for k in (1, 2):
            d = -best[z][k] * 2048.0
            if d > 0.0:
                pair.append(32767 if d > 32767.0 else _lround(d))
            else:
                pair.append(-32768 if d < -32768.0 else _lround(d))
        coefs.append(tuple(pair))
    return coefs

# ------------------------------------------------------------------------------------------------ frames
def encode_frame(pcm16, sample_count, coefs):
    """pcm16: list of 16 ints (yn2, yn1, then 14 samples). Returns (8 bytes, updated pcm16 with decoded samples)."""
    in_s = [[0] * 16 for _ in range(8)]
    out_s = [[0] * 14 for _ in range(8)]
    scale = [0] * 8
    dist_acc = [0.0] * 8
    for i in range(8):
        c1, c2 = coefs[i]
        in_s[i][0] = pcm16[0]; in_s[i][1] = pcm16[1]
        distance = 0
        for s in range(sample_count):
            v1 = _cdiv(pcm16[s] * c2 + pcm16[s + 1] * c1, 2048)
            in_s[i][s + 2] = v1
            v2 = pcm16[s + 2] - v1
            v3 = 32767 if v2 >= 32767 else (-32768 if v2 <= -32768 else v2)
            if abs(v3) > abs(distance):
                distance = v3
        sc = 0
        while sc <= 12 and (distance > 7 or distance < -8):
            sc += 1; distance = _cdiv(distance, 2)
        scale[i] = -1 if sc <= 1 else sc - 2
        while True:
            scale[i] += 1
            dist_acc[i] = 0.0
            index = 0
            for s in range(sample_count):
                v1 = in_s[i][s] * c2 + in_s[i][s + 1] * c1
                v2 = _cdiv((pcm16[s + 2] << 11) - v1, 2048)
                q = v2 / (1 << scale[i])
                v3 = int(q + F_0_4999999) if v2 > 0 else int(q - F_0_4999999)   # int() truncates like a C cast
                if v3 < -8:
                    t = -8 - v3
                    if index < t: index = t
                    v3 = -8
                elif v3 > 7:
                    t = v3 - 7
                    if index < t: index = t
                    v3 = 7
                out_s[i][s] = v3
                v1 = (v1 + ((v3 * (1 << scale[i])) << 11) + 1024) >> 11
                v2 = 32767 if v1 >= 32767 else (-32768 if v1 <= -32768 else v1)
                in_s[i][s + 2] = v2
                v3 = pcm16[s + 2] - v2
                dist_acc[i] += v3 * float(v3)
            xx = index + 8
            while xx > 256:
                scale[i] += 1
                if scale[i] >= 12:
                    scale[i] = 11
                xx >>= 1
            if not (scale[i] < 12 and index > 1):
                break
    best = 0; mn = float('inf')
    for i in range(8):
        if dist_acc[i] < mn:
            mn = dist_acc[i]; best = i
    out = list(pcm16)
    for s in range(sample_count):
        out[s + 2] = in_s[best][s + 2]
    b = bytearray(8)
    b[0] = ((best << 4) | (scale[best] & 0xF)) & 0xFF
    for s in range(sample_count, 14):
        out_s[best][s] = 0
    for y in range(7):
        b[y + 1] = ((out_s[best][y * 2] << 4) | (out_s[best][y * 2 + 1] & 0xF)) & 0xFF
    return bytes(b), out

def nibbles_for(n):
    return (n // 14) * 16 + ((n % 14) + 2 if n % 14 else 0)

def encode(pcm, coefs=None):
    """Encode int16 PCM the way gc-dspadpcm-encode's main() does: 14-sample frames, the last one zero-padded,
    history carried from the previous frame's decoded samples. Returns (bytes, info dict)."""
    pcm = [int(v) for v in pcm]
    if coefs is None:
        coefs = correlate_coefs(pcm)
    n = len(pcm)
    frames = -(-n // 14)
    conv = [0] * 16
    out = bytearray()
    for p in range(frames):
        chunk = pcm[p * 14:p * 14 + 14]
        conv[2:16] = chunk + [0] * (14 - len(chunk))
        blk, conv = encode_frame(conv, 14, coefs)
        out += blk
        conv[0] = conv[14]; conv[1] = conv[15]
    info = dict(num_samples=n, num_nibbles=nibbles_for(n), coefs=coefs, ps=out[0], yn1=0, yn2=0, frames=frames)
    return bytes(out), info

def dsp_header(info, rate=12000):
    """Standard 0x60-byte .dsp header (big-endian), as written by DSPADPCM / gc-dspadpcm-encode."""
    h = struct.pack('>IIIHHIII', info['num_samples'], info['num_nibbles'], rate, 0, 0, 2, info['num_nibbles'] - 1, 2)
    h += struct.pack('>16h', *[c for pair in info['coefs'] for c in pair])
    h += struct.pack('>HHhhHhh', 0, info['ps'], 0, 0, 0, 0, 0)
    return h + b'\0' * (0x60 - len(h))

def decode(data, coefs, n, yn1=0, yn2=0):
    """Standard DSP-ADPCM decode (same arithmetic as tools/ssm.py and the AX DSP)."""
    out = np.zeros(n, dtype=np.int16); h1, h2 = yn1, yn2; k = 0
    for f in range(-(-n // 14)):
        hdr = data[f * 8]; sc = 1 << (hdr & 0xF); c1, c2 = coefs[(hdr >> 4) & 7]
        for j in range(14):
            if k >= n: break
            b = data[f * 8 + 1 + j // 2]
            nib = (b >> 4) if j % 2 == 0 else (b & 0xF)
            if nib >= 8: nib -= 16
            s = (((nib * sc) << 11) + 1024 + c1 * h1 + c2 * h2) >> 11
            s = max(-32768, min(32767, s))
            h2, h1 = h1, s; out[k] = s; k += 1
    return out

def snr_db(ref, test):
    ref = np.asarray(ref, float); test = np.asarray(test, float)
    return 10 * np.log10(np.sum(ref ** 2) / max(np.sum((ref - test) ** 2), 1e-12))
