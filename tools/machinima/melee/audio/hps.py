"""Melee's HALPST (.hps) streamed-music container: read, write, inspect and round-trip check.

HAL's stream format (Melee's BGM and victory fanfares, `files/audio/*.hps`), as laid out in the vanilla files:

  0x00  " HALPST\\0"
  0x08  u32 sample rate (32000 in every vanilla fanfare)
  0x0C  u32 channel count (2)
  0x10  per channel, 0x38 bytes: u32 0x10000 (block size), u32 2 (format), u32 end nibble address, u32 2 (start
        nibble), 16 x s16 DSP-ADPCM coefficients, u16 gain 0, u16 initial ps, s16 yn1 0, s16 yn2 0
  0x80  blocks, each with a 0x20-byte header: u32 data bytes (all channels), u32 last nibble index in this block,
        u32 offset of the next block (0xFFFFFFFF ends the stream; an earlier offset loops), then per channel
        u16 ps, s16 yn1, s16 yn2, u16 0; then channel 0's data, then channel 1's. Full blocks hold 0x8000 bytes per
        channel; the last block's per-channel data is padded to 0x20 and its last nibble marks the true end.

All big-endian. One coefficient set per channel for the whole stream; the ADPCM history runs on across blocks (each block
header repeats the decoder state at its start, so the player can seek). Nothing game-derived lives in the repo: point this
at your own files.

Usage:
  hps.py info FILE.hps [...]                     rate, channels, blocks, samples, duration, loop
  hps.py decode FILE.hps OUT.wav                 16-bit PCM WAV
  hps.py encode IN.wav OUT.hps [--loop-start S]  DSP-ADPCM, stereo at the WAV's rate (Melee's fanfares: 32 kHz)
  hps.py check FILE.hps [--vgmstream PATH]       decode with this module and with vgmstream-cli; re-encode, re-decode;
                                                 report bit-exactness, SNR and the container fields
"""
import os, struct, subprocess, sys, tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dspadpcm

MAGIC = b' HALPST\0'
BLOCK_CH = 0x8000            # bytes of ADPCM per channel in a full block
HDR = 0x80


def _align(n, a):
    return (n + a - 1) // a * a


def read(path_or_bytes):
    """-> dict(rate, channels, coefs[ch], blocks[list of dict], pcm int16 (n, ch), loop_block or None)."""
    d = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else open(path_or_bytes, 'rb').read()
    assert d[:8] == MAGIC, 'not a HALPST file'
    rate, nch = struct.unpack('>II', d[8:16])
    chans = []
    for c in range(nch):
        o = 0x10 + 0x38 * c
        blk, fmt, end, start = struct.unpack('>IIII', d[o:o + 16])
        coefs = struct.unpack('>16h', d[o + 16:o + 48])
        gain, ps, yn1, yn2 = struct.unpack('>HHhh', d[o + 48:o + 56])
        chans.append(dict(block=blk, fmt=fmt, end=end, start=start, gain=gain, ps=ps, yn1=yn1, yn2=yn2,
                          coefs=[(coefs[2 * i], coefs[2 * i + 1]) for i in range(8)]))
    blocks, seen, o = [], {}, HDR
    while True:
        size, lastnib, nxt = struct.unpack('>III', d[o:o + 12])
        st = [struct.unpack('>Hhh', d[o + 12 + 8 * c:o + 18 + 8 * c]) for c in range(nch)]
        per = size // nch
        blocks.append(dict(off=o, size=size, lastnib=lastnib, next=nxt, state=st,
                           data=[d[o + 0x20 + per * c:o + 0x20 + per * (c + 1)] for c in range(nch)]))
        seen[o] = len(blocks) - 1
        if nxt == 0xFFFFFFFF or nxt in seen:
            break
        o = nxt
    loop_block = seen.get(blocks[-1]['next']) if blocks[-1]['next'] != 0xFFFFFFFF else None
    pcm = []
    for c in range(nch):
        parts = []
        for b in blocks:
            nib = b['lastnib'] + 1
            n = (nib // 16) * 14 + max(0, nib % 16 - 2)
            ps, yn1, yn2 = b['state'][c]
            parts.append(dspadpcm.decode(b['data'][c], chans[c]['coefs'], n, yn1, yn2))
        pcm.append(np.concatenate(parts))
    pcm = np.stack(pcm, 1)
    return dict(rate=rate, channels=nch, chans=chans, blocks=blocks, pcm=pcm, loop_block=loop_block)


def write(path, pcm, rate=32000, loop_start=None, coefs=None, exact_loop=False):
    """pcm: int16 (n, ch). loop_start: sample index to loop to, None = play once. By default the loop rounds down to a
    full-block start (1.792 s at 32 kHz). exact_loop: the loop starts at loop_start itself, as HAL's own stage streams
    do (their blocks aren't all 0x8000 per channel: Dream Land's old_kb.hps has 0x7F80 and 0x7F60 blocks): the block
    before the loop is cut short to end there. loop_start must then be a multiple of 56 samples (4 ADPCM frames, so every
    block stays a multiple of 0x20 bytes, as the vanilla ones are).
    Returns the bytes written and a report (per-channel SNR of the decoded stream against the input)."""
    pcm = np.asarray(pcm)
    assert pcm.dtype == np.int16 and pcm.ndim == 2, 'int16 (n, channels) expected'
    n, nch = pcm.shape
    spb = BLOCK_CH // 8 * 14                               # samples per full block per channel (57344)
    enc, dec, cfs = [], [], []
    for c in range(nch):
        cf = coefs[c] if coefs else dspadpcm.correlate_coefs(pcm[:, c])
        data, info = dspadpcm.encode(pcm[:, c], cf)
        enc.append(data); cfs.append(cf)
        dec.append(dspadpcm.decode(data, cf, n))
    # block start samples: full blocks, and with an exact loop a short block ending at the loop start
    if exact_loop and loop_start is not None:
        ls = int(loop_start)
        assert ls % 56 == 0 and 0 < ls < n, 'an exact loop start must be a multiple of 56 samples inside the stream'
        starts = list(range(0, ls, spb)) + list(range(ls, n, spb))
    else:
        starts = list(range(0, n, spb))
    nblocks = len(starts)
    bounds = starts + [n]
    if loop_start is None:
        loop_block = None
    elif exact_loop:
        loop_block = starts.index(int(loop_start))
    else:
        loop_block = min(int(loop_start) // spb, nblocks - 1)
    out = bytearray(HDR)
    offs = []
    body = bytearray()
    end_nib = 0
    nib0 = 0                                               # the block's first nibble in the channel's stream
    for b in range(nblocks):
        s0, s1 = bounds[b], bounds[b + 1]
        ns = s1 - s0
        fr = -(-ns // 14)
        per = fr * 8 if b < nblocks - 1 else _align(fr * 8, 0x20)
        last_in_frame = ns - (fr - 1) * 14                 # samples used in the final frame (1..14)
        lastnib = (fr - 1) * 16 + 1 + last_in_frame
        offs.append(HDR + len(body))
        hdr = bytearray(0x20)
        struct.pack_into('>III', hdr, 0, per * nch, lastnib, 0)
        for c in range(nch):
            chunk = enc[c][s0 // 14 * 8:(s0 // 14 + fr) * 8]
            yn1 = int(dec[c][s0 - 1]) if s0 >= 1 else 0
            yn2 = int(dec[c][s0 - 2]) if s0 >= 2 else 0
            struct.pack_into('>Hhh', hdr, 12 + 8 * c, chunk[0], yn1, yn2)
        blk = bytes(hdr)
        for c in range(nch):
            chunk = enc[c][s0 // 14 * 8:(s0 // 14 + fr) * 8]
            blk += chunk + b'\0' * (per - len(chunk))
        body += blk
        end_nib = nib0 + lastnib
        nib0 += per * 2
    for b in range(nblocks):                               # next pointers
        o = offs[b] - HDR
        nxt = offs[b + 1] if b + 1 < nblocks else (offs[loop_block] if loop_block is not None else 0xFFFFFFFF)
        struct.pack_into('>I', body, o + 8, nxt)
    out[0:8] = MAGIC
    struct.pack_into('>II', out, 8, rate, nch)
    for c in range(nch):
        o = 0x10 + 0x38 * c
        struct.pack_into('>IIII', out, o, BLOCK_CH * 2, 2, end_nib, 2)
        struct.pack_into('>16h', out, o + 16, *[v for pair in cfs[c] for v in pair])
        struct.pack_into('>HHhh', out, o + 48, 0, enc[c][0], 0, 0)
    data = bytes(out + body)
    if path:
        open(path, 'wb').write(data)
    rep = dict(samples=n, seconds=n / rate, blocks=nblocks, bytes=len(data), loop_block=loop_block,
               loop_sample=None if loop_block is None else starts[loop_block],
               snr_db=[round(float(dspadpcm.snr_db(pcm[:, c], dec[c])), 2) for c in range(nch)])
    return data, rep


def info(path):
    h = read(path)
    n = len(h['pcm'])
    return dict(file=os.path.basename(path), rate=h['rate'], channels=h['channels'], blocks=len(h['blocks']),
                samples=n, seconds=round(n / h['rate'], 4), loop_block=h['loop_block'], bytes=os.path.getsize(path),
                end_nibble=hex(h['chans'][0]['end']))


def _wav_read(path):
    import soundfile as sf
    x, sr = sf.read(path, dtype='int16', always_2d=True)
    return x, sr


def _wav_write(path, pcm, rate):
    import soundfile as sf
    sf.write(path, pcm, rate, subtype='PCM_16')


def check(path, vgm='/opt/homebrew/bin/vgmstream-cli'):
    """Decode with this module and vgmstream; re-encode the decoded PCM and compare the container fields."""
    h = read(path)
    rep = info(path)
    if os.path.exists(vgm):
        with tempfile.TemporaryDirectory() as td:
            o = os.path.join(td, 'v.wav')
            subprocess.run([vgm, '-i', '-o', o, path], check=True, capture_output=True)
            v, sr = _wav_read(o)
        m = min(len(v), len(h['pcm']))
        rep['vgmstream_samples'] = len(v)
        rep['decode_equals_vgmstream'] = bool(len(v) == len(h['pcm']) and np.array_equal(v, h['pcm']))
        rep['max_abs_diff_vs_vgmstream'] = int(np.abs(v[:m].astype(int) - h['pcm'][:m]).max())
    data, wrep = write(None, h['pcm'], h['rate'],
                       loop_start=None if h['loop_block'] is None else h['loop_block'] * (BLOCK_CH // 8 * 14))
    h2 = read(data)
    rep['reencode_same_size'] = len(data) == os.path.getsize(path)
    rep['reencode_same_layout'] = [(b['size'], b['lastnib'], b['next']) for b in h2['blocks']] == \
                                  [(b['size'], b['lastnib'], b['next']) for b in h['blocks']]
    rep['reencode_header_fields_equal'] = all(
        (a['block'], a['fmt'], a['end'], a['start']) == (b['block'], b['fmt'], b['end'], b['start'])
        for a, b in zip(h['chans'], h2['chans']))
    rep['reencode_snr_db'] = wrep['snr_db']
    return rep


if __name__ == '__main__':
    import argparse, json
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('info'); p.add_argument('files', nargs='+')
    p = sub.add_parser('decode'); p.add_argument('file'); p.add_argument('out')
    p = sub.add_parser('encode'); p.add_argument('wav'); p.add_argument('out'); p.add_argument('--loop-start', type=int)
    p = sub.add_parser('check'); p.add_argument('file'); p.add_argument('--vgmstream', default='/opt/homebrew/bin/vgmstream-cli')
    a = ap.parse_args()
    if a.cmd == 'info':
        for f in a.files:
            print(json.dumps(info(f)))
    elif a.cmd == 'decode':
        h = read(a.file); _wav_write(a.out, h['pcm'], h['rate']); print(json.dumps(info(a.file)))
    elif a.cmd == 'encode':
        x, sr = _wav_read(a.wav)
        _, rep = write(a.out, x, sr, loop_start=a.loop_start); print(json.dumps(rep))
    elif a.cmd == 'check':
        print(json.dumps(check(a.file, a.vgmstream), indent=1))
