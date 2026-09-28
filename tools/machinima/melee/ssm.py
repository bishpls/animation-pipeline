"""Parse and decode HAL .ssm sound banks (Melee): mono or stereo DSP-ADPCM, every sound to a 16-bit WAV at its own rate.
    .venv/bin/python tools/machinima/melee/ssm.py BANK.ssm OUT_DIR      # -> OUT_DIR/<bank>_<index>_id<sample id>.wav
Header layout verified against file sizes (all 110 banks, US and JP): u32 entry-table length, data length, sound count,
base sample id; per sound u32 channels, rate, then 0x40 bytes per channel (loop flag, format, loop/end/start nibble,
16 coefficients, gain, predictor/scale, history); the data at align32(table + 0x10). Decoded audio is game-derived: keep
it outside the repo. SO BACK decoded the announcer banks with it (projects/so-back/vocals/decode_banks.sh)."""
import struct, numpy as np, sys, os, wave

def parse(path):
    b = open(path, 'rb').read()
    hlen, dlen, count, start = struct.unpack('>4I', b[:16])
    data_off = hlen + 0x10
    if data_off % 0x20: data_off += 0x20 - data_off % 0x20
    assert data_off + dlen == len(b), (hex(data_off), hex(dlen), hex(len(b)))
    off = 0x10
    sounds = []
    for i in range(count):
        nch, rate = struct.unpack('>2I', b[off:off+8]); off += 8
        chans = []
        for c in range(nch):
            loopflag, fmt, lstart, end, cur = struct.unpack('>2H3I', b[off:off+16])
            coefs = struct.unpack('>16h', b[off+16:off+48])
            gain, ps, yn1, yn2, lps, lyn1, lyn2, pad = struct.unpack('>H H h h H h h H', b[off+48:off+64])
            chans.append(dict(loop=loopflag, fmt=fmt, lstart=lstart, end=end, cur=cur, coefs=coefs,
                              gain=gain, ps=ps, yn1=yn1, yn2=yn2, lps=lps, hdr_off=off))
            off += 64
        sounds.append(dict(index=i, id=start + i, nch=nch, rate=rate, chans=chans))
    return dict(hlen=hlen, dlen=dlen, count=count, start=start, data_off=data_off, sounds=sounds, raw=b)

def decode_channel(bank, ch):
    """cur/end are nibble addresses into the data region (frame = 8 bytes = 16 nibbles, first 2 = header)."""
    data = bank['raw'][bank['data_off']:]
    coefs = np.array(ch['coefs']).reshape(8, 2)
    start_n, end_n = ch['cur'], ch['end']
    out = []
    h1, h2 = ch['yn1'], ch['yn2']
    n = start_n
    # start at frame boundary containing start_n
    frame = (start_n // 16)
    pos = frame * 16
    while pos <= end_n:
        fb = frame * 8
        hdr = data[fb]
        scale = 1 << (hdr & 0xF)
        c1, c2 = coefs[(hdr >> 4) & 0x7]
        for k in range(14):
            nib_addr = pos + 2 + k
            if nib_addr > end_n: break
            byte = data[fb + 1 + k // 2]
            nib = (byte >> 4) if k % 2 == 0 else (byte & 0xF)
            if nib >= 8: nib -= 16
            s = ((nib * scale) << 11) + 1024 + c1 * h1 + c2 * h2
            s >>= 11
            s = max(-32768, min(32767, s))
            h2, h1 = h1, s
            if nib_addr >= start_n: out.append(s)
        frame += 1; pos = frame * 16
    return np.array(out, dtype=np.int16)

def write_wav(path, x, rate):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1 if x.ndim == 1 else x.shape[1]); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(x.astype('<i2').tobytes())

if __name__ == '__main__':
    path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    bank = parse(path)
    name = os.path.basename(path).replace('.ssm', '')
    print(f"{name}: count={bank['count']} start_id={bank['start']} (0x{bank['start']:x}) hlen=0x{bank['hlen']:x} dlen=0x{bank['dlen']:x}")
    for s in bank['sounds']:
        chans = [decode_channel(bank, c) for c in s['chans']]
        x = chans[0] if len(chans) == 1 else np.stack(chans, 1)
        fn = f"{outdir}/{name}_{s['index']:02d}_id{s['id']}.wav"
        write_wav(fn, x, s['rate'])
        c = s['chans'][0]
        print(f"  [{s['index']:2d}] id={s['id']} ch={s['nch']} rate={s['rate']} loop={c['loop']} fmt={c['fmt']} dur={len(chans[0])/s['rate']:.3f}s")
